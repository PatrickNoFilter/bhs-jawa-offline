#!/usr/bin/env python3
"""Generate app/res/drawable/ic_launcher.png (512x512) using the Python stdlib only.

Design: batik-brown rounded square, white open-book glyph (kamus) + gold bookmark.
Pola disalin dari make_icon.py katolik-digital-offline (supersampling + stdlib PNG).
"""
import argparse
import os
import struct
import zlib

SIZE = 512
SS = 3  # supersampling per axis -> 9 samples/pixel


def bg_color(x, y):
    """Vertical gradient: top #6b4226 -> bottom #2e1a0e (batik brown)."""
    t = y / SIZE
    r = int(107 + (46 - 107) * t)
    g = int(66 + (26 - 66) * t)
    b = int(38 + (14 - 38) * t)
    return r, g, b


def in_rounded_square(x, y, x0, y0, x1, y1, rad):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + rad), x1 - rad)
    cy = min(max(y, y0 + rad), y1 - rad)
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= rad * rad


def in_book(x, y):
    # open book: two page rects with center spine gap
    # left page
    if 118 <= x <= 244 and 168 <= y <= 372:
        return True
    # right page
    if 268 <= x <= 394 and 168 <= y <= 372:
        return True
    # spine
    if 244 <= x <= 268 and 160 <= y <= 380:
        return True
    return False


def in_textlines(x, y):
    # text lines on pages (cut OUT of the book -> drawn as bg color later)
    if y % 44 < 0:  # pragma: no cover - placeholder guard
        return False
    for ly in (216, 260, 304, 348):
        if ly <= y <= ly + 12:
            if 140 <= x <= 222 or 290 <= x <= 372:
                return True
    return False


def in_bookmark(x, y):
    # gold bookmark ribbon hanging from top-right of book
    if 330 <= x <= 366 and 96 <= y <= 220:
        # notch at bottom
        if y > 188:
            mid = (330 + 366) / 2
            if abs(x - mid) < (y - 188) * 0.55:
                return False
        return True
    return False


def build_png(path):
    raw = bytearray()
    for py in range(SIZE):
        for px in range(SIZE):
            white = 0
            gold = 0
            for sy in range(SS):
                for sx in range(SS):
                    x = (px * SS + sx + 0.5) / SS
                    y = (py * SS + sy + 0.5) / SS
                    if not in_rounded_square(x, y, 20, 20, 492, 492, 46):
                        continue
                    if in_bookmark(x, y):
                        gold += 1
                    elif in_book(x, y) and not in_textlines(x, y):
                        white += 1
            cov_w = white / (SS * SS)
            cov_g = gold / (SS * SS)
            r, g, b = bg_color(px + 0.5, py + 0.5)
            # blend white book glyph
            r = int(r + (250 - r) * cov_w)
            g = int(g + (246 - g) * cov_w)
            b = int(b + (240 - b) * cov_w)
            # blend gold bookmark (#d9a441)
            r = int(r + (217 - r) * cov_g)
            g = int(g + (164 - g) * cov_g)
            b = int(b + (65 - b) * cov_g)
            raw.append(r)
            raw.append(g)
            raw.append(b)
            raw.append(255)

    stride = SIZE * 4
    scanlines = b"".join(b"\x00" + bytes(raw[i:i + stride]) for i in range(0, len(raw), stride))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    print("wrote", path, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="app/res/drawable/ic_launcher.png")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    build_png(args.out)
