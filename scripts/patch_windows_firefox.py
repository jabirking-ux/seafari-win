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
import subprocess
import sys
import tempfile
import zipfile


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
        background: transparent !important;
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
    h1, h2, p, span, label { color: white !important; }
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
    # Remove bash $UA_LINE placeholder
    cfg = cfg.replace("$UA_LINE", 'pref("widget.windows.mica", false);\n  pref("xpinstall.signatures.required", false);')

    # Fix upstream XPCOM contract ID bug for nsIFileOutputStream
    cfg = cfg.replace("@mozilla.org/file/output-stream;1", "@mozilla.org/network/file-output-stream;1")

    # Inject Windows profile theme auto-sync & immediate nsIStyleSheetService registration right after log("Seafari Autoconfig initialization started");
    profile_sync_js = """
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
          if (!target.exists() || target.fileSize !== entry.fileSize) {
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

  // Register userChrome.css and userContent.css immediately via nsIStyleSheetService
  // so the Safari theme is active on the very first launch without requiring a restart.
  var sss = Components.classes["@mozilla.org/content/style-sheet-service;1"]
                      .getService(Components.interfaces.nsIStyleSheetService);
  var ioSvc = Components.classes["@mozilla.org/network/io-service;1"]
                        .getService(Components.interfaces.nsIIOService);
  ["userChrome.css", "userContent.css"].forEach(function(cssName) {
    try {
      var cssFile = chromeDst.clone();
      cssFile.append(cssName);
      if (cssFile.exists()) {
        var cssURI = ioSvc.newFileURI(cssFile);
        if (!sss.sheetRegistered(cssURI, sss.USER_SHEET)) {
          sss.loadAndRegisterSheet(cssURI, sss.USER_SHEET);
          log("Registered " + cssName + " via nsIStyleSheetService");
        }
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

    # Also support modern CSS Flexbox in makePill and skip toolbarspring elements
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
        'Array.from(navBar.children).forEach(function(node) {\n      if (node.localName === "toolbarspring" || node.localName === "toolbartabstop") { try { node.style.setProperty("display", "none", "important"); } catch(e) {} return; }\n      var id = node.id || "";',
    )
    cfg = cfg.replace(
        'forceStyle(pill, "display", "-moz-box");\n      forceStyle(pill, "-moz-box-align", "center");',
        'forceStyle(pill, "display", "-moz-box");\n      forceStyle(pill, "display", "flex");\n      forceStyle(pill, "-moz-box-align", "center");\n      forceStyle(pill, "align-items", "center");',
    )
    cfg = cfg.replace(
        'forceStyle(node, "display", "-moz-box");\n        forceStyle(node, "-moz-box-align", "center");\n        forceStyle(node, "-moz-box-pack", "center");',
        'forceStyle(node, "display", "-moz-box");\n        forceStyle(node, "display", "inline-flex");\n        forceStyle(node, "-moz-box-align", "center");\n        forceStyle(node, "align-items", "center");\n        forceStyle(node, "-moz-box-pack", "center");\n        forceStyle(node, "justify-content", "center");',
    )
    cfg = cfg.replace(
        'if (pillUrlbar) {\n      pillUrlbar.setAttribute("flex", "1");\n      forceStyle(pillUrlbar, "-moz-box-flex", "1");\n    }',
        'if (pillUrlbar) {\n      pillUrlbar.setAttribute("flex", "1");\n      forceStyle(pillUrlbar, "-moz-box-flex", "1");\n      forceStyle(pillUrlbar, "flex", "1 1 auto");\n      if (urlbarEl) { urlbarEl.setAttribute("flex", "1"); forceStyle(urlbarEl, "flex", "1 1 auto"); }\n    }',
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
        # Fallback to unzip command if available
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
        # Also overlay chrome/browser/locale/en-US/branding into chrome/en-US/locale/branding and localization/en-US/branding
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
    if "CodeName=" not in content:
        content = content.replace("[App]", "[App]\nCodeName=Seafari", 1)
    with open(ini_path, "w", encoding="utf-8") as f:
        f.write(content)


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

    # Ensure chrome/ tree and seafari.ico are up to date
    subprocess.run([sys.executable, os.path.join(repo_root, "scripts", "init_chrome_tree.py")], check=True)

    # 1. Distribution & Extensions
    dist_dir = os.path.join(firefox_dir, "distribution")
    ext_dir = os.path.join(dist_dir, "extensions")
    os.makedirs(ext_dir, exist_ok=True)

    patch_ublock_xpi(args.ublock_xpi, os.path.join(ext_dir, "uBlock0@raymondhill.net.xpi"))
    shutil.copy2(args.atbc_xpi, os.path.join(ext_dir, "ATBC@EasonWong.xpi"))

    tab_overview_dst = os.path.join(firefox_dir, "tab-overview")
    if os.path.exists(tab_overview_dst):
        shutil.rmtree(tab_overview_dst)
    shutil.copytree(os.path.join(repo_root, "tab-overview"), tab_overview_dst)

    policies = {
        "policies": {
            "DisableAppUpdate": True,
            "DontCheckDefaultBrowser": True,
            "SearchEngines": {"Default": "Google"},
            "Preferences": {
                "extensions.webextensions.remote": False,
                "browser.tabs.remote.autostart": False,
                "toolkit.legacyUserProfileCustomizations.stylesheets": True,
                "xpinstall.signatures.required": False,
                "widget.windows.mica": False,
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

    # 6. Copy seafari.ico, seafari.png, and create seafari.exe launcher copy
    shutil.copy2(os.path.join(repo_root, "seafari.ico"), os.path.join(firefox_dir, "seafari.ico"))
    shutil.copy2(os.path.join(repo_root, "seafari.png"), os.path.join(firefox_dir, "seafari.png"))
    ff_exe = os.path.join(firefox_dir, "firefox.exe")
    seafari_exe = os.path.join(firefox_dir, "seafari.exe")
    if os.path.exists(ff_exe):
        shutil.copy2(ff_exe, seafari_exe)

    print("[+] Successfully patched Windows Firefox build into Seafari!")


if __name__ == "__main__":
    main()
