"""端到端 API 测试：认证、习惯、打卡、统计、血压、推送订阅、管理后台。

既可以用 `python3 tests/run_tests.py` 直接运行，也可以在装有 pytest 的环境里用 pytest 运行。
"""
import os
import tempfile
from datetime import date, timedelta

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="dailycreate-test-")
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["START_SCHEDULER"] = "0"

from fastapi.testclient import TestClient

from app.dates import today_str
from app.main import app

PASSWORD = "pass1234"

# 模块级共享客户端（触发 lifespan 建表）
client = TestClient(app)
client.__enter__()


def register(username, invite=None):
    return client.post("/api/auth/register", json={
        "username": username, "password": PASSWORD, "invite_code": invite,
    })


def login(username):
    return client.post("/api/auth/login", json={"username": username, "password": PASSWORD})


def new_invite():
    r = client.post("/api/admin/invite-codes", json={"expires_days": 30})
    assert r.status_code == 201
    return r.json()["code"]


# ---------- 认证 ----------
def test_first_user_becomes_admin():
    r = register("admin")
    assert r.status_code == 201
    assert r.json()["is_admin"] is True
    assert login("admin").status_code == 200


def test_me_requires_auth():
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    login("admin")


def test_register_requires_invite():
    assert register("nobody").status_code == 400
    assert register("nobody2", invite="WRONG123").status_code == 400


def test_register_with_invite_and_reuse_rejected():
    login("admin")
    code = new_invite()
    assert register("member", invite=code).status_code == 201
    # 邀请码只能使用一次
    assert register("member2", invite=code).status_code == 400


def test_login_wrong_password():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_logout():
    login("admin")
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    login("admin")


# ---------- 习惯 ----------
def test_habit_crud_and_isolation():
    login("admin")
    r = client.post("/api/habits", json={
        "name": "锻炼", "value_label": "分钟", "reminder_time": "07:30", "reminder_enabled": True,
    })
    assert r.status_code == 201
    habit_id = r.json()["id"]
    assert client.get("/api/habits").json()[0]["name"] == "锻炼"

    # 其他用户看不到、改不了这个习惯（成员有自己的默认习惯，但不应包含管理员的习惯 id）
    login("member")
    ids = [h["id"] for h in client.get("/api/habits").json()]
    assert habit_id not in ids
    assert client.patch(f"/api/habits/{habit_id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/habits/{habit_id}").status_code == 404

    login("admin")
    r = client.patch(f"/api/habits/{habit_id}", json={"name": "晨跑", "reminder_enabled": False})
    assert r.status_code == 200
    assert r.json()["name"] == "晨跑"
    assert r.json()["reminder_enabled"] is False
    assert client.delete(f"/api/habits/{habit_id}").status_code == 204


def test_habit_validation():
    login("admin")
    assert client.post("/api/habits", json={"name": "x", "reminder_time": "25:99"}).status_code == 422
    assert client.post("/api/habits", json={"name": "x", "color": "notacolor"}).status_code == 422


# ---------- 打卡 ----------
def test_checkin_upsert_backfill_and_future_rejected():
    login("admin")
    habit_id = client.post("/api/habits", json={"name": "吃药"}).json()["id"]

    r = client.put(f"/api/checkins/{habit_id}?date={today_str()}", json={"done": True, "value": "1"})
    assert r.status_code == 200
    assert r.json()["done"] is True

    # 同一天再次提交视为更新
    r = client.put(f"/api/checkins/{habit_id}?date={today_str()}", json={"done": True, "value": "2", "note": "晚饭后"})
    assert r.json()["value"] == "2"

    # 补打卡（过去日期）
    past = (date.fromisoformat(today_str()) - timedelta(days=3)).isoformat()
    assert client.put(f"/api/checkins/{habit_id}?date={past}", json={"done": True}).status_code == 200

    # 未来日期不允许
    future = (date.fromisoformat(today_str()) + timedelta(days=1)).isoformat()
    assert client.put(f"/api/checkins/{habit_id}?date={future}", json={"done": True}).status_code == 400

    data = client.get(f"/api/today?date={today_str()}").json()
    assert any(h["id"] == habit_id and h["checkin"]["done"] for h in data["habits"])


