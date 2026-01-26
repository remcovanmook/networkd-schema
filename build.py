import os
import subprocess
import shutil

# Top 10 most commonly used/LTS systemd versions (recent 5 roughly)
# + v257 (current)
VERSIONS = [
    "v259",
    "v258",
    "v257",
    "v256",
    "v255",
    "v254",
    "v253",
    "v252",
    "v251",
    "v250",
    "v249",
    "v248",
    "v247",
    "v246",
    "v245",
    "v244",
    "v243",
    "v242",
    "v241",
    "v240",
    "v239",
    "v238",
    "v237"
]

BASE_VERSION = "v257"
CURATED_BASE_DIR = f"curated/{BASE_VERSION}"
SRC_ORIGINAL_DIR = "src/original"
SCHEMAS_DIR = "schemas"

FILES = [
    "systemd.network",
    "systemd.netdev",
    "systemd.link",
    "systemd.networkd.conf"
]

def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

def ensure_dirs():
    os.makedirs(SRC_ORIGINAL_DIR, exist_ok=True)
    os.makedirs(SCHEMAS_DIR, exist_ok=True)

import argparse

# ... (imports)

def main():
    parser = argparse.ArgumentParser(description="Build systemd networkd schemas.")
    parser.add_argument("-v", "--version", help="Build a specific version (e.g. v255)")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if files exist/unchanged")
    args = parser.parse_args()

    ensure_dirs()
    
    # Auto-detect venv python
    venv_python = os.path.join(os.getcwd(), ".venv", "bin", "python3")
    if os.path.exists(venv_python):
        python_cmd = venv_python
    else:
        python_cmd = "python3"
        
    target_versions = VERSIONS
    if args.version:
        if args.version not in VERSIONS:
            print(f"Error: Version {args.version} not in supported list.")
            print("Supported versions:", ", ".join(VERSIONS))
            return
        target_versions = [args.version]
    
    # 1. Generate Raw Schemas for all versions
    for ver in target_versions:
        # ... logic ...
        ver_dir = os.path.join(SRC_ORIGINAL_DIR, ver)
        os.makedirs(ver_dir, exist_ok=True)
        
        # Check if already generated to save time (optional, but good for retries)
        # But user asked to "Build a directory... pre-build". So we just build.
        # We assume generate_systemd_schema.py supports --out
        
        # Check if output files exist
        exists = True
        for f in FILES:
             if not os.path.exists(os.path.join(ver_dir, f"{f}.{ver}.schema.json")):
                 exists = False
                 break
        
        if not exists or args.force:
            print(f"Generating raw schemas for {ver}...")
            cmd = [
                python_cmd, "bin/generate_systemd_schema.py",
                "--version", ver,
                "--out", ver_dir
            ]
            if args.force:
                cmd.append("--force")
            run_command(cmd)
        else:
            print(f"Raw schemas for {ver} already exist.")

    # 2. Derive Curated Schemas for all versions
    # Base Curated is curated/v257/systemd.*.v257.schema.json
    # Base Generated is src/original/v257/systemd.*.v257.schema.json
    
    for ver in target_versions:
        print(f"Deriving curated schemas for {ver}...")
        out_dir = os.path.join(SCHEMAS_DIR, ver)
        os.makedirs(out_dir, exist_ok=True)
        
        # Canonical URL Base
        id_base = "https://raw.githubusercontent.com/remcovanmook/networkd-schema/main/schemas"

        if ver == BASE_VERSION:
            # For base version, load, update ID, and save (instead of just copy)
            import json
            for f in FILES:
                src = os.path.join(CURATED_BASE_DIR, f"{f}.{ver}.schema.json")
                dst = os.path.join(out_dir, f"{f}.schema.json")
                
                # Construct ID: .../schemas/v257/systemd.network.schema.json
                # The filename in repo is {f}.schema.json (no version)
                canonical_id = f"{id_base}/{ver}/{f}.schema.json"
                
                with open(src, 'r') as fh:
                    data = json.load(fh)
                
                data['$id'] = canonical_id
                
                with open(dst, 'w') as fh:
                    json.dump(data, fh, indent=2)
            
        else:
            # For other versions, derive
            for f in FILES:
                curated_base = os.path.join(CURATED_BASE_DIR, f"{f}.{BASE_VERSION}.schema.json")
                generated_base = os.path.join(SRC_ORIGINAL_DIR, BASE_VERSION, f"{f}.{BASE_VERSION}.schema.json")
                generated_target = os.path.join(SRC_ORIGINAL_DIR, ver, f"{f}.{ver}.schema.json")
                out_file = os.path.join(out_dir, f"{f}.schema.json")
                
                canonical_id = f"{id_base}/{ver}/{f}.schema.json"
                
                cmd = [
                    python_cmd, "bin/derive_schema_version.py",
                    "--curated-base", curated_base,
                    "--generated-base", generated_base,
                    "--generated-target", generated_target,
                    "--out", out_file,
                    "--id-url", canonical_id
                ]
                if args.force:
                    cmd.append("--force")
                run_command(cmd)
            
        # 3. Validate Generated Schemas
        print(f"Validating schemas for {ver}...")
        built_files = [os.path.join(out_dir, f"{f}.schema.json") for f in FILES]
        run_command([python_cmd, "bin/validate_schema.py"] + built_files)

    print("\nBuild Complete!")

if __name__ == "__main__":
    main()
