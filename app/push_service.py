"""Web Push 发送服务（RFC 8291 + RFC 8188 aes128gcm）：
首次启动自动生成 VAPID (ECDSA P-256) 密钥；推送加密完全用 cryptography 实现，无第三方推送库。"""
import base64
import json
import os
import struct
import time
from typing import Tuple
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import VAPID_KEYS_PATH, VAPID_SUBJECT

P256_CURVE = ec.SECP256R1()


class SubscriptionGone(Exception):
    """订阅已失效（410/404），应删除该订阅。"""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        super().__init__("subscription gone")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _load_or_generate_keys() -> Tuple[bytes, str]:
    """返回 (private_key_pem_bytes, public_key_b64url)。"""
    if VAPID_KEYS_PATH.exists():
        data = json.loads(VAPID_KEYS_PATH.read_text(encoding="utf-8"))
        return data["private_key"].encode("ascii"), data["public_key"]

    private_key = ec.generate_private_key(P256_CURVE)
    pub_numbers = private_key.public_key().public_numbers()
    pub_bytes = (
        b"\x04"
        + pub_numbers.x.to_bytes(32, "big")
        + pub_numbers.y.to_bytes(32, "big")
    )
    public_key = _b64url(pub_bytes)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    VAPID_KEYS_PATH.write_text(
        json.dumps({"private_key": pem, "public_key": public_key}),
        encoding="utf-8",
    )
    return pem.encode("ascii"), public_key


def get_vapid_public_key() -> str:
    _, public_key = _load_or_generate_keys()
    return public_key


def _es256_sign(private_key: bytes, payload: bytes) -> bytes:
    key = serialization.load_pem_private_key(private_key, password=None)
    der_sig = key.sign(payload, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_sig)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def _vapid_authorization(private_key: bytes, public_key_b64url: str, audience: str) -> str:
    header = _b64url(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    claims = _b64url(json.dumps({
        "aud": audience,
        "exp": int(time.time()) + 12 * 3600,
        "sub": VAPID_SUBJECT,
    }).encode())
    signing_input = f"{header}.{claims}".encode()
    signature = _es256_sign(private_key, signing_input)
    token = f"{header}.{claims}.{_b64url(signature)}"
    return f"vapid t={token}, k={public_key_b64url}"


def _encrypt_payload(p256dh_b64url: str, auth_b64url: str, data: bytes) -> Tuple[bytes, dict]:
    """按 RFC 8291/8188 加密，返回 (body, headers)。"""
    ua_public = base64.urlsafe_b64decode(p256dh_b64url + "===")
    auth_secret = base64.urlsafe_b64decode(auth_b64url + "===")

    server_private = ec.generate_private_key(P256_CURVE)
    server_public = server_private.public_key()
    spn = server_public.public_numbers()
    server_public_bytes = b"\x04" + spn.x.to_bytes(32, "big") + spn.y.to_bytes(32, "big")

    peer_public = ec.EllipticCurvePublicKey.from_encoded_point(P256_CURVE, ua_public)
    shared_secret = server_private.exchange(ec.ECDH(), peer_public)

    info = b"WebPush: info\x00" + ua_public + server_public_bytes
    prk = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth_secret, info=b"Content-Encoding: auth\x00").derive(shared_secret)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=None, info=b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=None, info=b"Content-Encoding: nonce\x00").derive(prk)

    salt = os.urandom(16)
    rs = len(data) + 16
    header = salt + struct.pack(">I", rs) + bytes([len(server_public_bytes)]) + server_public_bytes
    ciphertext = AESGCM(cek).encrypt(nonce, data, header)
    body = header + ciphertext
    return body, {
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": "86400",
    }


def send_push(endpoint: str, p256dh: str, auth: str, title: str, body_text: str) -> None:
    private_key, public_key = _load_or_generate_keys()
    payload = json.dumps({"title": title, "body": body_text}, ensure_ascii=False).encode("utf-8")
    body, headers = _encrypt_payload(p256dh, auth, payload)
    audience = f"{urlparse(endpoint).scheme}://{urlparse(endpoint).netloc}"
    headers["Authorization"] = _vapid_authorization(private_key, public_key, audience)

    try:
        resp = requests.post(endpoint, data=body, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        if resp.status_code in (404, 410):
            raise SubscriptionGone(endpoint) from exc
        raise
