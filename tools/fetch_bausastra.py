#!/usr/bin/env python3
"""Unduh Bausastra Jawa Poerwadarminta 1939 dari sastra.org (28 bagian A-Z).
Struktur mudah: <dt>kata :</dt><dd>definisi</dd> per entri.
Keluaran: data/bausastra_raw.jsonl {part, headword, definition}.

Sopan: delay antar request, User-Agent jelas, resume (lewati part selesai).
Yayasan Sastra Lestari, CC BY-NC (atribusi di aplikasi).

Usage:
    python3 tools/fetch_bausastra.py [--delay 1.0] [--status]
"""
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "bausastra_raw.jsonl")
BASE = "https://www.sastra.org/bahasa-dan-budaya/kamus-dan-leksikon"
UA = {"User-Agent": "BasaJawa-Offline/1.0 (kamus offline non-komersial)"}

# Koleksi #781-#808 (28 bagian; 12-y = halaman pola ini)
PARTS = [
    ("01-a", "781-bausastra-jawa-poerwadarminta-1939-75-bagian-01-a"),
    ("02-b", "782-bausastra-jawa-poerwadarminta-1939-75-bagian-02-b"),
    ("03-kh", "783-bausastra-jawa-poerwadarminta-1939-75-bagian-03-kh"),
    ("04-d", "784-bausastra-jawa-poerwadarminta-1939-75-bagian-04-d"),
    ("05-j", "785-bausastra-jawa-poerwadarminta-1939-75-bagian-05-j"),
    ("06-dh", "786-bausastra-jawa-poerwadarminta-1939-75-bagian-06-dh"),
    ("07-e", "787-bausastra-jawa-poerwadarminta-1939-75-bagian-07-e"),
    ("08-e", "788-bausastra-jawa-poerwadarminta-1939-75-bagian-08-e"),
    ("09-g", "789-bausastra-jawa-poerwadarminta-1939-75-bagian-09-g"),
    ("10-h", "790-bausastra-jawa-poerwadarminta-1939-75-bagian-10-h"),
    ("11-i", "791-bausastra-jawa-poerwadarminta-1939-75-bagian-11-i"),
    ("12-y", "792-bausastra-jawa-poerwadarminta-1939-75-bagian-12-y"),
    ("13-k", "793-bausastra-jawa-poerwadarminta-1939-75-bagian-13-k"),
    ("14-l", "794-bausastra-jawa-poerwadarminta-1939-75-bagian-14-l"),
    ("15-m", "795-bausastra-jawa-poerwadarminta-1939-75-bagian-15-m"),
    ("16-n", "796-bausastra-jawa-poerwadarminta-1939-75-bagian-16-n"),
    ("17-ny", "797-bausastra-jawa-poerwadarminta-1939-75-bagian-17-ny"),
    ("18-ng", "798-bausastra-jawa-poerwadarminta-1939-75-bagian-18-ng"),
    ("19-u", "799-bausastra-jawa-poerwadarminta-1939-75-bagian-19-u"),
    ("20-o", "800-bausastra-jawa-poerwadarminta-1939-75-bagian-20-o"),
    ("21-p", "801-bausastra-jawa-poerwadarminta-1939-75-bagian-21-p"),
    ("22-r", "802-bausastra-jawa-poerwadarminta-1939-75-bagian-22-r"),
    ("23-s", "803-bausastra-jawa-poerwadarminta-1939-75-bagian-23-s"),
    ("24-t", "804-bausastra-jawa-poerwadarminta-1939-75-bagian-24-t"),
    ("25-c", "805-bausastra-jawa-poerwadarminta-1939-75-bagian-25-c"),
    ("26-th", "806-bausastra-jawa-poerwadarminta-1939-75-bagian-26-th"),
    ("27-w", "807-bausastra-jawa-poerwadarminta-1939-75-bagian-27-w"),
    ("28-z", "808-bausastra-jawa-poerwadarminta-1939-75-bagian-28-z"),
]


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse(html):
    """-> list[(headword, definition)] dari pasangan dt/dd."""
    items = []
    for m in re.finditer(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", html, flags=re.S):
        head = clean(m.group(1)).rstrip(":").strip()
        defi = clean(m.group(2))
        if not head or not defi:
            continue
        if re.match(r"^---?\s*\d+", head):
            continue  # nomor halaman
        if "~" in head and len(head.split()) <= 3 and not defi:
            continue
        items.append((head, defi))
    return items


def main():
    delay = 1.0
    for a in sys.argv[1:]:
        if a.startswith("--delay="):
            delay = float(a.split("=", 1)[1])
    if "--status" in sys.argv:
        n = sum(1 for _ in open(OUT, encoding="utf-8")) if os.path.exists(OUT) else 0
        print(f"BAUSASTRA status: {n} baris raw")
        return 0
    os.makedirs(DATA, exist_ok=True)
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line).get("part"))
                except Exception:
                    pass
    print(f"  sudah selesai: {sorted(done) or '-'}")
    total = 0
    with open(OUT, "a", encoding="utf-8") as f:
        for part, slug in PARTS:
            if part in done:
                continue
            url = f"{BASE}/{slug}"
            try:
                req = urllib.request.Request(url, headers=UA)
                html = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", errors="replace")
            except Exception as e:
                print(f"  [{part}] gagal: {e}")
                continue
            items = parse(html)
            for head, defi in items:
                f.write(json.dumps({"part": part, "headword": head, "definition": defi},
                                   ensure_ascii=False) + "\n")
            f.flush()
            total += len(items)
            print(f"  [{part}] +{len(items)} entri")
            time.sleep(delay)
    print(f"BAUSASTRA_OK: +{total} entri sesi ini")


if __name__ == "__main__":
    sys.exit(main())
