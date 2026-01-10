#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
from pathlib import Path

def is_storage0_path(p: Path) -> bool:
    s = str(p.resolve())
    # typische Android/Termux shared-storage Pfade
    prefixes = (
        "/storage/emulated/0/",
        "/sdcard/",
        "/storage/self/primary/",
    )
    return any(s.startswith(x) for x in prefixes)

def run(cmd, cwd: Path):
    print("$ " + " ".join(cmd) + f"  (cwd={cwd})")
    subprocess.check_call(cmd, cwd=str(cwd))

def sanitize_version(v: str) -> str:
    v = v.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    out = "".join(ch for ch in v if ch in allowed)
    if not out:
        raise SystemExit("ERROR: invalid version (allowed: letters/digits . _ -)")
    return out

def copy_project(src_root: Path, dst_root: Path):
    # wirklich simpel: copytree ohne node_modules und dist
    ignore = shutil.ignore_patterns("node_modules", "dist", ".git", "__pycache__", "*.pyc")
    if dst_root.exists():
        shutil.rmtree(dst_root)
    shutil.copytree(src_root, dst_root, ignore=ignore)

def main():
    # Script liegt neben src/
    root = Path(__file__).resolve().parent
    src_dir = root / "src"
    dist_dir = root / "dist"
    entry = src_dir / "ui-kit-0.js"  # simple assumption

    if not src_dir.is_dir():
        raise SystemExit(f"ERROR: src/ not found next to {Path(__file__).name}")
    if not entry.is_file():
        raise SystemExit(f"ERROR: entry not found: {entry}")

    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(__file__).name} <version>\nExample: {Path(__file__).name} 0.0.1")
    version = sanitize_version(sys.argv[1])

    name = "ui-kit-0"
    out_dev = f"{name}-{version}.js"
    out_min = f"{name}-{version}.min.js"

    dist_dir.mkdir(parents=True, exist_ok=True)

    # Wenn Projekt in storage0 liegt, in $HOME bauen
    build_root = root
    building_in_home = is_storage0_path(root)
    if building_in_home:
        home = Path(os.environ.get("HOME", str(Path("~").expanduser()))).resolve()
        ws = home / ".uikit_release"
        ws.mkdir(parents=True, exist_ok=True)
        build_root = ws / f"build_{root.name}"
        copy_project(root, build_root)

    # Ensure dist in build root
    (build_root / "dist").mkdir(parents=True, exist_ok=True)

    # esbuild über npx (kein npm install nötig)
    common = ["npx", "-y", "esbuild", "./src/ui-kit-0.js", "--bundle", "--format=esm", "--target=es2020"]

    # unminified
    run(common + ["--sourcemap", f"--outfile=./dist/{out_dev}"], cwd=build_root)
    # minified
    run(common + ["--minify", f"--outfile=./dist/{out_min}"], cwd=build_root)

    # Ergebnis zurückkopieren, wenn wir in $HOME gebaut haben
    if building_in_home:
        built_dist = build_root / "dist"
        for fn in (out_dev, out_dev + ".map", out_min):
            shutil.copy2(built_dist / fn, dist_dir / fn)
    
    src_files = ["sbom.json", "ui-kit-.theme.css", "ui-kit-0.css"]
    for fn in src_files:
        src_src = build_root / "src" / fn
        if src_src.is_file():
            shutil.copy2(src_src, dist_dir / fn)

    doc_files = ["API.md", "README.md", "Styling.md"]
    for fn in doc_files:
        doc_src = build_root / fn
        if doc_src.is_file():
            shutil.copy2(doc_src, dist_dir / fn)
    
    # third_party deploy:
    # - default: only *.min.js
    # - exception: include ace/*.js (ace has no min in your tree)
    # - never include *.map
    tp_src = build_root / "src" / "third_party"
    tp_dst = dist_dir / "third_party"

    if tp_src.is_dir():
        # clean target
        if tp_dst.exists():
            shutil.rmtree(tp_dst)
        tp_dst.mkdir(parents=True, exist_ok=True)

        def copy_rel(src_file: Path):
            rel = src_file.relative_to(tp_src)
            out = tp_dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, out)

        # 1) copy all *.min.js recursively (no maps)
        for p in tp_src.rglob("*.min.js"):
            if p.name.endswith(".map"):
                continue
            copy_rel(p)

        # 2) copy ace/*.js (no maps) because ace isn't minified in your tree
        ace_dir = tp_src / "ace"
        if ace_dir.is_dir():
            for p in ace_dir.glob("*.js"):
                if p.name.endswith(".map"):
                    continue
                copy_rel(p)
    
    print("\nDone:")
    print(f" - dist/{out_dev}")
    print(f" - dist/{out_min}")

if __name__ == "__main__":
    main()