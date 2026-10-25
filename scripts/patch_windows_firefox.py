#!/usr/bin/env python3
"""
Patches an extracted Windows Firefox directory (core/) into Seafari for Windows.
Works on both Linux (ubuntu-latest GitHub Actions runner) and Windows.
"""
import argparse
import base64
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

from init_chrome_tree import encode_png_paeth, make_ico_dib, read_png_rgba, resize_rgba


TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

UBLOCK_LISTENER_JS = """
// Seafari NTP integration listener
if (typeof browser !== 'undefined' && browser.runtime && browser.runtime.onMessageExternal) {
  browser.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
    if (sender.id === "tab-overview@seafari.org") {
      if (message && message.action === "getUblockStats") {
        var totalBlocked = 0;
        try {
          var ub = typeof µBlock !== 'undefined' ? µBlock : (typeof µb !== 'undefined' ? µb : (typeof uBlock0 !== 'undefined' ? uBlock0 : (typeof uBlock !== 'undefined' ? uBlock : null)));
          if (ub) {
            if (ub.requestStats && typeof ub.requestStats.blockedCount === "number") {
              totalBlocked = ub.requestStats.blockedCount;
            } else if (ub.stats && typeof ub.stats.blocked === "number") {
              totalBlocked = ub.stats.blocked;
            } else if (ub.localSettings && typeof ub.localSettings.blockedRequestCount === "number") {
              totalBlocked = ub.localSettings.blockedRequestCount;
            } else if (typeof ub.blockedRequestCount === "number") {
              totalBlocked = ub.blockedRequestCount;
            }
          }
        } catch(e) {
          totalBlocked = -1;
        }
        sendResponse({ totalBlocked: totalBlocked });
        return true;
      }
    }
    return false;
  });
}
"""

USERCONTENT_APPEND_CSS = """
@-moz-document url-prefix("about:welcome") {
    .section-secondary, .hero-image, .onboarding-hero-image, .page-header-image, .welcome-image, .fox-image, .illustration, .brand-logo, .logo-container {
        display: none !important;
    }
    .onboardingContainer {
        background: #1a1a1a !important;
        background-image: none !important;
    }
    .screen {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        background: transparent !important;
    }
    .section-main {
        width: 100% !important;
        max-width: 800px !important;
        margin: 0 auto !important;
        background: #1a1a1a !important;
        color: #ffffff !important;
        border-radius: 16px !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
    }
    .main-content {
        max-width: 100% !important;
        margin: 0 !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        background-color: transparent !important;
    }
    .onboardingContainer h1, .onboardingContainer h2, .onboardingContainer p, .onboardingContainer span, .onboardingContainer label { color: white !important; }
}
@-moz-document url("about:home"), url("about:newtab") {
    body { background-color: #1a1a1a !important; }
    .activity-stream { background: transparent !important; }
    .search-wrapper, .wordmark { display: none !important; }

    .logo-and-wordmark {
        display: flex !important;
        justify-content: center !important;
        margin-top: 60px !important;
        margin-bottom: 20px !important;
    }
    .logo {
        background: url("seafari.png") no-repeat center !important;
        background-size: contain !important;
        width: 120px !important;
        height: 120px !important;
        display: block !important;
    }

    /* Titles */
    .section-title span { visibility: hidden !important; }
    .section-title span::before { visibility: visible !important; font-weight: 600 !important; font-size: 24px !important; color: white !important; }

    .top-sites .section-title span::before { content: "Favorites" !important; }
    .highlights .section-title span::before { content: "Frequently Visited" !important; }

    /* Top Sites (Favorites) */
    .top-site-outer .tile {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        backdrop-filter: blur(10px) !important;
        width: 70px !important;
        height: 70px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important;
    }
    .top-site-outer .title { color: white !important; font-weight: 500 !important; margin-top: 8px !important; }

    /* Highlights (Frequently Visited) */
    .highlights .card-outer {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 16px !important;
        overflow: hidden !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        transition: transform 0.2s !important;
    }
    .highlights .card-outer:hover { transform: scale(1.02) !important; background: rgba(255, 255, 255, 0.08) !important; }
    .highlights .card-preview-image-outer { height: 120px !important; }
    .highlights .card-title { color: white !important; padding: 10px !important; }
    .highlights .card-context { display: none !important; }
}
@-moz-document url-prefix("about:") { .brand-logo, .logo { background: url("seafari.png") no-repeat center !important; background-size: contain !important; } }

@-moz-document url-prefix("about:preferences") {
    #policies-container,
    #policies-container-content,
    .enterprise-controlled,
    .managed-box,
    #managed-box,
    #updateSettingsContainer .box-container,
    #updateApp .box-container,
    .box-container:has(span[id="label"]),
    .box-container:has(slot[name="actions-start"]) {
        display: none !important;
    }
}
"""

NEWTAB_REDIRECT_JS = """try {
  var prefURL = '';
  if (typeof Services !== 'undefined' && Services.prefs) {
    prefURL = Services.prefs.getStringPref('browser.newtabpage.url');
  } else {
    var prefService = Components.classes['@mozilla.org/preferences-service;1'].getService(Components.interfaces.nsIPrefBranch);
    prefURL = prefService.getCharPref('browser.newtabpage.url');
  }
  if (prefURL && prefURL.startsWith('moz-extension://')) {
    window.location.replace(prefURL);
  }
} catch(e) {}
"""

ONBOARDING_BYPASS_PREFS_JS = """
// Seafari: Suppress Firefox 158+ Terms of Use / Spotlight / AboutWelcome modals and Nova visual overrides
pref("termsofuse.bypassNotification", true);
pref("termsofuse.acceptedVersion", 999);
pref("termsofuse.acceptedDate", "1700000000000");
pref("termsofuse.firstAcceptedDate", "1700000000000");
pref("browser.aboutwelcome.enabled", false);
pref("browser.nova.enabled", false);
pref("browser.newtabpage.activity-stream.nova.enabled", false);
pref("toolkit.crashreporter.enabled", false);
pref("breakpad.reportURL", "");
pref("browser.tabs.crashReporting.sendReport", false);
pref("browser.crashReports.unsubmittedCheck.enabled", false);
pref("browser.crashReports.unsubmittedCheck.autoSubmit2", false);
pref("datareporting.healthreport.uploadEnabled", false);
pref("datareporting.policy.dataSubmissionEnabled", false);
pref("toolkit.startup.max_resumed_crashes", -1);
pref("browser.sessionstore.resume_from_crash", false);
pref("browser.sessionstore.max_resumed_crashes", -1);
pref("browser.sessionstore.interval", 60000);
pref("browser.tabs.unloadOnLowMemory", true);
pref("gfx.webrender.all", true);
pref("gfx.webrender.pre-cache-shaders", true);
pref("gfx.canvas.accelerated", true);
pref("layers.gpu-process.enabled", true);
pref("network.http.http3.enable", true);
pref("network.ssl_tokens_cache_capacity", 2048);
pref("network.http.max-connections", 900);
pref("network.http.max-persistent-connections-per-server", 8);
pref("network.http.pacing.requests.enabled", false);
pref("network.http.speculative-parallel-limit", 0);
pref("content.notify.interval", 100000);
pref("content.notify.ontimer", true);
pref("image.mem.decode_bytes_at_a_time", 65536);
pref("browser.sessionhistory.max_entries", 15);
pref("browser.sessionhistory.max_total_viewers", 3);
pref("browser.cache.memory.enable", true);
pref("browser.cache.memory.capacity", 524288);
pref("browser.cache.disk.enable", true);
pref("media.autoplay.default", 5);
pref("media.memory_cache_max_size", 65536);
pref("javascript.options.mem.gc_incremental_slice_ms", 10);
pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
pref("datareporting.policy.firstRunURL", "");
pref("browser.messaging-system.whatsNewPanel.enabled", false);
pref("browser.uitour.enabled", false);
pref("browser.promo.focus.enabled", false);
pref("widget.windows.mica", false);
pref("xpinstall.signatures.required", false);
"""


