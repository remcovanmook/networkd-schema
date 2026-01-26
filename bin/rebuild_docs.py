#!/usr/bin/env python3
import os
import shutil
import subprocess
import glob

def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

def main():
    # 1. Clean and Prepare Output Directory
    if os.path.exists("docs/html"):
        shutil.rmtree("docs/html")
    os.makedirs("docs/html")
    
    # 2. Setup CSS
    # User requirement: CSS in docs/css, not docs/html/css
    # But deployment artifact comes from docs/html.
    # So we symlink docs/css -> docs/html/css to include it in the upload without duplication.
    # Relative path: ../css relative to docs/html/css
    
    # Ensure docs/css exists (it should, we moved it there)
    if not os.path.exists("docs/css"):
         os.makedirs("docs/css")

    # Create the link inside docs/html
    os.symlink("../css", "docs/html/css")

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
        cmd = [
            "python3", "bin/generate_html.py",
            "--version", ver,
            "--web-schemas",
            "--available-versions"
        ] + all_versions_arg
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
            try:
                run_command(cmd_cl)
            except Exception as e:
                print(f"Failed to generate changelog for {ver}: {e}")

    # 5. Create 'latest' alias
    if latest_version:
        print(f"Creating latest alias from {latest_version}...")
        # cp -r docs/html/vXXX docs/html/latest
        shutil.copytree(f"docs/html/{latest_version}", "docs/html/latest")

    # 6. Publish Schemas (Symlinks) to docs/html/schemas
    print("Publishing schemas (symlinking)...")
    schemas_out = "docs/html/schemas"
    os.makedirs(schemas_out, exist_ok=True)
    
    for ver in versions:
        ver_dir = os.path.join(schemas_out, ver)
        os.makedirs(ver_dir, exist_ok=True)
        
        # Symlink JSON files from ../../../schemas/vXXX/*.json to docs/html/schemas/vXXX/
        # Relative path from docs/html/schemas/vXXX to schemas/vXXX
        # is ../../../schemas/vXXX
        
        # We need to glob the source files
        source_files = glob.glob(f"schemas/{ver}/*.json")
        for src in source_files:
            fname = os.path.basename(src)
            # Link target (relative)
            link_target = os.path.join("../../../", src) 
            link_name = os.path.join(ver_dir, fname)
            if os.path.exists(link_name):
                os.remove(link_name)
            os.symlink(link_target, link_name)
            
    # Also for latest schema
    if latest_version:
        latest_schema_dir = os.path.join(schemas_out, "latest")
        os.makedirs(latest_schema_dir, exist_ok=True)
        source_files = glob.glob(f"schemas/{latest_version}/*.json")
        for src in source_files:
            fname = os.path.basename(src)
            link_target = os.path.join("../../../", src)
            link_name = os.path.join(latest_schema_dir, fname)
            if os.path.exists(link_name):
                os.remove(link_name)
            os.symlink(link_target, link_name)

    # 7. Generate Landing Page
    print("Generating landing page...")
    cmd_index = ["python3", "bin/generate_index.py", "--out", "docs/html", "--versions"] + versions
    run_command(cmd_index)

    print("Documentation Rebuild Complete.")

if __name__ == "__main__":
    main()
