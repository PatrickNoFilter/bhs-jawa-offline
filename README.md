# Basa Jawa Offline — Kamus & Ensiklopedia Basa Jawa (offline)

Aplikasi kamus & ensiklopedia Bahasa Jawa yang berjalan 100% offline:
satu file `index.html` (+ data `kamus_data.js`) dibungkus WebView → APK,
**tanpa Gradle**, tanpa internet. Package `id.basajawa.offline`.

Pola build menyalin `katolik-digital-offline`: `javac → d8 → aapt2 → zip → zipalign → apksigner`.

## Isi repo

| Path | Keterangan |
|---|---|
| `index.html` | Source utama aplikasi (WebView) |
| `kamus_data.js` | Data kamus hasil build |
| `RENCANA.md` | Rencana arsitektur & keputusan |
| `apk/app/` | Source wrapper Android (manifest, MainActivity, res) |
| `apk/scripts/` | Script build APK (`01_build_apk.sh`, `make_icon.py`) |
| `apk/dist/` | Hasil build terakhir |
| `BasaJawa-Offline-v*.apk` | Riwayat APK v0.1 → v1.8 |
| `tools/` | Script build kamus (`build_kamus.py`) & fetcher data |
| `data/` | Sumber data kamus (csv/jsonl/xlsx) |
| `logs/` | Log proses crawl/build |

## Yang TIDAK ikut di repo

- `apk/keystore.jks` — keystore penandatangan, hanya ada di HP build.
  Tanpa keystore ini, update APK di Play Store / install menimpa tidak bisa
  ditandatangani ulang dengan sertifikat yang sama. **Jaga baik-baik.**
- `data/kbji_raw.jsonl` (113 MB) — dump mentah crawl KBJI; melebihi batas
  100 MB per file GitHub. Tetap tersimpan di HP, bisa dibuat ulang via
  `tools/fetch_kbji.py`.

## Rilis

APK terbaru selalu dilampirkan di [Releases](../../releases).