# ---------- 统计 ----------
def test_month_stats_and_streak():
    login("admin")
    habit_id = client.post("/api/habits", json={"name": "阅读"}).json()["id"]
    for d in ("2020-01-10", "2020-01-20"):
        client.put(f"/api/checkins/{habit_id}?date={d}", json={"done": True})

    stats = client.get("/api/stats/month?year=2020&month=1").json()
    habit = next(h for h in stats["habits"] if h["id"] == habit_id)
    assert habit["done_count"] == 2
    assert habit["elapsed_days"] == 31
    assert habit["rate"] == round(2 / 31, 2)
    assert habit["days"].get("2020-01-10") is True

    # 连续天数：昨天+今天打卡
    yesterday = (date.fromisoformat(today_str()) - timedelta(days=1)).isoformat()
    client.put(f"/api/checkins/{habit_id}?date={yesterday}", json={"done": True})
    client.put(f"/api/checkins/{habit_id}?date={today_str()}", json={"done": True})
    streak = client.get(f"/api/habits/{habit_id}/streak").json()["streak"]
    assert streak >= 2


# ---------- 血压 ----------
def test_bp_crud_and_validation():
    login("admin")
    today = today_str()
    r = client.post("/api/bp", json={"date": today, "time": "07:30", "systolic": 128, "diastolic": 82, "pulse": 72})
    assert r.status_code == 201
    bp_id = r.json()["id"]
    assert r.json()["systolic"] == 128

    client.post("/api/bp", json={"date": today, "time": "20:00", "systolic": 118, "diastolic": 76})

    data = client.get("/api/bp?days=30").json()
    assert data["count"] == 2
    assert data["avg_systolic"] == round((128 + 118) / 2, 1)
    assert len(data["records"]) == 2

    # 收缩压必须高于舒张压
    assert client.post("/api/bp", json={"date": today, "systolic": 80, "diastolic": 90}).status_code == 400
    # 未来日期
    future = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    assert client.post("/api/bp", json={"date": future, "systolic": 120, "diastolic": 80}).status_code == 400
    # 数值越界
    assert client.post("/api/bp", json={"date": today, "systolic": 999, "diastolic": 80}).status_code == 422

    # 修改与删除
    r = client.patch(f"/api/bp/{bp_id}", json={"systolic": 122, "note": "复测"})
    assert r.status_code == 200
    assert r.json()["systolic"] == 122
    assert r.json()["note"] == "复测"
    assert client.delete(f"/api/bp/{bp_id}").status_code == 204

    # 他人不可见
    login("member")
    assert client.get("/api/bp?days=30").json()["count"] == 0
    assert client.delete(f"/api/bp/{bp_id}").status_code == 404


# ---------- 推送 ----------
def test_vapid_and_subscribe():
    login("admin")
    key = client.get("/api/push/vapid-public-key").json()["public_key"]
    assert len(key) > 20

    endpoint = "https://push.example.com/fake-endpoint-123"
    r = client.post("/api/push/subscribe", json={
        "endpoint": endpoint, "p256dh": "x" * 87, "auth": "y" * 22,
    })
    assert r.status_code == 200
    assert client.delete(f"/api/push/subscribe?endpoint={endpoint}").status_code == 200


# ---------- 管理后台 ----------
def test_admin_members_and_disable():
    login("admin")
    members = {m["username"]: m for m in client.get("/api/admin/members").json()}
    assert members["admin"]["is_admin"] is True

    member_id = members["member"]["id"]
    r = client.patch(f"/api/admin/members/{member_id}", json={"is_disabled": True})
    assert r.status_code == 200
    assert r.json()["is_disabled"] is True

    # 停用后无法登录
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "member", "password": PASSWORD}).status_code == 403
    login("admin")
    client.patch(f"/api/admin/members/{member_id}", json={"is_disabled": False})

    # 非管理员无权访问
    login("member")
    assert client.get("/api/admin/members").status_code == 403
    login("admin")


def test_invite_codes_list():
    login("admin")
    codes = client.get("/api/admin/invite-codes").json()
    assert len(codes) >= 1
    assert all(c["code"] for c in codes)


