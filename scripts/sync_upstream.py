#!/usr/bin/env python3
"""
Synchronizes UI assets and build scripts from upstream InledGroup/seafari
into this Windows port repository, preserving Windows-specific adaptations.
"""
import os
import shutil
import subprocess
import sys
import tempfile


UPSTREAM_REPO = "https://github.com/InledGroup/seafari.git"
SYNC_DIRS = ["MacTahoe", "tab-overview"]
SYNC_FILES = [
    "userChrome.css",
    "userContent.css",
    "customChrome.css",
    "newtab.html",
    "seafari.png",
    "diagnose.js",
    "test_extraction.js",
]


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with tempfile.TemporaryDirectory() as tmpdir:
        upstream_dir = os.path.join(tmpdir, "seafari")
        print(f"[*] Cloning upstream {UPSTREAM_REPO} ...")
        subprocess.run(
            ["git", "clone", "--depth", "1", UPSTREAM_REPO, upstream_dir],
            check=True,
        )

        commit_sha = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream_dir)
            .decode("utf-8")
            .strip()
        )
        print(f"[*] Latest upstream commit: {commit_sha}")

        for d in SYNC_DIRS:
            src_d = os.path.join(upstream_dir, d)
            dst_d = os.path.join(repo_root, d)
            if os.path.exists(src_d):
                if os.path.exists(dst_d):
                    shutil.rmtree(dst_d)
                shutil.copytree(src_d, dst_d)
                print(f"[*] Synced directory: {d}/")

        for f in SYNC_FILES:
            src_f = os.path.join(upstream_dir, f)
            dst_f = os.path.join(repo_root, f)
            if os.path.exists(src_f):
                shutil.copy2(src_f, dst_f)
                print(f"[*] Synced file: {f}")

        src_build = os.path.join(upstream_dir, "build_seafari.sh")
        if os.path.exists(src_build):
            shutil.copy2(src_build, os.path.join(repo_root, "build_seafari_linux.sh"))
            print("[*] Synced build_seafari.sh -> build_seafari_linux.sh")

        with open(os.path.join(repo_root, "last_upstream_commit.txt"), "w", encoding="utf-8") as f:
            f.write(commit_sha + "\n")

        # Refresh chrome/ tree with synced assets + Windows fixes
        subprocess.run(
            [sys.executable, os.path.join(repo_root, "scripts", "init_chrome_tree.py")],
            check=True,
        )
        print("[+] Upstream synchronization complete!")


if __name__ == "__main__":
    main()