def find_7z():
    for candidate in [
        shutil.which("7z"),
        shutil.which("7za"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        r"C:\Program Files (x86)\AOMEI Partition Assistant\7z.exe",
    ]:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def patch_ublock_xpi(src_xpi, dst_xpi):
    print(f"[*] Patching uBlock Origin XPI -> {dst_xpi}")
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(src_xpi, "r") as zf:
            zf.extractall(tmpdir)

        manifest_path = os.path.join(tmpdir, "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["externally_connectable"] = {"ids": ["tab-overview@seafari.org"]}
            if "browser_action" in data and isinstance(data["browser_action"], dict):
                data["browser_action"]["default_area"] = "menupanel"
            if "action" in data and isinstance(data["action"], dict):
                data["action"]["default_area"] = "menupanel"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        bg_js = os.path.join(tmpdir, "js", "background.js")
        if os.path.exists(bg_js):
            with open(bg_js, "a", encoding="utf-8") as f:
                f.write(UBLOCK_LISTENER_JS)

        with zipfile.ZipFile(dst_xpi, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_dir, _, files in os.walk(tmpdir):
                for file in files:
                    full_path = os.path.join(root_dir, file)
                    rel_path = os.path.relpath(full_path, tmpdir).replace("\\", "/")
                    zf.write(full_path, rel_path)


def extract_seafari_cfg_from_linux_script(linux_script_path):
    """Extracts the seafari.cfg template from build_seafari_linux.sh and injects Windows enhancements."""
    with open(linux_script_path, "r", encoding="utf-8") as f:
        script = f.read()

    m = re.search(
        r'cat <<EOF > "\$FIREFOX_DIR/seafari\.cfg"\n(.*?)\nEOF\n\necho "Preparing Theme Folder\.\.\."',
        script,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("Could not locate seafari.cfg block in build_seafari_linux.sh")

    cfg = m.group(1)
    # Replace bash $UA_LINE placeholder with Windows & onboarding bypass prefs
    extra_prefs = (
        'pref("widget.windows.mica", false);\n'
        '  pref("xpinstall.signatures.required", false);\n'
        '  pref("termsofuse.bypassNotification", true);\n'
        '  pref("termsofuse.acceptedVersion", 999);\n'
        '  pref("termsofuse.acceptedDate", "1700000000000");\n'
        '  pref("termsofuse.firstAcceptedDate", "1700000000000");\n'
        '  pref("browser.aboutwelcome.enabled", false);\n'
        '  pref("browser.nova.enabled", false);\n'
        '  pref("browser.newtabpage.activity-stream.nova.enabled", false);\n'
        '  pref("toolkit.crashreporter.enabled", false);\n'
        '  pref("breakpad.reportURL", "");\n'
        '  pref("browser.tabs.crashReporting.sendReport", false);\n'
        '  pref("browser.crashReports.unsubmittedCheck.enabled", false);\n'
        '  pref("browser.crashReports.unsubmittedCheck.autoSubmit2", false);\n'
        '  pref("datareporting.healthreport.uploadEnabled", false);\n'
        '  pref("datareporting.policy.dataSubmissionEnabled", false);\n'
        '  pref("toolkit.startup.max_resumed_crashes", -1);\n'
        '  pref("browser.sessionstore.resume_from_crash", false);\n'
        '  pref("browser.sessionstore.max_resumed_crashes", -1);\n'
        '  pref("browser.sessionstore.interval", 60000);\n'
        '  pref("browser.tabs.unloadOnLowMemory", true);\n'
        '  pref("gfx.webrender.all", true);\n'
        '  pref("gfx.webrender.pre-cache-shaders", true);\n'
        '  pref("gfx.canvas.accelerated", true);\n'
        '  pref("layers.gpu-process.enabled", true);\n'
        '  pref("network.http.http3.enable", true);\n'
        '  pref("network.ssl_tokens_cache_capacity", 2048);\n'
        '  pref("network.http.max-connections", 900);\n'
        '  pref("network.http.max-persistent-connections-per-server", 8);\n'
        '  pref("network.http.pacing.requests.enabled", false);\n'
        '  pref("network.http.speculative-parallel-limit", 0);\n'
        '  pref("content.notify.interval", 100000);\n'
        '  pref("content.notify.ontimer", true);\n'
        '  pref("image.mem.decode_bytes_at_a_time", 65536);\n'
        '  pref("browser.sessionhistory.max_entries", 15);\n'
        '  pref("browser.sessionhistory.max_total_viewers", 3);\n'
        '  pref("browser.cache.memory.enable", true);\n'
        '  pref("browser.cache.memory.capacity", 524288);\n'
        '  pref("browser.cache.disk.enable", true);\n'
        '  pref("media.autoplay.default", 5);\n'
        '  pref("media.memory_cache_max_size", 65536);\n'
        '  pref("javascript.options.mem.gc_incremental_slice_ms", 10);\n'
        '  pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);\n'
        '  pref("datareporting.policy.firstRunURL", "");'
    )
    cfg = cfg.replace("$UA_LINE", extra_prefs)

    # Fix upstream XPCOM contract ID bug for nsIFileOutputStream
    cfg = cfg.replace("@mozilla.org/file/output-stream;1", "@mozilla.org/network/file-output-stream;1")

    # Inject Windows profile theme auto-sync & immediate nsIStyleSheetService registration right after log("Seafari Autoconfig initialization started");
    profile_sync_js = """
try {
  // Set explicit AppUserModelID on Windows shell for taskbar identification & grouping
  var { ctypes } = ChromeUtils.importESModule("resource://gre/modules/ctypes.sys.mjs");
  var shell32 = ctypes.open("shell32.dll");
  var SetCurrentProcessExplicitAppUserModelIDFn = shell32.declare(
    "SetCurrentProcessExplicitAppUserModelID",
    ctypes.winapi_abi,
    ctypes.long,
    ctypes.jschar.ptr
  );
  SetCurrentProcessExplicitAppUserModelIDFn("InledGroup.Seafari");
  log("Explicit AppUserModelID set to InledGroup.Seafari");
} catch (aumidErr) {
  log("AppUserModelID init error: " + aumidErr);
}

try {
  // Ensure onboarding/Terms-of-Use/Nova prefs are set on the user branch too
  var pb = Components.classes["@mozilla.org/preferences-service;1"]
                     .getService(Components.interfaces.nsIPrefBranch);
  pb.setBoolPref("termsofuse.bypassNotification", true);
  pb.setIntPref("termsofuse.acceptedVersion", 999);
  pb.setCharPref("termsofuse.acceptedDate", "1700000000000");
  pb.setCharPref("termsofuse.firstAcceptedDate", "1700000000000");
  pb.setBoolPref("browser.aboutwelcome.enabled", false);
  pb.setBoolPref("browser.nova.enabled", false);
  pb.setBoolPref("browser.newtabpage.activity-stream.nova.enabled", false);
  pb.setBoolPref("toolkit.crashreporter.enabled", false);
  pb.setCharPref("breakpad.reportURL", "");
  pb.setBoolPref("browser.tabs.crashReporting.sendReport", false);
  pb.setBoolPref("browser.crashReports.unsubmittedCheck.enabled", false);
  pb.setBoolPref("browser.crashReports.unsubmittedCheck.autoSubmit2", false);
  pb.setBoolPref("datareporting.healthreport.uploadEnabled", false);
  pb.setBoolPref("datareporting.policy.dataSubmissionEnabled", false);
  pb.setIntPref("toolkit.startup.max_resumed_crashes", -1);
  pb.setBoolPref("browser.sessionstore.resume_from_crash", false);
  pb.setIntPref("browser.sessionstore.max_resumed_crashes", -1);
  pb.setBoolPref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
} catch (prefErr) {}

try {
  // Automatically sync GreD/seafari-theme into ProfD/chrome on Windows/Linux
  // so launching firefox.exe or seafari.exe directly always has the Safari UI.
  var greDir = Components.classes["@mozilla.org/file/directory_service;1"]
                         .getService(Components.interfaces.nsIProperties)
                         .get("GreD", Components.interfaces.nsIFile);
  var themeSrc = greDir.clone();
  themeSrc.append("seafari-theme");
  var profDir = Components.classes["@mozilla.org/file/directory_service;1"]
                          .getService(Components.interfaces.nsIProperties)
                          .get("ProfD", Components.interfaces.nsIFile);
  var chromeDst = profDir.clone();
  chromeDst.append("chrome");

  function copyDirRecursive(srcDir, dstDir) {
    if (!dstDir.exists()) {
      dstDir.create(Components.interfaces.nsIFile.DIRECTORY_TYPE, 493); // 0755
    }
    var entries = srcDir.directoryEntries;
    while (entries.hasMoreElements()) {
      var entry = entries.getNext().QueryInterface(Components.interfaces.nsIFile);
      var target = dstDir.clone();
      target.append(entry.leafName);
      if (entry.isDirectory()) {
        copyDirRecursive(entry, target);
      } else {
        try {
          var isCss = entry.leafName.endsWith(".css");
          if (isCss || !target.exists() || target.fileSize !== entry.fileSize || target.lastModifiedTime < entry.lastModifiedTime) {
            if (target.exists()) target.remove(false);
            entry.copyTo(dstDir, entry.leafName);
          }
        } catch (copyErr) {}
      }
    }
  }

  if (themeSrc.exists() && themeSrc.isDirectory()) {
    copyDirRecursive(themeSrc, chromeDst);
    log("Synced seafari-theme to profile chrome directory: " + chromeDst.path);
  }

  // Register userChrome.css, windows-fixes.css, and userContent.css immediately via nsIStyleSheetService
  // and invalidate startupCache so updated styles are always active on first launch.
  try {
    var obsSvc = Components.classes["@mozilla.org/observer-service;1"]
                           .getService(Components.interfaces.nsIObserverService);
    obsSvc.notifyObservers(null, "startupcache-invalidate", null);
  } catch (cacheErr) {}

  var sss = Components.classes["@mozilla.org/content/style-sheet-service;1"]
                      .getService(Components.interfaces.nsIStyleSheetService);
  var ioSvc = Components.classes["@mozilla.org/network/io-service;1"]
                        .getService(Components.interfaces.nsIIOService);
  ["userChrome.css", "windows-fixes.css", "userContent.css"].forEach(function(cssName) {
    try {
      var cssFile = chromeDst.clone();
      cssFile.append(cssName);
      if (cssFile.exists()) {
        var cssURI = ioSvc.newFileURI(cssFile);
        if (sss.sheetRegistered(cssURI, sss.USER_SHEET)) {
          sss.unregisterSheet(cssURI, sss.USER_SHEET);
        }
        sss.loadAndRegisterSheet(cssURI, sss.USER_SHEET);
        log("Registered " + cssName + " via nsIStyleSheetService");
      }
    } catch (cssErr) {
      log("Error registering " + cssName + ": " + cssErr);
    }
  });
} catch (syncErr) {
  log("Profile theme sync error: " + syncErr);
}
"""
    cfg = cfg.replace(
        'log("Seafari Autoconfig initialization started");',
        'log("Seafari Autoconfig initialization started");\n' + profile_sync_js,
        1,
    )

    cfg = cfg.replace(
        '    function relocateUblockBtn(node) {\n      if (!node) return;',
        '    function relocateUblockBtn(node) {\n      try {\n        if (window.CustomizableUI) {\n          window.CustomizableUI.removeWidgetFromArea("ublock0_raymondhill_net-browser-action");\n        }\n      } catch(e) {}\n      if (node) {\n        try {\n          node.style.setProperty("display", "none", "important");\n          node.setAttribute("hidden", "true");\n        } catch(e) {}\n      }\n      return;',
    )
    cfg = cfg.replace(
        'var knownSkipIds  = ["urlbar-container", "stop-reload-button",\n                         "sidebar-button", "developer-button",\n                         "fxa-toolbar-button", "unified-extensions-button"];',
        'var knownSkipIds  = ["urlbar-container", "stop-reload-button",\n                         "sidebar-button", "developer-button",\n                         "fxa-toolbar-button", "fxa-toolbar-menu-button", "unified-extensions-button", "vertical-spacer"];',
    )
    cfg = cfg.replace(
        'var fxaNode = findNode("fxa-toolbar-button");',
        'var fxaNode = findNode("fxa-toolbar-button") || findNode("fxa-toolbar-menu-button");',
    )
    cfg = cfg.replace(
        'Array.from(navBar.children).forEach(function(node) {\n      var id = node.id || "";',
        'Array.from(navBar.children).forEach(function(node) {\n      if (node.localName === "toolbarspring" || node.localName === "toolbartabstop") { try { node.style.setProperty("display", "none", "important"); } catch(e) {} return; }\n      var id = node.id || "";\n      if (id.indexOf("ublock") !== -1 || id.indexOf("uBlock") !== -1) { relocateUblockBtn(node); return; }',
    )

    # Inject Windows taskbar grouping & document title
    window_move_js = """
      // --- Windows AppUserModelID & Taskbar Grouping ---
      try {
        var winTaskbar = Components.classes["@mozilla.org/windows-taskbar;1"]
                                   .getService(Components.interfaces.nsIWinTaskbar);
        if (winTaskbar) {
          winTaskbar.defaultGroupId = "InledGroup.Seafari";
          winTaskbar.setGroupIdForWindow(win, "InledGroup.Seafari");
        }
      } catch (tbErr) {}

      // Ensure window document title never says Firefox
      try {
        if (doc && doc.title && doc.title.indexOf("Firefox") !== -1) {
          doc.title = doc.title.replace(/Mozilla Firefox/g, "Seafari").replace(/Firefox/g, "Seafari");
        }
      } catch (titleErr) {}

      // --- Inject Guaranteed Runtime macOS Window Animations Style ---
      try {
        if (!doc.getElementById("seafari-macos-window-fx")) {
          var fxStyle = doc.createElementNS("http://www.w3.org/1999/xhtml", "style");
          fxStyle.id = "seafari-macos-window-fx";
          fxStyle.textContent = [
            ":root { --seafari-drag-dx: 0px; --seafari-drag-dy: 0px; }",
            "@keyframes macosWindowZoom {",
            "  0% { opacity: 0; transform: scale(0.86) translateY(24px); filter: blur(6px); }",
            "  68% { opacity: 1; transform: scale(1.014) translateY(-2px); filter: blur(0px); }",
            "  100% { opacity: 1; transform: scale(1) translateY(0px); filter: blur(0px); }",
            "}",
            "@keyframes macosGenieMinimize {",
            "  0% { transform: perspective(900px) rotateX(0deg) scale(1, 1) translateY(0%); clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%); opacity: 1; filter: blur(0px); }",
            "  28% { transform: perspective(900px) rotateX(-8deg) scale(0.88, 0.78) translateY(14%); clip-path: polygon(3% 0%, 97% 0%, 78% 100%, 22% 100%); opacity: 0.96; filter: blur(0.5px); }",
            "  62% { transform: perspective(900px) rotateX(-16deg) scale(0.54, 0.38) translateY(48%); clip-path: polygon(14% 0%, 86% 0%, 62% 100%, 38% 100%); opacity: 0.82; filter: blur(1.5px); }",
            "  100% { transform: perspective(900px) rotateX(-24deg) scale(0.14, 0.04) translateY(96%); clip-path: polygon(42% 0%, 58% 0%, 52% 100%, 48% 100%); opacity: 0; filter: blur(4px); }",
            "}",
            "@keyframes macosGenieRestore {",
            "  0% { transform: perspective(900px) rotateX(-24deg) scale(0.14, 0.04) translateY(96%); clip-path: polygon(42% 0%, 58% 0%, 52% 100%, 48% 100%); opacity: 0; filter: blur(4px); }",
            "  36% { transform: perspective(900px) rotateX(-14deg) scale(0.54, 0.38) translateY(46%); clip-path: polygon(14% 0%, 86% 0%, 62% 100%, 38% 100%); opacity: 0.84; filter: blur(1.2px); }",
            "  72% { transform: perspective(900px) rotateX(-4deg) scale(0.92, 0.84) translateY(10%); clip-path: polygon(3% 0%, 97% 0%, 82% 100%, 18% 100%); opacity: 0.98; filter: blur(0px); }",
            "  100% { transform: perspective(900px) rotateX(0deg) scale(1, 1) translateY(0%); clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%); opacity: 1; filter: blur(0px); }",
            "}",
            ":root[seafari-launch-zoom-init='true'] #navigator-toolbox, :root[seafari-launch-zoom-init='true'] #browser { opacity: 0 !important; transform: scale(0.86) translateY(24px) !important; }",
            ":root[seafari-launch-zoom-active='true'] #navigator-toolbox, :root[seafari-launch-zoom-active='true'] #browser, :root[seafari-zoom-toggle='true'] #navigator-toolbox, :root[seafari-zoom-toggle='true'] #browser { animation: macosWindowZoom 0.52s cubic-bezier(0.16, 1, 0.3, 1) forwards !important; transform-origin: center center !important; }",
            ":root[seafari-genie-minimizing='true'] #navigator-toolbox, :root[seafari-genie-minimizing='true'] #browser { animation: macosGenieMinimize 0.38s cubic-bezier(0.32, 0, 0.67, 0) forwards !important; transform-origin: center bottom !important; pointer-events: none !important; }",
            ":root[seafari-genie-restoring='true'] #navigator-toolbox, :root[seafari-genie-restoring='true'] #browser { animation: macosGenieRestore 0.42s cubic-bezier(0.16, 1, 0.3, 1) forwards !important; transform-origin: center bottom !important; }",
            "#navigator-toolbox, #browser, #tabbrowser-tabbox { transition: transform 260ms cubic-bezier(0.22, 1, 0.36, 1), opacity 220ms cubic-bezier(0.22, 1, 0.36, 1), filter 220ms cubic-bezier(0.22, 1, 0.36, 1), border-radius 260ms cubic-bezier(0.22, 1, 0.36, 1), box-shadow 260ms cubic-bezier(0.22, 1, 0.36, 1) !important; transform-origin: center top !important; }",
            ":root[seafari-window-moving='true'] #navigator-toolbox { background-color: color-mix(in srgb, var(--gnome-toolbar-background, #1e1e1e) 68%, transparent) !important; backdrop-filter: blur(28px) saturate(190%) !important; box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28), 0 10px 30px rgba(0, 0, 0, 0.24) !important; }",
            ":root[seafari-window-moving='true'] #nav-bar hbox[seafari-pill] { background: color-mix(in srgb, var(--toolbar-color, currentColor) 15%, transparent) !important; backdrop-filter: blur(24px) saturate(185%) !important; box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.38), 0 6px 18px rgba(0, 0, 0, 0.20) !important; transform: translate3d(calc(var(--seafari-drag-dx, 0px) * -0.22), calc(var(--seafari-drag-dy, 0px) * -0.22), 0) scale(1.015) !important; transition: transform 90ms linear, box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1) !important; }",
            ":root[seafari-window-moving='true'] #browser { transform: scale(0.984) translate3d(calc(var(--seafari-drag-dx, 0px) * -0.42), calc(var(--seafari-drag-dy, 0px) * -0.42), 0) !important; opacity: 0.92 !important; filter: saturate(1.15) brightness(1.02) !important; border-radius: 14px !important; box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.20), 0 20px 48px rgba(0, 0, 0, 0.38) !important; overflow: hidden !important; transition: transform 90ms linear, border-radius 180ms ease, box-shadow 180ms ease, opacity 180ms ease !important; }"
          ].join("\\n");
          doc.documentElement.appendChild(fxStyle);
        }
      } catch (styleErr) {}

      // --- 1. macOS Window Zoom Launch & Green Zoom Button Animation ---
      function playMacOSZoom(durationMs) {
        try {
          var dur = durationMs || 520;
          var rootEl = doc.documentElement;
          rootEl.removeAttribute("seafari-launch-zoom-init");
          rootEl.setAttribute("seafari-launch-zoom-active", "true");
          var targets = [doc.getElementById("navigator-toolbox"), doc.getElementById("browser")];
          targets.forEach(function(el) {
            if (el && typeof el.animate === "function") {
              el.animate([
                { opacity: 0, transform: "scale(0.86) translateY(24px)", filter: "blur(6px)" },
                { opacity: 1, transform: "scale(1.014) translateY(-2px)", filter: "blur(0px)", offset: 0.68 },
                { opacity: 1, transform: "scale(1) translateY(0px)", filter: "blur(0px)" }
              ], {
                duration: dur,
                easing: "cubic-bezier(0.16, 1, 0.3, 1)",
                fill: "none"
              });
            }
          });
          win.setTimeout(function() {
            rootEl.removeAttribute("seafari-launch-zoom-active");
          }, dur + 40);
        } catch (zErr) {}
      }

      try {
        doc.documentElement.setAttribute("seafari-launch-zoom-init", "true");
        // Start with macOS Zoomed window state
        if (win.windowState !== 1) {
          try { win.maximize(); } catch (maxErr) {}
        }
        win.setTimeout(function() {
          if (typeof win.requestAnimationFrame === "function") {
            win.requestAnimationFrame(function() { playMacOSZoom(520); });
          } else {
            playMacOSZoom(520);
          }
        }, 90);

        // Also animate when clicking the green macOS Zoom button (.titlebar-max / .titlebar-restore)
        var zoomBtns = doc.querySelectorAll(".titlebar-max, .titlebar-restore");
        zoomBtns.forEach(function(zBtn) {
          zBtn.addEventListener("command", function() {
            playMacOSZoom(360);
          }, true);
          zBtn.addEventListener("click", function(ev) {
            if (ev.button === 0) playMacOSZoom(360);
          }, true);
        });
      } catch (launchZoomErr) {}

      // --- 2. macOS Genie Animation (Minimize & Restore) ---
      try {
        var rootEl = doc.documentElement;
        var origMinimize = win.minimize ? win.minimize.bind(win) : null;

        function playGenieMinimize() {
          if (win._seafariGenieAnimating) return;
          win._seafariGenieAnimating = true;
          win._seafariWasMinimized = true;
          rootEl.removeAttribute("seafari-genie-restoring");
          rootEl.setAttribute("seafari-genie-minimizing", "true");

          var genieAnims = [];
          var targets = [doc.getElementById("navigator-toolbox"), doc.getElementById("browser")];
          targets.forEach(function(el) {
            if (el && typeof el.animate === "function") {
              var anim = el.animate([
                { transform: "perspective(900px) rotateX(0deg) scale(1, 1) translateY(0%)", clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)", opacity: 1, filter: "blur(0px)" },
                { transform: "perspective(900px) rotateX(-8deg) scale(0.88, 0.78) translateY(14%)", clipPath: "polygon(3% 0%, 97% 0%, 78% 100%, 22% 100%)", opacity: 0.96, filter: "blur(0.5px)", offset: 0.28 },
                { transform: "perspective(900px) rotateX(-16deg) scale(0.54, 0.38) translateY(48%)", clipPath: "polygon(14% 0%, 86% 0%, 62% 100%, 38% 100%)", opacity: 0.82, filter: "blur(1.5px)", offset: 0.62 },
                { transform: "perspective(900px) rotateX(-24deg) scale(0.14, 0.04) translateY(96%)", clipPath: "polygon(42% 0%, 58% 0%, 52% 100%, 48% 100%)", opacity: 0, filter: "blur(4px)" }
              ], {
                duration: 380,
                easing: "cubic-bezier(0.32, 0, 0.67, 0)",
                fill: "forwards"
              });
              genieAnims.push(anim);
            }
          });

          win.setTimeout(function() {
            if (origMinimize) {
              try { origMinimize(); } catch (mErr) {}
            }
            win.setTimeout(function() {
              rootEl.removeAttribute("seafari-genie-minimizing");
              genieAnims.forEach(function(a) { try { a.cancel(); } catch (cErr) {} });
              win._seafariGenieAnimating = false;
            }, 80);
          }, 360);
        }

        function playGenieRestore() {
          if (win._seafariGenieAnimating) return;
          rootEl.removeAttribute("seafari-genie-minimizing");
          rootEl.setAttribute("seafari-genie-restoring", "true");

          var targets = [doc.getElementById("navigator-toolbox"), doc.getElementById("browser")];
          targets.forEach(function(el) {
            if (el && typeof el.animate === "function") {
              el.animate([
                { transform: "perspective(900px) rotateX(-24deg) scale(0.14, 0.04) translateY(96%)", clipPath: "polygon(42% 0%, 58% 0%, 52% 100%, 48% 100%)", opacity: 0, filter: "blur(4px)" },
                { transform: "perspective(900px) rotateX(-14deg) scale(0.54, 0.38) translateY(46%)", clipPath: "polygon(14% 0%, 86% 0%, 62% 100%, 38% 100%)", opacity: 0.84, filter: "blur(1.2px)", offset: 0.36 },
                { transform: "perspective(900px) rotateX(-4deg) scale(0.92, 0.84) translateY(10%)", clipPath: "polygon(3% 0%, 97% 0%, 82% 100%, 18% 100%)", opacity: 0.98, filter: "blur(0px)", offset: 0.72 },
                { transform: "perspective(900px) rotateX(0deg) scale(1, 1) translateY(0%)", clipPath: "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)", opacity: 1, filter: "blur(0px)" }
              ], {
                duration: 420,
                easing: "cubic-bezier(0.16, 1, 0.3, 1)",
                fill: "none"
              });
            }
          });

          win.setTimeout(function() {
            rootEl.removeAttribute("seafari-genie-restoring");
          }, 440);
        }

        // Override window.minimize so any minimize invocation uses the Genie funnel
        win.minimize = function() {
          playGenieMinimize();
        };

        // Strip XUL oncommand and intercept command/click on all .titlebar-min buttons
        var minBtns = doc.querySelectorAll(".titlebar-min");
        minBtns.forEach(function(btn) {
          btn.removeAttribute("oncommand");
          ["command", "click"].forEach(function(evName) {
            btn.addEventListener(evName, function(ev) {
              ev.preventDefault();
              ev.stopPropagation();
              ev.stopImmediatePropagation();
              playGenieMinimize();
            }, true);
          });
        });

        win.addEventListener("sizemodechange", function() {
          if (win.windowState === 2) {
            win._seafariWasMinimized = true;
          } else if (win._seafariWasMinimized && !win._seafariGenieAnimating) {
            win._seafariWasMinimized = false;
            playGenieRestore();
          }
        }, true);

        win.addEventListener("activate", function() {
          if (win._seafariWasMinimized && win.windowState !== 2 && !win._seafariGenieAnimating) {
            win._seafariWasMinimized = false;
            playGenieRestore();
          }
        }, true);
      } catch (genieErr) {}

      // --- 3. Cool macOS Window Moving Physics & Liquid Glass Inertia ---
      try {
        var lastWinX = win.screenX;
        var lastWinY = win.screenY;
        var moveTimeout = null;
        var isMoving = false;

        win.setInterval(function() {
          try {
            if (win._seafariGenieAnimating || win.windowState === 2) return;
            var cx = win.screenX;
            var cy = win.screenY;
            if (cx !== lastWinX || cy !== lastWinY) {
              var dx = Math.max(-18, Math.min(18, cx - lastWinX));
              var dy = Math.max(-18, Math.min(18, cy - lastWinY));
              lastWinX = cx;
              lastWinY = cy;
              doc.documentElement.style.setProperty("--seafari-drag-dx", dx + "px");
              doc.documentElement.style.setProperty("--seafari-drag-dy", dy + "px");
              if (!isMoving) {
                isMoving = true;
                doc.documentElement.setAttribute("seafari-window-moving", "true");
              }
              if (moveTimeout) win.clearTimeout(moveTimeout);
              moveTimeout = win.setTimeout(function() {
                isMoving = false;
                doc.documentElement.removeAttribute("seafari-window-moving");
                doc.documentElement.style.setProperty("--seafari-drag-dx", "0px");
                doc.documentElement.style.setProperty("--seafari-drag-dy", "0px");
              }, 150);
            }
          } catch (e) {}
        }, 16);
      } catch (moveErr) {}
"""
    cfg = cfg.replace(
        'if (urlbar) {\n        urlbar.addEventListener("focusin", function() { setHidden(false); updateToolbarLuminance(); });',
        window_move_js + '\n      if (urlbar) {\n        urlbar.addEventListener("focusin", function() { setHidden(false); updateToolbarLuminance(); });',
        1,
    )
    return cfg


def unpack_omni_ja(ja_path, out_dir, seven_zip):
    os.makedirs(out_dir, exist_ok=True)
    if seven_zip:
        # 7z exits with code 2 on Mozilla's optimized omni.ja header, which is expected
        subprocess.run(
            [seven_zip, "x", ja_path, f"-o{out_dir}", "-y"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if not os.listdir(out_dir):
        unzip_bin = shutil.which("unzip")
        if unzip_bin:
            subprocess.run(
                [unzip_bin, "-q", ja_path, "-d", out_dir],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    if not os.listdir(out_dir):
        raise RuntimeError(f"Failed to unpack {ja_path}: output directory is empty")


def repack_omni_ja(src_dir, ja_path, seven_zip):
    if os.path.exists(ja_path):
        os.remove(ja_path)

    # Remove META-INF if present so signature verification never fails on repacked omni.ja
    meta_inf = os.path.join(src_dir, "META-INF")
    if os.path.exists(meta_inf):
        shutil.rmtree(meta_inf)

    abs_ja = os.path.abspath(ja_path)
    if seven_zip:
        subprocess.run(
            [seven_zip, "a", "-tzip", "-mx=0", abs_ja, "*"],
            cwd=src_dir,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    else:
        with zipfile.ZipFile(abs_ja, "w", zipfile.ZIP_STORED) as zf:
            for root_dir, _, files in os.walk(src_dir):
                for file in files:
                    full_path = os.path.join(root_dir, file)
                    rel_path = os.path.relpath(full_path, src_dir).replace("\\", "/")
                    zf.write(full_path, rel_path)


def copy_tree_overlay(src_root, dst_root):
    if not os.path.exists(src_root):
        return
    for root_dir, _, files in os.walk(src_root):
        rel_dir = os.path.relpath(root_dir, src_root)
        target_dir = dst_root if rel_dir == "." else os.path.join(dst_root, rel_dir)
        os.makedirs(target_dir, exist_ok=True)
        for file in files:
            if file.endswith("-append.css"):
                continue
            shutil.copy2(os.path.join(root_dir, file), os.path.join(target_dir, file))


def patch_omni_tree(temp_dir, repo_root, is_browser_omni=False):
    # 1. Overlay files from chrome/browser/ or chrome/gre/
    if is_browser_omni:
        copy_tree_overlay(os.path.join(repo_root, "chrome", "browser"), temp_dir)
        locale_src = os.path.join(repo_root, "chrome", "browser", "locale", "en-US", "branding")
        if os.path.exists(locale_src):
            en_us_branding = os.path.join(temp_dir, "chrome", "en-US", "locale", "branding")
            if os.path.exists(en_us_branding):
                for fname in ["brand.properties", "brand.dtd"]:
                    src_f = os.path.join(locale_src, fname)
                    if os.path.exists(src_f):
                        shutil.copy2(src_f, os.path.join(en_us_branding, fname))
            l10n_branding = os.path.join(temp_dir, "localization", "en-US", "branding")
            if os.path.exists(l10n_branding):
                src_ftl = os.path.join(locale_src, "brand.ftl")
                if os.path.exists(src_ftl):
                    shutil.copy2(src_ftl, os.path.join(l10n_branding, "brand.ftl"))

        # Append onboarding & Nova bypass preferences directly to defaults/preferences/firefox.js
        firefox_prefs_js = os.path.join(temp_dir, "defaults", "preferences", "firefox.js")
        if os.path.exists(firefox_prefs_js):
            with open(firefox_prefs_js, "a", encoding="utf-8") as f:
                f.write("\n" + ONBOARDING_BYPASS_PREFS_JS)
    else:
        copy_tree_overlay(os.path.join(repo_root, "chrome", "gre"), temp_dir)

    # 2. Append global.css and aboutNetError.css overrides if present
    global_css = os.path.join(temp_dir, "chrome", "toolkit", "skin", "classic", "global", "global.css")
    global_append = os.path.join(
        repo_root, "chrome", "gre", "chrome", "toolkit", "skin", "classic", "global", "seafari-global-append.css"
    )
    if os.path.exists(global_css) and os.path.exists(global_append):
        with open(global_append, "r", encoding="utf-8") as f_in, open(global_css, "a", encoding="utf-8") as f_out:
            f_out.write("\n" + f_in.read())

    net_error_css = os.path.join(temp_dir, "chrome", "toolkit", "skin", "classic", "global", "aboutNetError.css")
    net_error_append = os.path.join(
        repo_root, "chrome", "gre", "chrome", "toolkit", "skin", "classic", "global", "seafari-aboutNetError-append.css"
    )
    if os.path.exists(net_error_css) and os.path.exists(net_error_append):
        with open(net_error_append, "r", encoding="utf-8") as f_in, open(net_error_css, "a", encoding="utf-8") as f_out:
            f_out.write("\n" + f_in.read())

    # 3. Patch about-firefox.mjs
    about_firefox_mjs = os.path.join(
        temp_dir, "chrome", "browser", "content", "browser", "preferences", "config", "about-firefox.mjs"
    )
    if os.path.exists(about_firefox_mjs):
        with open(about_firefox_mjs, "r", encoding="utf-8") as f:
            mjs = f.read()
        mjs = re.sub(
            r'Preferences\.addSetting\(\{\s*id:\s*"supportShareIdeas",\s*\}\);',
            'Preferences.addSetting({ id: "supportShareIdeas" });\n'
            'Preferences.addSetting({ id: "supportDiscord" });\n'
            'Preferences.addSetting({ id: "supportMatrix" });\n'
            'Preferences.addSetting({ id: "supportGithub" });',
            mjs,
        )
        mjs = re.sub(
            r'(\{\s*id:\s*"supportShareIdeas",\s*l10nId:\s*"support-share-ideas",\s*control:\s*"moz-box-link",\s*controlAttrs:\s*\{\s*href:\s*"https://connect\.mozilla\.org/",\s*\},\s*\})',
            r'\1,\n'
            '          {\n'
            '            id: "supportDiscord",\n'
            '            control: "moz-box-link",\n'
            '            controlAttrs: {\n'
            '              href: "https://discord.com/invite/PSeTkDMnr",\n'
            '              label: "Join our Discord",\n'
            '            },\n'
            '          },\n'
            '          {\n'
            '            id: "supportMatrix",\n'
            '            control: "moz-box-link",\n'
            '            controlAttrs: {\n'
            '              href: "https://matrix.inled.es",\n'
            '              label: "Join our Matrix space",\n'
            '            },\n'
            '          },\n'
            '          {\n'
            '            id: "supportGithub",\n'
            '            control: "moz-box-link",\n'
            '            controlAttrs: {\n'
            '              href: "https://github.com/InledGroup/seafari",\n'
            '              label: "GitHub Repository",\n'
            '            },\n'
            '          }',
            mjs,
        )
        with open(about_firefox_mjs, "w", encoding="utf-8") as f:
            f.write(mjs)

    # 4. Walk tree for illustrations, brand.*, native newtab files, and Firefox->Seafari text replacement
    text_exts = (
        ".properties", ".dtd", ".ftl", ".json", ".js", ".sys.mjs", ".xhtml", ".xml", ".html", ".css"
    )
    word_re = re.compile(r"(?<!/)\bFirefox\b")

    for root_dir, dirs, files in os.walk(temp_dir):
        if os.path.basename(root_dir) == "illustrations":
            for file in files:
                fpath = os.path.join(root_dir, file)
                if file.endswith(".svg"):
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" viewBox="0 0 1 1"/>\n')
                elif file.endswith(".png"):
                    with open(fpath, "wb") as f:
                        f.write(TRANSPARENT_PNG)
                else:
                    with open(fpath, "wb") as f:
                        f.write(b"")

        for file in files:
            fpath = os.path.join(root_dir, file)

            if file == "brand.properties":
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                content = re.sub(r"^brandShorterName\s*=.*", "brandShorterName=Seafari", content, flags=re.M)
                content = re.sub(r"^brandShortName\s*=.*", "brandShortName=Seafari", content, flags=re.M)
                content = re.sub(r"^brandFullName\s*=.*", "brandFullName=Seafari Browser", content, flags=re.M)
                content = re.sub(r"^vendorShortName\s*=.*", "vendorShortName=Inled Group", content, flags=re.M)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

            elif file == "brand.dtd":
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                content = re.sub(r'<!ENTITY\s+brandShorterName\s+"[^"]*"\s*>', '<!ENTITY brandShorterName "Seafari">', content)
                content = re.sub(r'<!ENTITY\s+brandShortName\s+"[^"]*"\s*>', '<!ENTITY brandShortName "Seafari">', content)
                content = re.sub(r'<!ENTITY\s+brandFullName\s+"[^"]*"\s*>', '<!ENTITY brandFullName "Seafari Browser">', content)
                content = re.sub(r'<!ENTITY\s+vendorShortName\s+"[^"]*"\s*>', '<!ENTITY vendorShortName "Inled Group">', content)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

            elif file == "brand.ftl":
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                content = re.sub(r"^-brand-shorter-name\s*=.*", "-brand-shorter-name = Seafari", content, flags=re.M)
                content = re.sub(r"^-brand-short-name\s*=.*", "-brand-short-name = Seafari", content, flags=re.M)
                content = re.sub(r"^-brand-shortcut-name\s*=.*", "-brand-shortcut-name = Seafari", content, flags=re.M)
                content = re.sub(r"^-brand-full-name\s*=.*", "-brand-full-name = Seafari Browser", content, flags=re.M)
                content = re.sub(r"^-brand-product-name\s*=.*", "-brand-product-name = Seafari", content, flags=re.M)
                content = re.sub(r"^-vendor-short-name\s*=.*", "-vendor-short-name = Inled Group", content, flags=re.M)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

            if file in ("newtab.xhtml", "newtab.html", "activity-stream.html"):
                for sibling in os.listdir(root_dir):
                    if sibling.endswith(".js"):
                        js_path = os.path.join(root_dir, sibling)
                        try:
                            with open(js_path, "r", encoding="utf-8") as f:
                                js_content = f.read()
                            if "browser.newtabpage.url" not in js_content:
                                with open(js_path, "w", encoding="utf-8") as f:
                                    f.write(NEWTAB_REDIRECT_JS + "\n" + js_content)
                        except Exception:
                            pass

            if file.endswith(text_exts):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        text = f.read()
                    new_text = word_re.sub("Seafari", text)
                    if new_text != text:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(new_text)
                except Exception:
                    pass


def patch_application_ini(ini_path):
    if not os.path.exists(ini_path):
        return
    with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    content = re.sub(r"^Vendor=.*", "Vendor=Inled Group", content, flags=re.M)
    content = re.sub(r"^Name=.*", "Name=Seafari", content, flags=re.M)
    content = re.sub(r"^RemotingName=.*", "RemotingName=seafari", content, flags=re.M)
    content = re.sub(r"^ID=.*", "ID=seafari@inledgroup", content, flags=re.M)
    content = re.sub(r"^Enabled=1", "Enabled=0", content, flags=re.M)
    content = re.sub(r"^ServerURL=.*", "ServerURL=", content, flags=re.M)
    if "CodeName=" not in content:
        content = content.replace("[App]", "[App]\nCodeName=Seafari", 1)
    with open(ini_path, "w", encoding="utf-8") as f:
        f.write(content)


def patch_pe_resources_inplace(exe_path, png_path):
    """
    Pure-Python Win32 PE resource patcher that works identically on Linux and Windows.
    Replaces embedded Firefox icons (RT_ICON / RT_GROUP_ICON), version strings (RT_VERSION),
    and string table (RT_STRING) in firefox.exe / seafari.exe with Seafari branding,
    and strips the Authenticode certificate table so Windows accepts the modified binary.
    """
    if not os.path.exists(exe_path):
        return
    print(f"[*] Patching Win32 PE resources (icons + version info) in {os.path.basename(exe_path)} ...")

    src_w, src_h, src_px = read_png_rgba(png_path)
    dib_16 = make_ico_dib(16, 16, resize_rgba(src_w, src_h, src_px, 16, 16))
    dib_32 = make_ico_dib(32, 32, resize_rgba(src_w, src_h, src_px, 32, 32))
    dib_48 = make_ico_dib(48, 48, resize_rgba(src_w, src_h, src_px, 48, 48))
    png_256 = encode_png_paeth(256, 256, resize_rgba(src_w, src_h, src_px, 256, 256))
    png_192 = encode_png_paeth(192, 192, resize_rgba(src_w, src_h, src_px, 192, 192))

    with open(exe_path, "rb") as f:
        data = bytearray(f.read())

    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    num_sections = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    size_opt = struct.unpack_from("<H", data, e_lfanew + 20)[0]
    opt_offset = e_lfanew + 24
    magic = struct.unpack_from("<H", data, opt_offset)[0]
    dd_offset = opt_offset + (112 if magic == 0x20B else 96)

    # Clear IMAGE_DIRECTORY_ENTRY_SECURITY (index 4) and CheckSum
    sec_rva, sec_size = struct.unpack_from("<II", data, dd_offset + 4 * 8)
    if sec_rva > 0 and sec_rva + sec_size == len(data):
        del data[sec_rva:]
    struct.pack_into("<II", data, dd_offset + 4 * 8, 0, 0)
    struct.pack_into("<I", data, opt_offset + 64, 0)

    # Locate .rsrc section
    sec_table = opt_offset + size_opt
    rsrc_rva = rsrc_raw = 0
    for i in range(num_sections):
        s = sec_table + i * 40
        name = bytes(data[s : s + 8]).rstrip(b"\x00")
        vsize, vrva, rawsize, rawptr = struct.unpack_from("<IIII", data, s + 8)
        if name == b".rsrc":
            rsrc_rva = vrva
            rsrc_raw = rawptr
            break
    if not rsrc_raw:
        print(f"[!] Could not locate .rsrc section in {exe_path}")
        return

    def rva_to_raw(rva):
        return rsrc_raw + (rva - rsrc_rva)

    icon_entries = {}  # icon_id -> (data_entry_off, raw_off, orig_size)
    group_entries = {}  # group_id -> (data_entry_off, raw_off, orig_size)

    def walk_rsrc(offset, path=()):
        num_named, num_id = struct.unpack_from("<HH", data, rsrc_raw + offset + 12)
        for i in range(num_named + num_id):
            entry_off = rsrc_raw + offset + 16 + i * 8
            name_or_id, data_or_dir = struct.unpack_from("<II", data, entry_off)
            ident = name_or_id if not (name_or_id & 0x80000000) else "NAMED"
            if data_or_dir & 0x80000000:
                walk_rsrc(data_or_dir & 0x7FFFFFFF, path + (ident,))
            else:
                d_off = rsrc_raw + data_or_dir
                d_rva, d_size, _, _ = struct.unpack_from("<IIII", data, d_off)
                raw_off = rva_to_raw(d_rva)
                if path[0] == 3:
                    icon_entries[path[1]] = (d_off, raw_off, d_size)
                elif path[0] == 14:
                    group_entries[path[1]] = (d_off, raw_off, d_size)

    walk_rsrc(0)

    # First find a large icon slot (>= len(png_256)) such as icon 28 (61,748 bytes)
    # where we can store the 256x256 Seafari PNG and point other 256x256 icon entries to its RVA!
    shared_256_rva = None
    for iid, (d_off, raw_off, orig_size) in icon_entries.items():
        if orig_size >= len(png_256):
            data[raw_off : raw_off + len(png_256)] = png_256
            struct.pack_into("<I", data, d_off + 4, len(png_256))
            shared_256_rva = struct.unpack_from("<I", data, d_off)[0]
            break

    # Update all RT_GROUP_ICONs and their referenced RT_ICONs
    for gid, (g_doff, g_raw, g_size) in group_entries.items():
        _, _, gcount = struct.unpack_from("<HHH", data, g_raw)
        for j in range(gcount):
            grp_entry_off = g_raw + 6 + j * 14
            w, h, cc, r, planes, bpp, bytes_in_res, nid = struct.unpack_from(
                "<BBBBHHIH", data, grp_entry_off
            )
            if nid not in icon_entries:
                continue
            i_doff, i_raw, i_orig_size = icon_entries[nid]
            dim = 256 if w == 0 else w
            replacement = None
            if dim == 16 and len(dib_16) <= i_orig_size:
                replacement = dib_16
            elif dim == 32 and len(dib_32) <= i_orig_size:
                replacement = dib_32
            elif dim == 48 and len(dib_48) <= i_orig_size:
                replacement = dib_48
            elif dim == 256:
                if shared_256_rva is not None:
                    # Point this 256x256 icon's IMAGE_RESOURCE_DATA_ENTRY RVA to shared_256_rva
                    struct.pack_into("<II", data, i_doff, shared_256_rva, len(png_256))
                    struct.pack_into("<I", data, grp_entry_off + 8, len(png_256))
                    continue
                elif len(png_192) <= i_orig_size:
                    replacement = png_192

            if replacement is not None:
                data[i_raw : i_raw + len(replacement)] = replacement
                struct.pack_into("<I", data, i_doff + 4, len(replacement))
                struct.pack_into("<I", data, grp_entry_off + 8, len(replacement))

    # Replace UTF-8 manifest application identity and description
    data = bytearray(
        bytes(data)
        .replace(b'name="Firefox"', b'name="Seafari"')
        .replace(b"<description>Firefox</description>", b"<description>Seafari</description>")
        .replace(b'"Firefox"', b'"Seafari"')
    )

    # Replace UTF-16LE "Firefox" -> "Seafari" (same 7-char length!) and "Mozilla" -> "Seafari" in .rsrc
    rsrc_end = len(data)
    rsrc_slice = bytes(data[rsrc_raw:rsrc_end])
    rsrc_slice = rsrc_slice.replace("Mozilla Firefox".encode("utf-16le"), "Seafari Browser".encode("utf-16le"))
    rsrc_slice = rsrc_slice.replace("Firefox".encode("utf-16le"), "Seafari".encode("utf-16le"))
    rsrc_slice = rsrc_slice.replace(
        "Mozilla Corporation".encode("utf-16le"),
        "Inled Group        ".encode("utf-16le"),
    )
    rsrc_slice = rsrc_slice.replace(
        "Mozilla Foundation".encode("utf-16le"),
        "Inled Group       ".encode("utf-16le"),
    )
    rsrc_slice = rsrc_slice.replace("firefox.exe".encode("utf-16le"), "seafari.exe".encode("utf-16le"))
    data[rsrc_raw:rsrc_end] = rsrc_slice

    with open(exe_path, "wb") as f:
        f.write(data)


def main():
    parser = argparse.ArgumentParser(description="Patch extracted Windows Firefox into Seafari.")
    parser.add_argument("--firefox-dir", required=True, help="Path to extracted Firefox directory (core/)")
    parser.add_argument("--ublock-xpi", required=True, help="Path to downloaded ublock_origin.xpi")
    parser.add_argument("--atbc-xpi", required=True, help="Path to downloaded adaptive_tab_bar_colour.xpi")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    firefox_dir = os.path.abspath(args.firefox_dir)
    seven_zip = find_7z()
    print(f"[*] Using 7-Zip binary: {seven_zip}")

    # Ensure chrome/ tree and multi-size seafari.ico are up to date
    subprocess.run([sys.executable, os.path.join(repo_root, "scripts", "init_chrome_tree.py")], check=True)

    # 1. Distribution & Extensions
    dist_dir = os.path.join(firefox_dir, "distribution")
    ext_dir = os.path.join(dist_dir, "extensions")
    os.makedirs(ext_dir, exist_ok=True)

    patch_ublock_xpi(args.ublock_xpi, os.path.join(ext_dir, "uBlock0@raymondhill.net.xpi"))
    atbc_dst = os.path.join(ext_dir, "ATBC@EasonWong.xpi")
    if os.path.abspath(args.atbc_xpi) != os.path.abspath(atbc_dst):
        shutil.copy2(args.atbc_xpi, atbc_dst)

    tab_overview_dst = os.path.join(firefox_dir, "tab-overview")
    if os.path.exists(tab_overview_dst):
        shutil.rmtree(tab_overview_dst)
    shutil.copytree(os.path.join(repo_root, "tab-overview"), tab_overview_dst)

    policies = {
        "policies": {
            "DisableAppUpdate": True,
            "DontCheckDefaultBrowser": True,
            "DisableTelemetry": True,
            "DisableFeedbackCommands": True,
            "OverrideFirstRunPage": "",
            "OverridePostUpdatePage": "",
            "SearchEngines": {"Default": "Google"},
            "Preferences": {
                "toolkit.crashreporter.enabled": False,
                "breakpad.reportURL": "",
                "browser.tabs.crashReporting.sendReport": False,
                "browser.crashReports.unsubmittedCheck.enabled": False,
                "browser.crashReports.unsubmittedCheck.autoSubmit2": False,
                "datareporting.healthreport.uploadEnabled": False,
                "datareporting.policy.dataSubmissionEnabled": False,
                "toolkit.startup.max_resumed_crashes": -1,
                "browser.sessionstore.resume_from_crash": False,
                "browser.sessionstore.max_resumed_crashes": -1,
                "browser.sessionstore.interval": 60000,
                "browser.tabs.unloadOnLowMemory": True,
                "gfx.webrender.all": True,
                "gfx.webrender.pre-cache-shaders": True,
                "gfx.canvas.accelerated": True,
                "layers.gpu-process.enabled": True,
                "network.http.http3.enable": True,
                "network.ssl_tokens_cache_capacity": 2048,
                "network.http.max-connections": 900,
                "network.http.max-persistent-connections-per-server": 8,
                "network.http.pacing.requests.enabled": False,
                "network.http.speculative-parallel-limit": 0,
                "content.notify.interval": 100000,
                "content.notify.ontimer": True,
                "image.mem.decode_bytes_at_a_time": 65536,
                "browser.sessionhistory.max_entries": 15,
                "browser.sessionhistory.max_total_viewers": 3,
                "browser.cache.memory.enable": True,
                "browser.cache.memory.capacity": 524288,
                "browser.cache.disk.enable": True,
                "media.autoplay.default": 5,
                "media.memory_cache_max_size": 65536,
                "javascript.options.mem.gc_incremental_slice_ms": 10,
                "extensions.webextensions.remote": False,
                "browser.tabs.remote.autostart": False,
                "toolkit.legacyUserProfileCustomizations.stylesheets": True,
                "xpinstall.signatures.required": False,
                "widget.windows.mica": False,
                "termsofuse.bypassNotification": True,
                "termsofuse.acceptedVersion": 999,
                "termsofuse.acceptedDate": "1700000000000",
                "termsofuse.firstAcceptedDate": "1700000000000",
                "browser.aboutwelcome.enabled": False,
                "browser.nova.enabled": False,
                "browser.newtabpage.activity-stream.nova.enabled": False,
                "datareporting.policy.dataSubmissionPolicyBypassNotification": True,
                "datareporting.policy.firstRunURL": "",
                "keyword.enabled": True,
                "browser.search.suggest.enabled": True,
                "browser.urlbar.suggest.searches": True,
                "browser.urlbar.showSearchSuggestionsFirst": True,
                "browser.shell.checkDefaultBrowser": False,
                "browser.aboutConfig.showWarning": False,
                "browser.tabs.warnOnClose": False,
                "datareporting.healthreport.uploadEnabled": False,
                "datareporting.policy.dataSubmissionEnabled": False,
                "app.update.auto": False,
                "app.update.enabled": False,
                "browser.startup.homepage": "about:newtab",
                "browser.startup.page": 1,
                "browser.startup.homepage_override.mstone": "ignore",
                "browser.newtabpage.enabled": True,
                "browser.newtabpage.url": "about:newtab",
                "browser.newtabpage.activity-stream.enabled": False,
                "browser.newtabpage.activity-stream.showSearch": False,
                "browser.newtabpage.activity-stream.showTopSites": True,
                "browser.newtabpage.activity-stream.feeds.section.topstories": False,
                "browser.newtabpage.activity-stream.feeds.snippets": False,
                "browser.newtabpage.activity-stream.section.highlights.includeBookmarks": False,
                "browser.newtabpage.activity-stream.section.highlights.includeDownloads": False,
                "browser.newtabpage.activity-stream.section.highlights.includeVisited": True,
                "browser.newtabpage.activity-stream.section.highlights.includePocket": False,
                "browser.newtabpage.activity-stream.feeds.section.highlights": True,
                "browser.newtabpage.activity-stream.topSitesRows": 1,
                "browser.newtabpage.activity-stream.highlights.rows": 1,
            },
        }
    }
    with open(os.path.join(dist_dir, "policies.json"), "w", encoding="utf-8") as f:
        json.dump(policies, f, indent=2)

    # 2. Autoconfig (defaults/pref/autoconfig.js + seafari.cfg)
    pref_dir = os.path.join(firefox_dir, "defaults", "pref")
    os.makedirs(pref_dir, exist_ok=True)
    with open(os.path.join(pref_dir, "autoconfig.js"), "w", encoding="utf-8") as f:
        f.write(
            'pref("general.config.filename", "seafari.cfg");\n'
            'pref("general.config.obscure_value", 0);\n'
            'pref("general.config.sandbox_enabled", false);\n'
        )

    linux_script = os.path.join(repo_root, "build_seafari.sh")
    if not os.path.exists(linux_script):
        linux_script = os.path.join(repo_root, "build_seafari_linux.sh")
    seafari_cfg = extract_seafari_cfg_from_linux_script(linux_script)
    with open(os.path.join(firefox_dir, "seafari.cfg"), "w", encoding="utf-8") as f:
        f.write(seafari_cfg + "\n")

    # 3. Prepare seafari-theme/ folder inside Firefox directory
    theme_dir = os.path.join(firefox_dir, "seafari-theme")
    if os.path.exists(theme_dir):
        shutil.rmtree(theme_dir)
    os.makedirs(theme_dir, exist_ok=True)

    shutil.copytree(os.path.join(repo_root, "MacTahoe"), os.path.join(theme_dir, "MacTahoe"))
    for fname in ["userChrome.css", "userContent.css", "customChrome.css", "newtab.html", "seafari.png"]:
        shutil.copy2(os.path.join(repo_root, fname), os.path.join(theme_dir, fname))
    shutil.copy2(os.path.join(repo_root, "chrome", "windows-fixes.css"), os.path.join(theme_dir, "windows-fixes.css"))

    # Ensure userChrome.css imports windows-fixes.css
    uc_path = os.path.join(theme_dir, "userChrome.css")
    with open(uc_path, "r", encoding="utf-8") as f:
        uc_text = f.read()
    if "windows-fixes.css" not in uc_text:
        with open(uc_path, "a", encoding="utf-8") as f:
            f.write('\n@import "windows-fixes.css"; /**/\n')

    # Append extra styles to userContent.css
    ucont_path = os.path.join(theme_dir, "userContent.css")
    with open(ucont_path, "a", encoding="utf-8") as f:
        f.write("\n" + USERCONTENT_APPEND_CSS)

    # 4. Unpack, overlay, patch, and repack omni.ja & browser/omni.ja
    for rel_ja, is_browser in [("omni.ja", False), (os.path.join("browser", "omni.ja"), True)]:
        ja_path = os.path.join(firefox_dir, rel_ja)
        if not os.path.exists(ja_path):
            print(f"[!] Warning: {ja_path} not found, skipping")
            continue
        print(f"[*] Unpacking {rel_ja} ...")
        with tempfile.TemporaryDirectory() as tmp_omni:
            unpack_omni_ja(ja_path, tmp_omni, seven_zip)
            print(f"[*] Patching & overlaying Safari UI assets into {rel_ja} ...")
            patch_omni_tree(tmp_omni, repo_root, is_browser_omni=is_browser)
            print(f"[*] Repacking {rel_ja} ...")
            repack_omni_ja(tmp_omni, ja_path, seven_zip)

    # 5. Patch application.ini
    patch_application_ini(os.path.join(firefox_dir, "application.ini"))
    patch_application_ini(os.path.join(firefox_dir, "browser", "application.ini"))

    # 6. Remove *.sig signature files and crash reporter executables/telemetry daemons
    for root_dir, _, files in os.walk(firefox_dir):
        for file in files:
            if file.endswith(".sig"):
                try:
                    os.remove(os.path.join(root_dir, file))
                except OSError:
                    pass

    for cfile in [
        "crashreporter.exe",
        "crashreporter.ini",
        "crashhelper.exe",
        "minidump-analyzer.exe",
        "pingsender.exe",
        "default-browser-agent.exe",
    ]:
        cpath = os.path.join(firefox_dir, cfile)
        if os.path.exists(cpath):
            try:
                os.remove(cpath)
            except OSError:
                pass

    # 7. Replace Windows VisualElements icons & manifests
    png_src = os.path.join(repo_root, "seafari.png")
    ico_src = os.path.join(repo_root, "seafari.ico")
    shutil.copy2(ico_src, os.path.join(firefox_dir, "seafari.ico"))
    shutil.copy2(png_src, os.path.join(firefox_dir, "seafari.png"))

    vis_dir = os.path.join(firefox_dir, "browser", "VisualElements")
    if os.path.exists(vis_dir):
        for vfile in os.listdir(vis_dir):
            if vfile.endswith(".png"):
                shutil.copy2(png_src, os.path.join(vis_dir, vfile))

    ff_manifest = os.path.join(firefox_dir, "firefox.VisualElementsManifest.xml")
    seafari_manifest = os.path.join(firefox_dir, "seafari.VisualElementsManifest.xml")
    if os.path.exists(ff_manifest):
        shutil.copy2(ff_manifest, seafari_manifest)

    # 8. Build dedicated 1.5-second hold native launcher (seafari.exe) and patch Win32 PE resources
    ff_exe = os.path.join(firefox_dir, "firefox.exe")
    seafari_exe = os.path.join(firefox_dir, "seafari.exe")
    if os.path.exists(ff_exe):
        patch_pe_resources_inplace(ff_exe, png_src)

    launcher_c = os.path.join(repo_root, "src", "seafari_launcher.c")
    launcher_rc = os.path.join(repo_root, "src", "seafari_launcher.rc")
    built_launcher = False
    if os.path.exists(launcher_c):
        res_obj = None
        if os.path.exists(launcher_rc):
            if shutil.which("x86_64-w64-mingw32-windres"):
                res_out = os.path.join(repo_root, "src", "seafari_launcher.o")
                try:
                    subprocess.run(["x86_64-w64-mingw32-windres", f"-I{repo_root}", "-i", launcher_rc, "-o", res_out], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    res_obj = res_out
                except Exception:
                    pass
            elif shutil.which("llvm-rc"):
                res_out = os.path.join(repo_root, "src", "seafari_launcher.res")
                try:
                    subprocess.run(["llvm-rc", f"/I{repo_root}", f"/fo{res_out}", launcher_rc], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    res_obj = res_out
                except Exception:
                    pass

        compilers = []
        if res_obj:
            compilers.append(["x86_64-w64-mingw32-gcc", "-O2", "-mwindows", launcher_c, res_obj, "-o", seafari_exe, "-lshell32"])
            compilers.append(["clang", "-O2", launcher_c, res_obj, "-o", seafari_exe, "-Xlinker", "/subsystem:windows", "-lshell32"])
            compilers.append(["gcc", "-O2", "-mwindows", launcher_c, res_obj, "-o", seafari_exe, "-lshell32"])
        compilers.extend([
            ["x86_64-w64-mingw32-gcc", "-O2", "-mwindows", launcher_c, "-o", seafari_exe, "-lshell32"],
            ["clang", "-O2", launcher_c, "-o", seafari_exe, "-Xlinker", "/subsystem:windows", "-lshell32"],
            ["gcc", "-O2", "-mwindows", launcher_c, "-o", seafari_exe, "-lshell32"],
        ])

        for cmd in compilers:
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                patch_pe_resources_inplace(seafari_exe, png_src)
                built_launcher = True
                print("[*] Successfully compiled native 1.5-second hold launcher: seafari.exe")
                break
            except Exception:
                continue

        if res_obj and os.path.exists(res_obj):
            try:
                os.remove(res_obj)
            except Exception:
                pass

    if not built_launcher:
        if os.path.exists(ff_exe):
            shutil.copy2(ff_exe, seafari_exe)
        elif os.path.exists(seafari_exe):
            patch_pe_resources_inplace(seafari_exe, png_src)

    # 9. Register InledGroup.Seafari in Windows Registry if running on Windows
    if sys.platform == "win32":
        try:
            import winreg
            ico_target = os.path.join(firefox_dir, "seafari.ico")
            exe_target = os.path.join(firefox_dir, "seafari.exe")
            key_path = r"Software\Classes\AppUserModelId\InledGroup.Seafari"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Seafari")
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, ico_target if os.path.exists(ico_target) else f"{exe_target},0")
                winreg.SetValueEx(k, "IconBackgroundColor", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(k, "ShowInNewInstall", 0, winreg.REG_DWORD, 1)

            smi_path = r"Software\Clients\StartMenuInternet\Seafari"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, smi_path) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "Seafari")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, smi_path + r"\Capabilities") as k:
                winreg.SetValueEx(k, "ApplicationDescription", 0, winreg.REG_SZ, "Seafari Browser")
                winreg.SetValueEx(k, "ApplicationName", 0, winreg.REG_SZ, "Seafari")
                winreg.SetValueEx(k, "ApplicationIcon", 0, winreg.REG_SZ, f"{exe_target},0")
            print("[*] Successfully registered InledGroup.Seafari in Windows Registry")
        except Exception as reg_err:
            print(f"[!] Warning: Could not register AppUserModelId in registry: {reg_err}")

        # 10. Clean up any legacy Start Menu shortcuts (Firefox.lnk -> Seafari.lnk)
        try:
            smp = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
            ff_lnk = os.path.join(smp, "Firefox.lnk")
            sea_lnk = os.path.join(smp, "Seafari.lnk")
            if os.path.exists(ff_lnk):
                if os.path.exists(sea_lnk):
                    os.remove(ff_lnk)
                else:
                    shutil.move(ff_lnk, sea_lnk)
                print("[*] Fixed Start Menu shortcut from Firefox.lnk to Seafari.lnk")
            ff_pb = os.path.join(smp, "Firefox Private Browsing.lnk")
            if os.path.exists(ff_pb):
                os.remove(ff_pb)
        except Exception:
            pass

    print("[+] Successfully patched Windows Firefox build into Seafari!")


if __name__ == "__main__":
    main()
