#!/usr/bin/env python3
"""
Generates clean, comprehensive markdown release notes for Seafari Windows releases.
Includes commit changelog, upstream parity info, feature breakdown, and download table.
Strictly free of emojis.
"""

import os
import subprocess
import sys


def generate_notes(ff_ver, upstream_sha, build_reason, prev_tag=""):
    commits_output = ""
    if prev_tag:
        try:
            log_cmd = [
                "git",
                "log",
                f"{prev_tag}..HEAD",
                '--pretty=format:* %s ([%h](https://github.com/jabirking-ux/seafari-win/commit/%H))',
            ]
            commits_output = subprocess.check_output(log_cmd, stderr=subprocess.DEVNULL, text=True, errors="ignore").strip()
        except Exception:
            pass

    if not commits_output:
        try:
            log_cmd = [
                "git",
                "log",
                "-n",
                "10",
                '--pretty=format:* %s ([%h](https://github.com/jabirking-ux/seafari-win/commit/%H))',
            ]
            commits_output = subprocess.check_output(log_cmd, stderr=subprocess.DEVNULL, text=True, errors="ignore").strip()
        except Exception:
            commits_output = "* Maintenance and stability improvements."

    if not commits_output:
        commits_output = "* Upstream synchronization and stability improvements."

    content = f"""# Seafari for Windows v{ff_ver}

Automated Windows native port of [InledGroup/seafari](https://github.com/InledGroup/seafari) bringing the authentic macOS Safari browsing experience to Windows 10 and 11.

---

### Build and Version Information
- **Firefox Base:** Mozilla Firefox `{ff_ver}` (`win64`)
- **Upstream Commit:** [`{upstream_sha[:10]}`](https://github.com/InledGroup/seafari/commit/{upstream_sha})
- **Build Trigger:** {build_reason}
- **Release Architecture:** x86_64 (Windows 10 / Windows 11)

---

### What is Included and Key Updates
- **Zero-Flash 2-Second Startup Hold**: Synchronous Win32 `WH_CBT` hook intercepts window creation instantly at the OS level (`WS_EX_LAYERED`, `alpha = 0`) before any frames are composited or displayed by DWM, eliminating any window flicker or split-second display before smoothly revealing after 2 seconds.
- **macOS Liquid Glass Drag Animation**: Dynamic OS-level translucency (`alpha = 224`) and inertia tilt lag (`--seafari-drag-dx`, `--seafari-drag-dy`) while dragging the window.
- **Native Taskbar Identity**: Patched Win32 PE resources (`firefox.exe` & `seafari.exe`), dedicated multi-resolution `seafari.ico`, and `AppUserModelID = InledGroup.Seafari` ensuring the Windows Taskbar and Alt+Tab display **Seafari** instead of Firefox.
- **Left-Hand Traffic Light Controls**: Authentic macOS close, minimize, and zoom buttons on the left with coordinated triad hover animations in both Dark and Light modes.
- **Crash Reporter and Telemetry Neutralized**: Disabled `toolkit.crashreporter`, purged crash reporter helper binaries, and prevented crash popups and prompt dialogs.
- **Clean Default Toolbar**: Auto-configured toolbar layout with uBlock Origin active in the background without cluttering the main navigation bar.
- **Upstream 1:1 Parity**: Full synchronization with latest upstream assets (`MacTahoe/`, `tab-overview/`, contrast improvements, and new tab pages).

---

### Changes in this Release
{commits_output}

---

### Downloads and Installation

| Asset | Description |
| :--- | :--- |
| **[`Seafari-Setup-{ff_ver}.exe`](https://github.com/jabirking-ux/seafari-win/releases/download/v{ff_ver}/Seafari-Setup-{ff_ver}.exe)** | **Recommended:** One-click NSIS Windows Installer with Desktop and Start Menu shortcuts. |
| **[`Seafari-Windows-{ff_ver}.zip`](https://github.com/jabirking-ux/seafari-win/releases/download/v{ff_ver}/Seafari-Windows-{ff_ver}.zip)** | **Portable:** Extract anywhere and launch `seafari.exe` or `firefox.exe` directly. |

---
*Built automatically by [GitHub Actions](https://github.com/jabirking-ux/seafari-win/actions).*
"""
    with open("RELEASE_CHANGELOG.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("Generated RELEASE_CHANGELOG.md successfully!")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: generate_release_notes.py <ff_ver> <upstream_sha> <build_reason> [prev_tag]")
        sys.exit(1)
    ff_ver = sys.argv[1]
    upstream_sha = sys.argv[2]
    build_reason = sys.argv[3]
    prev_tag = sys.argv[4] if len(sys.argv) > 4 else ""
    generate_notes(ff_ver, upstream_sha, build_reason, prev_tag)
