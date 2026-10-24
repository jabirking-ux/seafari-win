#!/usr/bin/env python3
"""
Populates the chrome/ directory structure for Seafari Windows port from the
upstream Seafari assets in the repository root, and generates a proper
multi-resolution Windows ICO file (16, 32, 48, 64, 128, 256px) from seafari.png.
"""
import os
import shutil
import struct
import zlib


def read_png_rgba(path):
    with open(path, "rb") as f:
        data = f.read()
    pos = 8
    idat = bytearray()
    w = h = color_type = 0
    while pos < len(data):
        length, ctype = struct.unpack(">I4s", data[pos : pos + 8])
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            w, h, _, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break
    raw = zlib.decompress(bytes(idat))
    bpp = 4 if color_type == 6 else 3
    stride = w * bpp
    pixels = bytearray(w * h * 4)
    prev = bytearray(stride)
    i = 0
    for y in range(h):
        ftype = raw[i]
        row = bytearray(raw[i + 1 : i + 1 + stride])
        i += 1 + stride
        if ftype == 1:
            for x in range(bpp, stride):
                row[x] = (row[x] + row[x - bpp]) & 0xFF
        elif ftype == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 0xFF
        elif ftype == 3:
            for x in range(stride):
                a = row[x - bpp] if x >= bpp else 0
                b = prev[x]
                row[x] = (row[x] + ((a + b) >> 1)) & 0xFF
        elif ftype == 4:
            for x in range(stride):
                a = row[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[x] = (row[x] + pr) & 0xFF
        prev = row
        if bpp == 4:
            pixels[y * w * 4 : (y + 1) * w * 4] = row
        else:
            for x in range(w):
                pixels[(y * w + x) * 4 : (y * w + x) * 4 + 4] = bytes(
                    [row[x * 3], row[x * 3 + 1], row[x * 3 + 2], 255]
                )
    return w, h, pixels


def resize_rgba(src_w, src_h, src_px, dst_w, dst_h):
    dst = bytearray(dst_w * dst_h * 4)
    scale_x = src_w / dst_w
    scale_y = src_h / dst_h
    for dy in range(dst_h):
        sy0 = int(dy * scale_y)
        sy1 = max(sy0 + 1, int((dy + 1) * scale_y))
        for dx in range(dst_w):
            sx0 = int(dx * scale_x)
            sx1 = max(sx0 + 1, int((dx + 1) * scale_x))
            r = g = b = a = count = 0
            for sy in range(sy0, min(sy1, src_h)):
                for sx in range(sx0, min(sx1, src_w)):
                    idx = (sy * src_w + sx) * 4
                    r += src_px[idx]
                    g += src_px[idx + 1]
                    b += src_px[idx + 2]
                    a += src_px[idx + 3]
                    count += 1
            d_idx = (dy * dst_w + dx) * 4
            dst[d_idx] = r // count
            dst[d_idx + 1] = g // count
            dst[d_idx + 2] = b // count
            dst[d_idx + 3] = a // count
    return dst


def make_ico_dib(w, h, rgba):
    """Creates a 32-bit BGRA bottom-up BITMAPINFOHEADER + XOR + AND mask for ICO/RT_ICON."""
    xor_size = w * h * 4
    and_row_bytes = ((w + 31) // 32) * 4
    and_size = and_row_bytes * h
    header = struct.pack(
        "<IiiHHIIiiII",
        40,
        w,
        h * 2,
        1,
        32,
        0,
        xor_size + and_size,
        0,
        0,
        0,
        0,
    )
    xor_mask = bytearray(xor_size)
    and_mask = bytearray(and_size)
    for y in range(h):
        src_y = h - 1 - y
        for x in range(w):
            s_idx = (src_y * w + x) * 4
            d_idx = (y * w + x) * 4
            r, g, b, a = rgba[s_idx : s_idx + 4]
            xor_mask[d_idx] = b
            xor_mask[d_idx + 1] = g
            xor_mask[d_idx + 2] = r
            xor_mask[d_idx + 3] = a
            if a < 128:
                and_mask[y * and_row_bytes + (x // 8)] |= 1 << (7 - (x % 8))
    return header + bytes(xor_mask) + bytes(and_mask)


def encode_png_paeth(w, h, rgba):
    def make_chunk(ctype, data):
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I4s", len(data), ctype) + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    raw = bytearray()
    stride = w * 4
    prev = bytearray(stride)
    for y in range(h):
        row = rgba[y * stride : (y + 1) * stride]
        raw.append(4)
        for x in range(stride):
            a = row[x - 4] if x >= 4 else 0
            b = prev[x]
            c = prev[x - 4] if x >= 4 else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            raw.append((row[x] - pr) & 0xFF)
        prev = row
    idat = zlib.compress(bytes(raw), 9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + make_chunk(b"IHDR", ihdr)
        + make_chunk(b"IDAT", idat)
        + make_chunk(b"IEND", b"")
    )


def build_multi_size_ico(png_path, ico_path):
    src_w, src_h, src_px = read_png_rgba(png_path)
    sizes = [16, 32, 48, 64, 128, 256]
    blobs = []
    for sz in sizes:
        rgba = resize_rgba(src_w, src_h, src_px, sz, sz)
        if sz == 256:
            blobs.append((sz, encode_png_paeth(sz, sz, rgba)))
        else:
            blobs.append((sz, make_ico_dib(sz, sz, rgba)))

    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = bytearray()
    payload = bytearray()
    for sz, data in blobs:
        b_sz = 0 if sz >= 256 else sz
        entries.extend(
            struct.pack("<BBBBHHII", b_sz, b_sz, 0, 0, 1, 32, len(data), offset)
        )
        payload.extend(data)
        offset += len(data)

    with open(ico_path, "wb") as f:
        f.write(header + bytes(entries) + bytes(payload))


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    png_path = os.path.join(root, "seafari.png")
    ico_path = os.path.join(root, "seafari.ico")

    build_multi_size_ico(png_path, ico_path)

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

    print("Successfully initialized chrome/ tree and multi-resolution seafari.ico")


if __name__ == "__main__":
    main()
