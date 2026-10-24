#!/usr/bin/env bash
set -euo pipefail

FF_VERSION=""
SKIP_INSTALLER="false"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --firefox-version|--version)
            FF_VERSION="$2"
            shift
            ;;
        --skip-installer)
            SKIP_INSTALLER="true"
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
    shift
done

if [ -z "$FF_VERSION" ]; then
    echo "[*] Detecting latest Firefox win64 version from Mozilla API..."
    FF_VERSION=$(curl -fsSL "https://product-details.mozilla.org/1.0/firefox_versions.json" | python3 -c "import sys, json; print(json.load(sys.stdin)['LATEST_FIREFOX_VERSION'])")
fi

echo "========================================================"
echo " Building Seafari for Windows (Firefox $FF_VERSION)"
echo "========================================================"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$ROOT_DIR/build_workspace"
CACHE_DIR="$ROOT_DIR/build_cache_win64"

rm -rf "$WORKSPACE"
mkdir -p "$WORKSPACE" "$CACHE_DIR"

FF_URL="https://download.mozilla.org/?product=firefox-${FF_VERSION}-ssl&os=win64&lang=en-US"
INSTALLER_CACHE="$CACHE_DIR/firefox-${FF_VERSION}-win64.exe"

if [ ! -s "$INSTALLER_CACHE" ]; then
    echo "[*] Downloading Firefox $FF_VERSION (win64) from $FF_URL ..."
    curl -fL --retry 3 -o "$INSTALLER_CACHE.tmp" "$FF_URL"
    mv "$INSTALLER_CACHE.tmp" "$INSTALLER_CACHE"
else
    echo "[*] Using cached Firefox installer: $INSTALLER_CACHE"
fi

UBLOCK_XPI="$CACHE_DIR/ublock_origin.xpi"
if [ ! -s "$UBLOCK_XPI" ]; then
    echo "[*] Downloading uBlock Origin XPI..."
    curl -fL --retry 3 -o "$UBLOCK_XPI" "https://addons.mozilla.org/firefox/downloads/latest/ublock-origin/latest.xpi"
fi

ATBC_XPI="$CACHE_DIR/adaptive_tab_bar_colour.xpi"
if [ ! -s "$ATBC_XPI" ]; then
    echo "[*] Downloading Adaptive Tab Bar Colour XPI..."
    curl -fL --retry 3 -o "$ATBC_XPI" "https://addons.mozilla.org/firefox/downloads/file/4704834/adaptive_tab_bar_colour-3.3.2.xpi"
fi

echo "[*] Extracting Firefox Windows installer with 7z..."
7z x "$INSTALLER_CACHE" -o"$WORKSPACE/extracted" -y >/dev/null

if [ -d "$WORKSPACE/extracted/core" ]; then
    mv "$WORKSPACE/extracted/core" "$WORKSPACE/Seafari"
else
    echo "ERROR: Expected 'core/' directory inside Firefox installer archive!"
    exit 1
fi
rm -rf "$WORKSPACE/extracted"

echo "[*] Applying Seafari UI overlay, omni.ja patches, and Windows adaptations..."
python3 "$ROOT_DIR/scripts/patch_windows_firefox.py" \
    --firefox-dir "$WORKSPACE/Seafari" \
    --ublock-xpi "$UBLOCK_XPI" \
    --atbc-xpi "$ATBC_XPI"

PORTABLE_ZIP="$ROOT_DIR/Seafari-Windows-${FF_VERSION}.zip"
rm -f "$PORTABLE_ZIP"
echo "[*] Creating Portable ZIP archive: $PORTABLE_ZIP ..."
(
    cd "$WORKSPACE"
    7z a -tzip -mx=5 "$PORTABLE_ZIP" "Seafari" >/dev/null
)
echo "[+] Created $PORTABLE_ZIP"

if [ "$SKIP_INSTALLER" != "true" ] && command -v makensis >/dev/null 2>&1; then
    INSTALLER_EXE="$ROOT_DIR/Seafari-Setup-${FF_VERSION}.exe"
    rm -f "$INSTALLER_EXE"
    echo "[*] Building Windows NSIS Installer: $INSTALLER_EXE ..."
    makensis \
        -DVERSION="$FF_VERSION" \
        -DSOURCE_DIR="$WORKSPACE/Seafari" \
        -DOUT_FILE="$INSTALLER_EXE" \
        "$ROOT_DIR/installer/seafari.nsi"
    echo "[+] Created $INSTALLER_EXE"
else
    echo "[!] Skipping NSIS installer build (makensis not installed or --skip-installer set)"
fi

echo "========================================================"
echo " Seafari Windows build complete for v${FF_VERSION}!"
echo "========================================================"
