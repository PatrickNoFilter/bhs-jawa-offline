#!/usr/bin/env bash
# Build Basa Jawa Offline APK (WebView wrapper) without Gradle.
# Pipeline: javac -> d8 -> aapt2 -> zip assets -> zipalign -> apksigner
# Pola disalin dari katolik-digital-offline/apk/scripts/01_build_apk.sh
set -euo pipefail

VERSION_CODE=9
VERSION_NAME="1.8"
APK_NAME="BasaJawa-Offline-v${VERSION_NAME}.apk"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_WEB="/storage/emulated/0/Bhs Jawa Offline"
# SDK dipakai ulang dari katolik-digital-offline (tanpa download ulang)
SDK="/storage/emulated/0/katolik-digital-offline/apk/sdk"
BT="$SDK/build-tools/34.0.0"
PLAT="$SDK/platforms/android-35/android.jar"
APP="$ROOT/app"
TMP="$ROOT/tmp"
DIST="$ROOT/dist"

command -v java javac keytool zip >/dev/null || { echo "missing build tools"; exit 1; }
[ -f "$PLAT" ] || { echo "SDK not found at $PLAT"; exit 1; }

# extracted SDK zips may lose the executable bit, and /storage (android FUSE)
# refuses chmod -> stage a runnable copy under /tmp (real fs)
TOOLROOT=/tmp/bjtools
if [ ! -x "$TOOLROOT/aapt2" ]; then
  rm -rf "$TOOLROOT"
  mkdir -p "$TOOLROOT"
  cp -r "$BT/." "$TOOLROOT/"
  find "$TOOLROOT" -type f -exec chmod +x {} + 2>/dev/null || true
fi
BT="$TOOLROOT"

# Google's aapt2/zipalign are x86_64 binaries; emulate on non-x86 hosts (qemu-user)
QEMU=""
if [ "$(uname -m)" != "x86_64" ]; then
  command -v qemu-x86_64 >/dev/null || { echo "qemu-x86_64 required on this arch"; exit 1; }
  QEMU="qemu-x86_64"
fi

rm -rf "$TMP" "$DIST"
mkdir -p "$TMP/classes" "$TMP/dex" "$TMP/assets" "$DIST"

echo "==> 0. assets: index.html mandiri (data inline, pola Katolik)"
mkdir -p "$APP/assets"
cp "$SRC_WEB/index.html" "$APP/assets/index.html"
# kamus_data.js TIDAK ikut: sudah inline di index.html (tetap bisa dibuka via content://)
for f in ensiklopedi_data.js; do
  cp "$SRC_WEB/$f" "$APP/assets/$f" 2>/dev/null || true
done
# bersih: salinan kamus_data.js era v1.1 (kini selalu inline) jangan ikut ter-zip
rm -f "$APP/assets/kamus_data.js"
ls -la "$APP/assets/"

echo "==> 1. icon"
python3 "$ROOT/scripts/make_icon.py" --out "$APP/res/drawable/ic_launcher.png"

echo "==> 2. javac"
# NOTE: path mengandung spasi -> kumpulkan file via array NUL-delimited (anti word-splitting)
mapfile -d '' JAVA_SRC < <(find "$APP/src" -name '*.java' -print0 | sort -z)
javac -source 1.8 -target 1.8 -nowarn -Xlint:-options \
      -bootclasspath "$PLAT" \
      -d "$TMP/classes" "${JAVA_SRC[@]}"

echo "==> 3. d8 (dex)"
mapfile -t DEX_CLS < <(find "$TMP/classes" -name '*.class' | sort)
"$BT/d8" --release --lib "$PLAT" --min-api 24 \
    --output "$TMP/dex" "${DEX_CLS[@]}"
ls -la "$TMP/dex/classes.dex"

echo "==> 4. aapt2 (resources)"
$QEMU "$BT/aapt2" compile --dir "$APP/res" -o "$TMP/res.zip"
$QEMU "$BT/aapt2" link -o "$TMP/base.apk" -I "$PLAT" \
    --manifest "$APP/AndroidManifest.xml" \
    -R "$TMP/res.zip" \
    --min-sdk-version 24 --target-sdk-version 35 \
    --version-code "$VERSION_CODE" --version-name "$VERSION_NAME" \
    --auto-add-overlay

echo "==> 5. assemble (dex + assets into apk)"
cp "$TMP/base.apk" "$TMP/app.unsigned.apk"
cp "$TMP/dex/classes.dex" "$TMP/classes.dex"
mkdir -p "$TMP/assets"
cp "$APP/assets/"* "$TMP/assets/"
( cd "$TMP" && zip -0 -q app.unsigned.apk classes.dex $(ls assets/* | sort) )

echo "==> 6. zipalign"
$QEMU "$BT/zipalign" -f -p 4 "$TMP/app.unsigned.apk" "$TMP/app.aligned.apk"

echo "==> 7. keystore + sign"
KS="$ROOT/keystore.jks"
if [ ! -f "$KS" ]; then
    keytool -genkeypair -keystore "$KS" -alias basajawa \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass basajawa123 -keypass basajawa123 \
        -dname "CN=Basa Jawa Offline, OU=Offline, O=basajawa-web, L=Yogyakarta, ST=DIY, C=ID" 2>/dev/null
fi
"$BT/apksigner" sign --ks "$KS" --ks-key-alias basajawa \
    --ks-pass pass:basajawa123 --key-pass pass:basajawa123 \
    --out "$DIST/$APK_NAME" "$TMP/app.aligned.apk"

echo "==> 8. verify"
"$BT/apksigner" verify --print-certs "$DIST/$APK_NAME" | head -6
$QEMU "$BT/aapt2" dump badging "$DIST/$APK_NAME" | grep -E "^package|^application-label:|^sdkVersion|^targetSdkVersion|launchable-activity"
ls -la "$DIST/$APK_NAME"
echo "BUILD_OK"
du -h "$DIST/$APK_NAME"
