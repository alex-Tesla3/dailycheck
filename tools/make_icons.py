"""生成 PWA 图标：蓝色圆角方块 + 白色对勾（纯标准库，无第三方依赖）。"""
import math
import struct
import zlib
from pathlib import Path


def _dist_to_segment(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    c1 = vx * wx + vy * wy
    if c1 <= 0:
        return math.hypot(px - ax, py - ay)
    c2 = vx * vx + vy * vy
    if c2 <= c1:
        return math.hypot(px - bx, py - by)
    t = c1 / c2
    return math.hypot(px - (ax + vx * t), py - (ay + vy * t))


def in_rounded_rect(x, y, size, radius):
    r = radius
    if (r <= x < size - r) or (r <= y < size - r):
        return True
    cx = min(max(x, r), size - r)
    cy = min(max(y, r), size - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def make_icon(size: int) -> bytes:
    radius = int(size * 0.22)
    thick = max(2, size * 0.075)
    # 对勾线段（相对坐标，边长 1）
    segs = [
        ((0.28, 0.52), (0.44, 0.68)),
        ((0.44, 0.68), (0.74, 0.34)),
    ]
    rows = []
    for y in range(size):
        row = bytearray([0])  # filter type 0
        t = y / size
        r0 = int(79 + 10 * t)
        g0 = int(140 + 8 * t)
        b0 = int(255 - 12 * t)
        for x in range(size):
            if not in_rounded_rect(x, y, size, radius):
                row += bytes((0, 0, 0, 0))
                continue
            on_check = False
            for (a, b) in segs:
                if _dist_to_segment(
                    x / size, y / size, a[0], a[1], b[0], b[1]
                ) <= thick:
                    on_check = True
                    break
            if on_check:
                row += bytes((255, 255, 255, 255))
            else:
                row += bytes((r0, g0, b0, 255))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    return png


def main():
    out = Path(__file__).resolve().parent.parent / "static"
    for size in (192, 512):
        (out / f"icon-{size}.png").write_bytes(make_icon(size))
        print(f"icon-{size}.png generated")


if __name__ == "__main__":
    main()
