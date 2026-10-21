#!/usr/bin/env python3
"""Crawler sopan KBJI (Kamus Basa Jawa-Indonesia, Balai Bahasa DIY).
Sumber publik resmi: https://kbji.kemendikdasmen.go.id  (~41 rb lema, JV->ID + tingkat tutur).

Alur:
  Fase 1: /abjad/{A-Z}?page=N  -> kumpulkan slug /kata/*  -> data/kbji_slugs.json
  Fase 2: /kata/{slug}          -> parse lema + definisi -> data/kbji_raw.jsonl

Sopan: delay antar request, User-Agent jelas, resume otomatis (lewati slug selesai),
semua output mentah di data/ (tidak ikut APK). Baca robots.txt sekali saat mulai.

Usage:
    python3 tools/fetch_kbji.py --slugs [--letters AB...] [--delay 0.5]
    python3 tools/fetch_kbji.py --details [--limit N] [--delay 0.5]
    python3 tools/fetch_kbji.py --status
"""
import argparse
import html as ihtml
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SLUGS = os.path.join(DATA, "kbji_slugs.json")
RAW = os.path.join(DATA, "kbji_raw.jsonl")
BASE = "https://kbji.kemendikdasmen.go.id"
UA = {"User-Agent": "BasaJawa-Offline/1.0 (kamus offline non-komersial; kontak: balaibahasadiy@kemendikdasmen.go.id)"}


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def clean_text(s):
    s = re.sub(r"\s+", " ", ihtml.unescape(s)).strip()
    return s


def expand_abbr(p_html):
    # <span class="kbji-abbr" ... title="untuk">utk</span> -> "untuk"
    def rep(m):
        title, short = m.group(1), m.group(2)
        return title.strip() if title.strip() else short.strip()
    return re.sub(r'<span[^>]*class="[^"]*kbji-abbr[^"]*"[^>]*title="([^"]*)"[^>]*>(.*?)</span>',
                  rep, p_html, flags=re.S)


def _clean_pair(head_html, defi_html):
    """(head, defi) bersih dari potongan HTML entri; None bila bukan entri."""
    head = clean_text(re.sub(r"<[^>]+>", " ", head_html))
    defi = clean_text(re.sub(r"<[^>]+>", " ", defi_html))
    defi = re.sub(r"^(Padanan & Definisi Indonesia|\d+\s*lema ditemukan)\s*", "", defi)
    if not head or len(head) > 80 or not defi or len(defi) < 2:
        return None
    if "Hasil Pencarian" in head or "Daftar lema" in defi:
        return None
    return head, defi


def _split_heads(head):
    """'blekik, keblekik' -> [blekik, keblekik]; batasi 4 kata-kata valid."""
    parts = [p.strip() for p in head.split(",")]
    out = [p for p in parts
           if re.match(r"^[A-Za-zêéè'\- ]{1,40}$", p) and " " not in p.strip()]
    return out[:4] or ([head] if len(head) <= 80 else [])


def parse_detail(html):
    """-> list[(headword, definition)] dari kartu hasil.
    Mendukung dua layout: span.kbji-entry-copy (dengan <b> di depan) dan
    <p> yang langsung diawali <b>."""
    items = []
    # span copy selalu diikuti span actions sebagai sibling -> jangkar akhir
    # (isi mengandung nested span abbr, jadi </span> pertama BUKAN penutup).
    for m in re.finditer(
            r'<span[^>]*class="[^"]*kbji-entry-copy[^"]*"[^>]*>(.*?)</span>'
            r"\s*<span[^>]*kbji-entry-actions",
            html, flags=re.S):
        body = expand_abbr(m.group(1))
        hm = re.match(r"\s*<b>(.*?)</b>(.*)$", body, flags=re.S)
        if not hm:
            continue
        r = _clean_pair(hm.group(1), hm.group(2))
        if r:
            items.append(r)
    # SELALU jalankan fallback <p>: halaman berisi kedua format untuk lema berbeda
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, flags=re.S):
            body = expand_abbr(m.group(1))
            hm = re.match(r"\s*<b>(.*?)</b>(.*)$", body, flags=re.S)
            if not hm:
                continue
            r = _clean_pair(hm.group(1), hm.group(2))
            if r:
                items.append(r)
    # pecah multi-head + dedup lokal
    seen, out = set(), []
    for h, d in items:
        for h1 in _split_heads(h):
            if (h1.lower(), d) not in seen:
                seen.add((h1.lower(), d))
                out.append((h1, d))
    return out


