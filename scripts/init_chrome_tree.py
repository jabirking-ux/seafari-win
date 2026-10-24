#!/usr/bin/env python3
"""
Populates the chrome/ directory structure for Seafari Windows port from the
upstream Seafari assets in the repository root.
"""
import os
import shutil
import struct

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    png_path = os.path.join(root, "seafari.png")
    ico_path = os.path.join(root, "seafari.ico")

    with open(png_path, "rb") as f:
        png_data = f.read()

    # Generate valid Windows ICO file wrapping the PNG
    ico_header = struct.pack("<HHH", 0, 1, 1)
    ico_entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png_data), 22)
    with open(ico_path, "wb") as f:
        f.write(ico_header + ico_entry + png_data)

    dirs = [
        "chrome/browser/content/browser/preferences/config",
        "chrome/browser/content/branding",
        "chrome/browser/locale/en-US/branding",
        "chrome/browser/skin/classic/browser/preferences",
        "chrome/gre/chrome/toolkit/skin/classic/global",
    ]
    for d in dirs:
        os.makedirs(os.path.join(root, d), exist_ok=True)

    # Branding icons
    branding_dir = os.path.join(root, "chrome/browser/content/branding")
    for icon in [
        "icon16.png", "icon32.png", "icon48.png", "icon64.png", "icon128.png",
        "about.png", "about-logo.png", "about-logo@2x.png",
        "about-logo-private.png", "about-logo-private@2x.png",
    ]:
        shutil.copy2(png_path, os.path.join(branding_dir, icon))
    shutil.copy2(ico_path, os.path.join(branding_dir, "document.ico"))

    with open(os.path.join(branding_dir, "about-logo.svg"), "w", encoding="utf-8") as f:
        f.write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">\n'
            '  <image href="icon128.png" x="0" y="0" width="128" height="128"/>\n'
            '</svg>\n'
        )

    wordmark_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 30" width="120" height="30">\n'
        '  <text x="0" y="22" font-family="system-ui, sans-serif" font-size="20" font-weight="bold" fill="white">Seafari</text>\n'
        '</svg>\n'
    )
    for wm in ["firefox-wordmark.svg", "about-wordmark.svg"]:
        with open(os.path.join(branding_dir, wm), "w", encoding="utf-8") as f:
            f.write(wordmark_svg)

    # Transparent fox-ai.svg
    with open(os.path.join(root, "chrome/browser/skin/classic/browser/preferences/fox-ai.svg"), "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"/>\n')

    # Locale branding files
    locale_dir = os.path.join(root, "chrome/browser/locale/en-US/branding")
    with open(os.path.join(locale_dir, "brand.properties"), "w", encoding="utf-8") as f:
        f.write(
            "brandShorterName=Seafari\n"
            "brandShortName=Seafari\n"
            "brandFullName=Seafari Browser\n"
            "vendorShortName=Inled Group\n"
        )
    with open(os.path.join(locale_dir, "brand.dtd"), "w", encoding="utf-8") as f:
        f.write(
            '<!ENTITY brandShorterName      "Seafari">\n'
            '<!ENTITY brandShortName        "Seafari">\n'
            '<!ENTITY brandFullName         "Seafari Browser">\n'
            '<!ENTITY vendorShortName       "Inled Group">\n'
            '<!ENTITY trademarkInfo.part1   "Seafari and the Seafari logos are trademarks of Inled Group.">\n'
        )
    with open(os.path.join(locale_dir, "brand.ftl"), "w", encoding="utf-8") as f:
        f.write(
            "-brand-shorter-name = Seafari\n"
            "-brand-short-name = Seafari\n"
            "-brand-shortcut-name = Seafari\n"
            "-brand-full-name = Seafari Browser\n"
            "-brand-product-name = Seafari\n"
            "-vendor-short-name = Inled Group\n"
            "trademarkInfo = Seafari and the Seafari logos are trademarks of Inled Group.\n"
        )

    # Global CSS overrides in chrome/gre/
    gre_global_dir = os.path.join(root, "chrome/gre/chrome/toolkit/skin/classic/global")
    with open(os.path.join(gre_global_dir, "seafari-global-append.css"), "w", encoding="utf-8") as f:
        f.write("""
/* Apple Safari layout variables and overrides */
:root {
    --color-violet-90: #0071e3 !important;
    --color-violet-80: #005dc2 !important;
    --color-violet-70: #004da6 !important;
    --color-violet-60: #0071e3 !important;
    --button-background-color-primary: #0071e3 !important;
    --button-background-color-primary-hover: #005dc2 !important;
    --button-background-color-primary-active: #004da6 !important;
    --in-content-primary-button-background: #0071e3 !important;
    --in-content-primary-button-background-hover: #005dc2 !important;
    --in-content-primary-button-background-active: #004da6 !important;
    --newtab-primary-action-background: #0071e3 !important;
    --theme-primary-color: #0071e3 !important;
    --theme-primary-hover-color: #005dc2 !important;
    --theme-primary-active-color: #004da6 !important;
    --button-border-radius: 999px !important;
}

button.main-button,
button[type="submit"],
.button-primary,
button.button-primary,
button.primary,
button.dialog-button[default="true"],
.dialog-button-box button[default="true"],
#updateSettingsContainer button:not(moz-button),
#aboutwelcome-onboarding button:not(moz-button) {
    background-color: #0071e3 !important;
    background-image: none !important;
    border: none !important;
    color: white !important;
    box-shadow: none !important;
    text-shadow: none !important;
    cursor: pointer !important;
}

button.main-button:hover,
button[type="submit"]:hover,
.button-primary:hover,
button.button-primary:hover,
button.primary:hover,
button.dialog-button[default="true"]:hover,
.dialog-button-box button[default="true"]:hover,
#updateSettingsContainer button:hover:not(moz-button),
#aboutwelcome-onboarding button:hover:not(moz-button) {
    background-color: #005dc2 !important;
    background-image: none !important;
    box-shadow: none !important;
}

button.main-button:active,
button[type="submit"]:active,
.button-primary:active,
button.button-primary:active,
button.primary:active,
button.dialog-button[default="true"]:active,
.dialog-button-box button[default="true"]:active,
#updateSettingsContainer button:active:not(moz-button),
#aboutwelcome-onboarding button:active:not(moz-button) {
    background-color: #004da6 !important;
    background-image: none !important;
    box-shadow: none !important;
}

#category-more-from-mozilla,
.category[name="more-from-mozilla"] {
    display: none !important;
}
""")

    with open(os.path.join(gre_global_dir, "seafari-aboutNetError-append.css"), "w", encoding="utf-8") as f:
        f.write("""
/* Safari style for about:neterror */
body {
    background-color: #1a1a1a !important;
    color: #e0e0e0 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
    height: 100vh !important;
    margin: 0 !important;
    padding: 20px !important;
    box-sizing: border-box !important;
    text-align: center !important;
}

#errorPageContainer {
    max-width: 600px !important;
    margin: 0 auto !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
}

.illustration,
.error-illustration,
#errorPageContainer::before,
.title-icon {
    display: none !important;
}

h1,
.title {
    font-size: 22px !important;
    font-weight: 600 !important;
    color: #ffffff !important;
    margin-bottom: 12px !important;
    text-align: center !important;
}

.description,
p,
#errorDescriptionContainer,
#errorShortDescText {
    font-size: 14px !important;
    line-height: 1.5 !important;
    color: #a1a1a6 !important;
    text-align: center !important;
    margin-bottom: 24px !important;
    max-width: 480px !important;
}

#netErrorButtonContainer {
    margin-top: 10px !important;
}

button,
.button,
#tryAgainButton {
    background-color: rgba(255, 255, 255, 0.1) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    color: white !important;
    border-radius: 6px !important;
    padding: 6px 16px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    cursor: pointer !important;
}
""")

    # Sync userChrome.css, userContent.css, customChrome.css, newtab.html, seafari.png, MacTahoe into chrome/
    for item in ["userChrome.css", "userContent.css", "customChrome.css", "newtab.html", "seafari.png", "seafari.ico"]:
        shutil.copy2(os.path.join(root, item), os.path.join(root, "chrome", item))

    # Append windows-fixes.css import to chrome/userChrome.css if not present
    chrome_uc = os.path.join(root, "chrome", "userChrome.css")
    with open(chrome_uc, "r", encoding="utf-8") as f:
        uc_content = f.read()
    if "windows-fixes.css" not in uc_content:
        with open(chrome_uc, "a", encoding="utf-8") as f:
            f.write('\n@import "windows-fixes.css"; /**/\n')

    chrome_mactahoe = os.path.join(root, "chrome", "MacTahoe")
    if os.path.exists(chrome_mactahoe):
        shutil.rmtree(chrome_mactahoe)
    shutil.copytree(os.path.join(root, "MacTahoe"), chrome_mactahoe)

    print("Successfully initialized chrome/ tree and seafari.ico")

if __name__ == "__main__":
    main()
