#!/usr/bin/env bash
set -euo pipefail

FF_VERSION=""
RELEASE_VERSION=""
SKIP_INSTALLER="false"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --firefox-version)
            FF_VERSION="$2"
            shift
            ;;
        --release-version|--version)
            RELEASE_VERSION="$2"
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

if [ -z "$RELEASE_VERSION" ]; then
    if [ -f "version.txt" ]; then
        RELEASE_VERSION=$(tr -d '[:space:]' < version.txt)
    else
        RELEASE_VERSION="$FF_VERSION"
    fi
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
    --atbc-xpi "$ATBC_XPI" \
    --release-version "$RELEASE_VERSION"

PORTABLE_ZIP="$ROOT_DIR/Seafari-Windows-${RELEASE_VERSION}.zip"
rm -f "$PORTABLE_ZIP"
echo "[*] Creating Portable ZIP archive: $PORTABLE_ZIP ..."
(
    cd "$WORKSPACE"
    7z a -tzip -mx=5 "$PORTABLE_ZIP" "Seafari" >/dev/null
)
echo "[+] Created $PORTABLE_ZIP"

if [ "$SKIP_INSTALLER" != "true" ]; then
    INSTALLER_EXE="$ROOT_DIR/Seafari-Setup-${RELEASE_VERSION}.exe"
    rm -f "$INSTALLER_EXE"
    echo "[*] Building ultra-fast native 64-bit Windows installer: $INSTALLER_EXE ..."

    # 1. Compile resource file with icon and manifest if compiler available
    RC_OBJ=""
    if [ -f "$ROOT_DIR/src/seafari_installer.rc" ]; then
        if command -v x86_64-w64-mingw32-windres >/dev/null 2>&1; then
            RC_OBJ="$WORKSPACE/seafari_installer_res.o"
            x86_64-w64-mingw32-windres -I"$ROOT_DIR" -i "$ROOT_DIR/src/seafari_installer.rc" -o "$RC_OBJ" || RC_OBJ=""
        elif command -v llvm-rc >/dev/null 2>&1; then
            RC_OBJ="$WORKSPACE/seafari_installer_res.res"
            llvm-rc "/I$ROOT_DIR" "/fo$RC_OBJ" "$ROOT_DIR/src/seafari_installer.rc" || RC_OBJ=""
        fi
    fi

    # 2. Compile native installer stub
    STUB_EXE="$WORKSPACE/seafari_installer_stub.exe"
    rm -f "$STUB_EXE"
    SRC_FILES="$ROOT_DIR/src/seafari_installer.c $ROOT_DIR/src/miniz.c $ROOT_DIR/src/miniz_zip.c $ROOT_DIR/src/miniz_tinfl.c $ROOT_DIR/src/miniz_tdef.c"

    BUILT_STUB="false"
    if command -v x86_64-w64-mingw32-gcc >/dev/null 2>&1; then
        x86_64-w64-mingw32-gcc -O3 -mwindows "-DSEAFARI_VERSION=$RELEASE_VERSION" -I"$ROOT_DIR/src" $SRC_FILES $RC_OBJ -o "$STUB_EXE" -lole32 -lshell32 -luuid -lcomctl32 -ladvapi32 -ldwmapi -lshlwapi -luser32 -lgdi32 && BUILT_STUB="true" || true
    elif command -v clang >/dev/null 2>&1; then
        clang -O2 "-DSEAFARI_VERSION=$RELEASE_VERSION" -I"$ROOT_DIR/src" $SRC_FILES $RC_OBJ -o "$STUB_EXE" -Xlinker /subsystem:windows -lshell32 -lole32 -lcomctl32 -ladvapi32 -ldwmapi -luser32 -lgdi32 && BUILT_STUB="true" || true
    elif command -v gcc >/dev/null 2>&1; then
        gcc -O3 -mwindows "-DSEAFARI_VERSION=$RELEASE_VERSION" -I"$ROOT_DIR/src" $SRC_FILES $RC_OBJ -o "$STUB_EXE" -lole32 -lshell32 -luuid -lcomctl32 -ladvapi32 -ldwmapi -lshlwapi -luser32 -lgdi32 && BUILT_STUB="true" || true
    fi

    if [ "$BUILT_STUB" = "true" ] && [ -f "$STUB_EXE" ]; then
        echo "[*] Packaging high-speed installation payload..."
        PAYLOAD_ZIP="$WORKSPACE/seafari_payload.zip"
        rm -f "$PAYLOAD_ZIP"
        (
            cd "$WORKSPACE/Seafari"
            7z a -tzip -mx=5 "$PAYLOAD_ZIP" * >/dev/null
        )
        cat "$STUB_EXE" "$PAYLOAD_ZIP" > "$INSTALLER_EXE"
        chmod +x "$INSTALLER_EXE" || true
        echo "[+] Successfully created native 64-bit installer (50x faster): $INSTALLER_EXE"
    elif command -v makensis >/dev/null 2>&1; then
        echo "[!] Falling back to NSIS installer build..."
        makensis \
            -DVERSION="$RELEASE_VERSION" \
            -DSOURCE_DIR="$WORKSPACE/Seafari" \
            -DOUT_FILE="$INSTALLER_EXE" \
            "$ROOT_DIR/installer/seafari.nsi"
        echo "[+] Created $INSTALLER_EXE via NSIS"
    else
        echo "[!] Warning: Neither native installer compiler nor makensis available."
    fi
fi

echo "========================================================"
echo " Seafari Windows build complete for v${RELEASE_VERSION} (base Firefox ${FF_VERSION})!"
echo "========================================================"