# ---------- Web Push 加密正确性 ----------
def test_push_crypto_roundtrip():
    import struct

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    from app.push_service import _b64url, _encrypt_payload, _load_or_generate_keys, _vapid_authorization

    # 模拟浏览器订阅：P-256 密钥对 + 16 字节 auth
    sub_key = ec.generate_private_key(ec.SECP256R1())
    pn = sub_key.public_key().public_numbers()
    ua_public = b"\x04" + pn.x.to_bytes(32, "big") + pn.y.to_bytes(32, "big")
    auth_secret = os.urandom(16)
    p256dh = _b64url(ua_public)
    auth = _b64url(auth_secret)

    payload = "打卡提醒：吃药 今天还没打卡".encode("utf-8")
    body, headers = _encrypt_payload(p256dh, auth, payload)

    # 解析 aes128gcm 记录头
    salt = body[:16]
    rs = struct.unpack(">I", body[16:20])[0]
    idlen = body[20]
    server_pub = body[21:21 + idlen]
    ciphertext = body[21 + idlen:]
    assert idlen == 65
    assert rs == len(payload) + 16

    # 订阅方解密
    server_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), server_pub)
    shared = sub_key.exchange(ec.ECDH(), server_public)
    info = b"WebPush: info\x00" + ua_public + server_pub
    prk = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth_secret, info=b"Content-Encoding: auth\x00").derive(shared)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=None, info=b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=None, info=b"Content-Encoding: nonce\x00").derive(prk)
    plain = AESGCM(cek).decrypt(nonce, ciphertext, body[:21 + idlen])
    assert plain == payload
    assert headers["Content-Encoding"] == "aes128gcm"

    # VAPID JWT 签名可验证
    priv, pub = _load_or_generate_keys()
    authz = _vapid_authorization(priv, pub, "https://push.example.com")
    assert authz.startswith("vapid t=")
    token = authz.split("t=")[1].split(",")[0].strip()
    hdr, claims, sig_b64 = token.split(".")
    signing_input = f"{hdr}.{claims}".encode()
    sig = __import__("base64").urlsafe_b64decode(sig_b64 + "===")
    r = int.from_bytes(sig[:32], "big")
    s = int.from_bytes(sig[32:], "big")
    der = utils.encode_dss_signature(r, s)
    pub_point = __import__("base64").urlsafe_b64decode(pub + "===")
    verify_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub_point)
    verify_key.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))


# ---------- 指标（体重等） ----------
def test_metrics_crud_and_validation():
    login("admin")
    today = today_str()
    r = client.post("/api/metrics", json={"name": "体重", "value": 65.5, "unit": "kg", "date": today})
    assert r.status_code == 201
    mid = r.json()["id"]
    assert r.json()["value"] == 65.5

    client.post("/api/metrics", json={"name": "体重", "value": 64.8, "unit": "kg", "date": today})
    data = client.get("/api/metrics?days=30").json()
    assert data["count"] == 2
    assert data["latest"]["体重"]["value"] == 64.8

    # 未来日期 / 数值越界
    future = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    assert client.post("/api/metrics", json={"name": "体重", "value": 60, "date": future}).status_code == 400
    assert client.post("/api/metrics", json={"name": "体重", "value": 99999, "date": today}).status_code == 422
    assert client.post("/api/metrics", json={"name": "", "value": 60, "date": today}).status_code == 422

    # 修改与删除
    r = client.patch(f"/api/metrics/{mid}", json={"value": 66.0, "note": "饭后"})
    assert r.status_code == 200
    assert r.json()["value"] == 66.0
    assert r.json()["note"] == "饭后"
    assert client.delete(f"/api/metrics/{mid}").status_code == 204

    # 他人不可见
    login("member")
    assert client.get("/api/metrics?days=30").json()["count"] == 0
    assert client.delete(f"/api/metrics/{mid}").status_code == 404
    login("admin")


# ---------- AI 分析 ----------
def test_analysis_requires_key():
    login("admin")
    r = client.post("/api/analysis?days=30")
    assert r.status_code == 400
    assert "AI_API_KEY" in r.json()["detail"]


