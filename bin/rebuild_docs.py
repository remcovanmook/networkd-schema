#!/usr/bin/env python3
import os
import shutil
import subprocess
import glob
import argparse

def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force rebuild")
    args = parser.parse_args()

    # 1. Clean and Prepare Output Directory
    # We removed rmtree to allow incremental builds (atomic updates)
    # If user wants clean build, they can rm -rf docs/html manually for now, or we rely on overwrites.
    # if os.path.exists("docs/html") and args.force:
    #     shutil.rmtree("docs/html")
    
    os.makedirs("docs/html", exist_ok=True)
    
    # 2. Setup CSS
    if not os.path.exists("docs/css"):
         os.makedirs("docs/css")

    # Create the link inside docs/html
    # Use copytree to avoid symlink issues in artifact upload
    # dirs_exist_ok=True allows updating existing file
    shutil.copytree("docs/css", "docs/html/css", dirs_exist_ok=True)

    # 3. Identify Versions
    # schemas/vXXX
    schema_dirs = glob.glob("schemas/v*")
    versions = [os.path.basename(d) for d in schema_dirs]
    
    # Sort Versions (Natural Sort?)
    # Basic sort might fail on v2 vs v10, but they are all vXXX.
    # Let's try to sort by integer value of version
    def version_key(v):
        try:
            return int(v[1:])
        except:
            return 0
            
    versions.sort(key=version_key)
    
    # Latest version
    latest_version = versions[-1] if versions else None
    
    print(f"Found versions: {versions}")
    print(f"Latest version: {latest_version}")
    
    # 4. Build HTML for each version
    all_versions_arg = versions + ["latest"]
    
    for ver in versions:
        print(f"Building HTML for {ver}...")
        
        # Ensure version directory exists
        ver_out_dir = os.path.join("docs/html", ver)
        os.makedirs(ver_out_dir, exist_ok=True)
        
        cmd = [
            "python3", "bin/generate_html.py",
            "--version", ver,
            "--web-schemas",
            "--out", ver_out_dir,
            "--available-versions"
        ] + all_versions_arg
        
        if args.force:
            cmd.append("--force")
            
        run_command(cmd)

        # Build Changelog (if not first version)
        # We need previous version
        if versions.index(ver) > 0:
            prev_ver = versions[versions.index(ver) - 1]
            print(f"Generating changelog for {ver} (vs {prev_ver})...")
            changelog_out = f"docs/html/{ver}/changes.html"
            cmd_cl = [
                "python3", "bin/generate_changelog.py",
                "--current", ver,
                "--prev", prev_ver,
                "--schemas-dir", "schemas",
                "--output", changelog_out
            ]
            if args.force:
                cmd_cl.append("--force")
                
            try:
                run_command(cmd_cl)
            except Exception as e:
                print(f"Failed to generate changelog for {ver}: {e}")

    # 5. Create 'latest' alias
    if latest_version:
        print(f"Creating latest alias from {latest_version}...")
        # cp -r docs/html/vXXX docs/html/latest
        shutil.copytree(f"docs/html/{latest_version}", "docs/html/latest", dirs_exist_ok=True)

    # 6. Publish Schemas (Copy) to docs/html/schemas
    print("Publishing schemas (copying)...")
    schemas_out = "docs/html/schemas"
    os.makedirs(schemas_out, exist_ok=True)
    
    for ver in versions:
        # Copy schemas/vXXX to docs/html/schemas/vXXX
        src_dir = os.path.join("schemas", ver)
        dst_dir = os.path.join(schemas_out, ver)
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            
    # Also for latest schema
    if latest_version:
        latest_schema_dir = os.path.join(schemas_out, "latest")
        # if os.path.exists(latest_schema_dir):
        #    shutil.rmtree(latest_schema_dir)
        # Copy from schemas/latest_version
        src_dir = os.path.join("schemas", latest_version)
        shutil.copytree(src_dir, latest_schema_dir, dirs_exist_ok=True)

    # 7. Generate Landing Page
    print("Generating landing page...")
    cmd_index = ["python3", "bin/generate_index.py", "--out", "docs/html", "--versions"] + versions
    run_command(cmd_index)

    print("Documentation Rebuild Complete.")

if __name__ == "__main__":
    main()