def phase_slugs(letters, delay):
    slugs = {}
    if os.path.exists(SLUGS):
        slugs = json.load(open(SLUGS, encoding="utf-8"))
        print(f"  slugs tersimpan: {sum(len(v) for v in slugs.values())}")
    for L in letters:
        page, max_page, fresh = 1, None, 0
        known = set(slugs.get(L, []))
        while True:
            url = f"{BASE}/abjad/{L}" + (f"?page={page}" if page > 1 else "")
            try:
                html = fetch(url)
            except Exception as e:
                print(f"  [{L} p{page}] gagal: {e}; berhenti di huruf ini")
                break
            found = re.findall(r"/kata/([^\"'<> ]+)", html)
            new = [s for s in found if s not in known]
            known.update(found)
            fresh += len(new)
            if max_page is None:
                pages = [int(x) for x in re.findall(r"/abjad/%s\?page=(\d+)" % L, html)]
                max_page = max(pages) if pages else 1
                print(f"  [{L}] {max_page} halaman")
            print(f"  [{L} p{page}/{max_page}] +{len(new)} slug (total {len(known)})")
            if page >= max_page or not found:
                break
            page += 1
            time.sleep(delay)
        slugs[L] = sorted(known)
        json.dump(slugs, open(SLUGS, "w", encoding="utf-8"), ensure_ascii=False)
    total = sum(len(v) for v in slugs.values())
    print(f"SLUGS_OK: {total} slug unik")
    return total


def phase_details(limit, delay, workers=1):
    if not os.path.exists(SLUGS):
        print("Jalankan --slugs dulu.")
        return 1
    slugs = json.load(open(SLUGS, encoding="utf-8"))
    done = set()
    if os.path.exists(RAW):
        with open(RAW, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line).get("slug"))
                except Exception:
                    pass
    print(f"  sudah selesai: {len(done)} slug")
    todo = [s for L in sorted(slugs) for s in slugs[L] if s not in done]
    if limit:
        todo = todo[:limit]
    print(f"  antre: {len(todo)} slug, workers={workers}, delay={delay}")
    lock = threading.Lock()
    state = {"i": 0, "n_new": 0, "n_err": 0}
    fout = open(RAW, "a", encoding="utf-8")

    def one(slug):
        url = f"{BASE}/kata/{slug}"
        try:
            html = fetch(url)
            rows = [json.dumps({"slug": slug, "headword": h, "definition": d},
                               ensure_ascii=False) + "\n"
                    for h, d in parse_detail(html)]
        except Exception as e:
            rows, err = [], str(e)
        else:
            err = None
        time.sleep(delay)
        with lock:
            state["i"] += 1
            if err:
                state["n_err"] += 1
                if state["n_err"] <= 5:
                    print(f"  [{state['i']}/{len(todo)}] {slug} gagal: {err}", flush=True)
            else:
                for r in rows:
                    fout.write(r)
                state["n_new"] += len(rows)
            if state["i"] % 200 == 0:
                fout.flush()
                print(f"  [{state['i']}/{len(todo)}] {state['n_new']} entri, "
                      f"{state['n_err']} gagal...", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, todo))
    fout.close()
    print(f"DETAILS_OK: +{state['n_new']} entri, {state['n_err']} gagal")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", action="store_true")
    ap.add_argument("--details", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--letters", default="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    if a.status or (not a.slugs and not a.details):
        n_slug = sum(len(v) for v in json.load(open(SLUGS, encoding="utf-8")).values()) if os.path.exists(SLUGS) else 0
        n_raw = sum(1 for _ in open(RAW, encoding="utf-8")) if os.path.exists(RAW) else 0
        print(f"KBJI status: {n_slug} slug, {n_raw} baris raw")
        return 0
    try:
        robots = fetch(BASE + "/robots.txt")
        print("  robots.txt:", robots[:200].replace("\n", " | "))
    except Exception as e:
        print("  robots.txt tak terbaca:", e)
    if a.slugs:
        phase_slugs(a.letters, a.delay)
    if a.details:
        return phase_details(a.limit, a.delay, a.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
