#!/usr/bin/env python3
"""
zalo_acquisition.py

Module acquisition cho đồ án: nhận folder backup (hoặc adb pull nếu cần),
tạo workspace acquisition, tính hashes, lưu manifest và chain-of-custody.

WARNING: Chỉ chạy trên dữ liệu mà bạn có quyền truy cập.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def compute_sha256(file_path, chunk_size=8192):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def copy_with_metadata(src: Path, dst: Path):
    # copy file preserving metadata (atime/mtime) and permissions
    shutil.copy2(src, dst)

def walk_and_copy(src_root: Path, dst_root: Path):
    """
    Walk src_root and copy files to dst_root preserving folder structure.
    Return list of dicts with metadata and hashes.
    """
    manifest = []
    for root, dirs, files in os.walk(src_root):
        rel_dir = os.path.relpath(root, src_root)
        dst_dir = dst_root / rel_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        for fname in files:
            src_file = Path(root) / fname
            dst_file = dst_dir / fname
            copy_with_metadata(src_file, dst_file)
            sha256 = compute_sha256(dst_file)
            stat = dst_file.stat()
            manifest.append({
                "original_path": str(src_file),
                "acquired_path": str(dst_file),
                "rel_path": str(Path(rel_dir) / fname),
                "size": stat.st_size,
                "mtime": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
                "sha256": sha256
            })
    return manifest

def adb_pull_package(package_name: str, out_dir: Path):
    """
    Try to adb pull /data/data/<package_name> to out_dir/package_name
    Requires adb available and device connected + permission (root or backup allowed).
    """
    dest = out_dir / package_name
    dest.mkdir(parents=True, exist_ok=True)
    print(f"[adb] Pulling package {package_name} to {dest} (this may fail if no permission)...")
    # Try simple adb pull paths
    candidates = [
        f"/data/data/{package_name}",
        f"/sdcard/Android/data/{package_name}",
    ]
    for p in candidates:
        try:
            cmd = ["adb", "pull", p, str(dest)]
            subprocess.run(cmd, check=True)
            print(f"[adb] Pulled {p} successfully.")
            return dest
        except subprocess.CalledProcessError:
            print(f"[adb] Unable to pull {p} (may require root or not present).")
    raise RuntimeError("adb pull failed for known candidate paths. Check device permissions or try manual copy.")

def write_json_atomic(path: Path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    tmp.replace(path)

def create_acquisition_workspace(base_out: Path, package_name: str):
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    folder_name = f"acq_{package_name}_{ts}"
    out = base_out / folder_name
    out.mkdir(parents=True, exist_ok=False)
    return out

def compress_and_hash(folder: Path, zip_name: Path):
    shutil.make_archive(base_name=str(zip_name.with_suffix("")), format="zip", root_dir=folder)
    final_zip = zip_name.with_suffix(".zip")
    h = compute_sha256(final_zip)
    return final_zip, h

def parse_args():
    p = argparse.ArgumentParser(description="Acquisition module - copy backup folder, create manifest and chain-of-custody.")
    p.add_argument("--input", "-i", type=str, help="Path to input backup folder (required unless --adb is used).")
    p.add_argument("--adb-package", type=str, help="(optional) Android package to adb pull (e.g. com.zing.zalo).")
    p.add_argument("--outdir", "-o", type=str, default="./acquisitions", help="Base output directory for acquisitions.")
    p.add_argument("--case-id", type=str, default="CASE-UNKNOWN", help="Case ID for Chain of Custody.")
    p.add_argument("--collector", type=str, default="Collector-Unknown", help="Name of person collecting evidence.")
    p.add_argument("--reason", type=str, default="Forensic acquisition", help="Reason / notes.")
    p.add_argument("--zip", action="store_true", help="Create a zip archive of the acquisition and compute its sha256.")
    p.add_argument("--consent", action="store_true", help="Confirm you have legal consent / authorization to acquire data.")
    return p.parse_args()

def main():
    args = parse_args()
    if not args.consent:
        print("LEGAL WARNING: You must have explicit authorization to collect/analyze device data.")
        print("Run again with --consent when you have authorization.")
        sys.exit(1)

    base_out = Path(args.outdir).resolve()
    base_out.mkdir(parents=True, exist_ok=True)

    # Determine source
    if args.adb_package:
        # attempt adb pull
        try:
            src_root = adb_pull_package(args.adb_package, base_out)
            package_name = args.adb_package.replace(".", "_")
        except Exception as e:
            print(f"[ERROR] adb pull failed: {e}")
            sys.exit(2)
    elif args.input:
        src_root = Path(args.input).resolve()
        if not src_root.exists():
            print(f"[ERROR] Input path not found: {src_root}")
            sys.exit(2)
        package_name = src_root.name
    else:
        print("Either --input or --adb-package is required.")
        sys.exit(2)

    # create workspace
    workspace = create_acquisition_workspace(base_out, package_name)
    print(f"[+] Created workspace: {workspace}")

    # copy and manifest
    print("[*] Copying files and computing hashes...")
    manifest = walk_and_copy(src_root, workspace / "data")
    manifest_path = workspace / "manifest.json"
    write_json_atomic(manifest_path, {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "source": str(src_root),
        "items": manifest
    })
    print(f"[+] Manifest written: {manifest_path}")

    # chain of custody
    coc = {
        "case_id": args.case_id,
        "collector": args.collector,
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "reason": args.reason,
        "source": str(src_root),
        "workspace": str(workspace)
    }
    coc_path = workspace / "chain_of_custody.json"
    write_json_atomic(coc_path, coc)
    print(f"[+] Chain-of-custody written: {coc_path}")

    # summary
    total_files = len(manifest)
    total_bytes = sum(item["size"] for item in manifest)
    summary = {
        "summary_created_at": datetime.utcnow().isoformat() + "Z",
        "total_files": total_files,
        "total_bytes": total_bytes
    }
    write_json_atomic(workspace / "summary.json", summary)
    print(f"[+] Summary: {total_files} files, {total_bytes} bytes")

    # optional zip
    if args.zip:
        print("[*] Creating zip archive (this may take time)...")
        zip_base = base_out / f"{workspace.name}"
        archive_path, archive_hash = compress_and_hash(workspace, zip_base)
        meta = {
            "archive": str(archive_path),
            "archive_sha256": archive_hash
        }
        write_json_atomic(workspace / "archive_info.json", meta)
        print(f"[+] Archive created: {archive_path}")
        print(f"[+] Archive SHA256: {archive_hash}")

    print("[+] Acquisition complete.")
    print(f"Workspace folder: {workspace}")
    print("Please preserve this workspace and include chain_of_custody.json when handing off evidence.")

if __name__ == "__main__":
    main()
