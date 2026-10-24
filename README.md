<div align="left">
  <img src="seafari.png" alt="Seafari Logo" width="110" align="left" style="margin-right: 20px;">
  <h1>Seafari for Windows</h1>
</div>

**Seafari for Windows** is an automated Windows port of [InledGroup/seafari](https://github.com/InledGroup/seafari) — a Safari-styled browser built on top of Mozilla Firefox.

It automatically tracks both **Mozilla's latest Windows (`win64`) Firefox releases** and **upstream [InledGroup/seafari](https://github.com/InledGroup/seafari) commits** daily via GitHub Actions, patching `omni.ja` and `browser/omni.ja` on `ubuntu-latest` runners and publishing both a **Windows Installer (`.exe`)** and a **Portable Archive (`.zip`)**.

<p align="center">
  <img src="demo-seafari-v2.6.gif" alt="Seafari demo" width="85%">
</p>

<p align="center">
  <img src="demo.png" alt="Seafari demo" width="55%">
</p>

---

## Features

- **Safari / macOS Tahoe Liquid Glass UI**: Pill-grouped navigation toolbar, centered tabs below the address bar, macOS traffic-light window controls adapted for Windows, and smooth scroll auto-hiding toolbox.
- **Built-in Extensions**:
  - **uBlock Origin** (patched to integrate blocked tracker statistics directly into the Safari New Tab Page and relocated into the URL bar).
  - **Adaptive Tab Bar Colour (ATBC)** for dynamic page-matched toolbar coloring.
  - **Seafari Tab Overview & Start Page** (`tab-overview@seafari.org`) with Favorites, Reading List, Privacy Report, and custom background video support.
- **Zero-Wrapper Native Launch**: `seafari.cfg` (Firefox AutoConfig) automatically syncs `seafari-theme/` into the active profile's `chrome/` folder and registers `userChrome.css` and `userContent.css` via `nsIStyleSheetService` on first launch.
- **Daily Auto-Updates & Upstream Sync**: Automatically rebuilds whenever Mozilla releases a new Firefox `win64` version or upstream `InledGroup/seafari` pushes new UI updates.

---

## Repository Structure

```text
seafari-win/
├── .github/workflows/
│   └── build.yml               # Daily auto-update & release pipeline (runs on ubuntu-latest)
├── chrome/                     # Safari-styled UI assets & omni.ja overlay tree
│   ├── browser/                # Files overlaid into browser/omni.ja
│   │   ├── content/branding/   # Seafari icons, wordmarks, and about dialog assets
│   │   ├── content/browser/    # Browser XHTML/MJS overrides
│   │   ├── locale/en-US/       # Brand locale strings (brand.properties, brand.dtd, brand.ftl)
│   │   └── skin/classic/       # Browser skin overrides
│   ├── gre/                    # Files overlaid into root omni.ja (toolkit global.css / aboutNetError.css)
│   ├── MacTahoe/               # Safari / macOS Tahoe theme stylesheets & icons
│   ├── windows-fixes.css       # Windows-specific caption button & flexbox adaptations
│   ├── userChrome.css          # Chrome UI entry stylesheet
│   ├── userContent.css         # In-content pages stylesheet
│   └── customChrome.css        # Liquid glass pill wrappers & adaptive icon rules
├── installer/
│   └── seafari.nsi             # NSIS script for building Seafari-Setup-{VERSION}.exe
├── scripts/
│   ├── init_chrome_tree.py     # Generates seafari.ico and populates chrome/ overlay tree
│   ├── patch_windows_firefox.py# Unpacks omni.ja, overlays Safari UI, configures AutoConfig & extensions
│   └── sync_upstream.py        # Pulls latest commits from upstream InledGroup/seafari
├── MacTahoe/                   # Upstream MacTahoe theme directory
├── tab-overview/               # Built-in Seafari Start Page & Tab Overview WebExtension
├── build_seafari_win.sh        # Automated Windows build script (runs on Linux/WSL/Git Bash)
├── last_version.txt            # Last built Firefox win64 version (for idempotent CI runs)
└── README.md
```

---

## Building Locally

### On Ubuntu / Debian / WSL

1. Install dependencies:
   ```bash
   sudo apt-get update
   sudo apt-get install -y p7zip-full nsis zip unzip curl jq python3
   ```

2. Sync latest upstream changes (optional):
   ```bash
   python3 scripts/sync_upstream.py
   ```

3. Build Portable ZIP and NSIS Installer EXE:
   ```bash
   chmod +x build_seafari_win.sh
   ./build_seafari_win.sh
   ```

### On Windows (PowerShell + Python + 7-Zip)

```powershell
# Sync upstream assets
python scripts\sync_upstream.py

# Patch an extracted Firefox win64 'core/' directory
python scripts\patch_windows_firefox.py `
  --firefox-dir path\to\extracted\core `
  --ublock-xpi path\to\ublock_origin.xpi `
  --atbc-xpi path\to\adaptive_tab_bar_colour.xpi
```

---

## License & Acknowledgments

- Upstream project by **Inled Group**: [InledGroup/seafari](https://github.com/InledGroup/seafari)
- Based on **Mozilla Firefox** (MPL-2.0) and [Vinceliuice/MacTahoe-gtk-theme](https://github.com/vinceliuice/MacTahoe-gtk-theme)
