import json
import os
import glob
import urllib.parse
import re

URL_BASE = "https://remcovanmook.github.io/networkd-schema"
VERSION = "v257"

def migrate_file(path):
    with open(path, 'r') as f:
        data = json.load(f)
    
    modified = False
    
    def update_links(obj):
        nonlocal modified
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "documentation" and isinstance(v, str):
                    if "freedesktop.org" in v:
                        # Parse old URL
                        # Example: .../systemd.network.html#%5BMatch%5D%20Section%20Options
                        parts = v.split('#')
                        base_url = parts[0]
                        anchor = parts[1] if len(parts) > 1 else ""
                        
                        # Extract filename
                        filename = base_url.split('/')[-1]
                        
                        # Extract Section
                        # Decode anchor: %5BMatch%5D%20Section%20Options -> [Match] Section Options
                        decoded_anchor = urllib.parse.unquote(anchor)
                        match = re.search(r'\[(.*?)\]', decoded_anchor)
                        
                        new_anchor = ""
                        if match:
                            section = match.group(1)
                            new_anchor = f"#section-{section}"
                        else:
                            # Fallback?
                            print(f"Warning: Could not parse anchor '{decoded_anchor}' in {v}")
                            new_anchor = f"#{anchor}" # Keep generic?
                            
                        new_url = f"{URL_BASE}/{VERSION}/{filename}{new_anchor}"
                        
                        if obj[k] != new_url:
                            obj[k] = new_url
                            modified = True
                            
                elif isinstance(v, (dict, list)):
                    update_links(v)
                    
        elif isinstance(obj, list):
            for item in obj:
                update_links(item)

    update_links(data)
    
    if modified:
        print(f"Updating {path}")
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        print(f"No changes for {path}")

def main():
    files = glob.glob(f"curated/{VERSION}/*.json")
    for f in files:
        migrate_file(f)

if __name__ == "__main__":
    main()