def test_analysis_generate_with_mock():
    import app.analysis as analysis_mod

    login("admin")
    # 模拟服务器配置了共享 key（测试环境 config 读取时为空，这里运行时注入）
    analysis_mod.AI_API_KEY = "sk-shared-mock"
    analysis_mod.AI_FREE_LIMIT = 5
    # 给 admin 造一点数据，让摘要非空
    hid = client.post("/api/habits", json={"name": "散步"}).json()["id"]
    client.put(f"/api/checkins/{hid}?date={today_str()}", json={"done": True, "value": "30"})
    client.post("/api/bp", json={"date": today_str(), "systolic": 125, "diastolic": 82})
    client.post("/api/metrics", json={"name": "体重", "value": 66, "unit": "kg", "date": today_str()})

    original = analysis_mod.call_llm
    analysis_mod.call_llm = lambda summary, api_key, base_url, model: "### 总体评价\n很好。\n\n### 改进建议\n- 多喝水\n- 早睡"
    try:
        r = client.post("/api/analysis?days=30")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["content"].startswith("### 总体评价")
        assert body["model"]
        aid = body["id"]

        # 列表包含该记录
        lst = client.get("/api/analysis").json()
        assert any(a["id"] == aid for a in lst)

        # 查看单条
        one = client.get(f"/api/analysis/{aid}").json()
        assert one["content"] == body["content"]

        # 他人不可见
        login("member")
        assert client.get(f"/api/analysis/{aid}").status_code == 404
        login("admin")

        # 删除
        assert client.delete(f"/api/analysis/{aid}").status_code == 204
        assert client.get("/api/analysis").json() == []
    finally:
        analysis_mod.call_llm = original
        analysis_mod.AI_API_KEY = ""
        analysis_mod.AI_FREE_LIMIT = 5


# ---------- AI 设置（用户自己的 Key / 共享额度） ----------
def test_ai_status_default():
    login("admin")
    st = client.get("/api/me/ai").json()
    assert st["has_own_key"] is False
    assert isinstance(st["free_used"], int)
    assert "api_key" not in st  # 任何响应都不应包含 key


def test_ai_set_own_key_no_leak_and_clear():
    login("admin")
    # 设置自己的 key
    r = client.put("/api/me/ai", json={"api_key": "sk-own-secret-abc", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"})
    assert r.status_code == 200
    assert "sk-own-secret-abc" not in r.text  # 不泄露
    st = client.get("/api/me/ai").json()
    assert st["has_own_key"] is True
    assert "api_key" not in str(st)
    # 清空恢复
    r = client.put("/api/me/ai", json={"api_key": None})
    assert r.status_code == 200
    assert client.get("/api/me/ai").json()["has_own_key"] is False


def test_ai_free_limit_enforced():
    import app.analysis as analysis_mod

    login("admin")
    analysis_mod.AI_API_KEY = "sk-shared-limit"
    analysis_mod.AI_FREE_LIMIT = 2
    original = analysis_mod.call_llm
    analysis_mod.call_llm = lambda summary, api_key, base_url, model: "### 总体评价\n测试内容"
    try:
        # 清空自己的 key，并把已用次数清零，保证从 0 开始
        client.put("/api/me/ai", json={"api_key": None})
        from app.db import Database as _Db
        _d = _Db()
        _d.execute("UPDATE users SET ai_free_used = 0 WHERE username = 'admin'")
        _d.commit()
        _d.close()
        for _ in range(2):
            r = client.post("/api/analysis?days=30")
            assert r.status_code == 200, r.text
        # 第 3 次应提示额度用完
        r = client.post("/api/analysis?days=30")
        assert r.status_code == 400
        assert "额度已用完" in r.json()["detail"]
        # 填自己的 key 后不再受限
        client.put("/api/me/ai", json={"api_key": "sk-mine"})
        assert client.post("/api/analysis?days=30").status_code == 200
        client.put("/api/me/ai", json={"api_key": None})
    finally:
        analysis_mod.call_llm = original
        analysis_mod.AI_API_KEY = ""
        analysis_mod.AI_FREE_LIMIT = 5
