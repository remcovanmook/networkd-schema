#!/usr/bin/env python3
import os
import sys
import json
import re

# Add current directory to path to import ini2json
sys.path.append(os.path.dirname(__file__))
import ini2json

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(BASE_DIR, 'samples')
# We use v257 schema as the source of truth for version_added
SCHEMAS_DIR = os.path.join(BASE_DIR, 'schemas', 'v257')

def load_schema(name):
    # Handle specific mapping if needed (networkd.conf -> systemd.networkd.conf)
    # But for samples we mostly care about network, netdev, link
    fname = f'systemd.{name}.schema.json'
    path = os.path.join(SCHEMAS_DIR, fname)
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)

SCHEMAS = {
    'network': load_schema('network'),
    'netdev': load_schema('netdev'),
    'link': load_schema('link')
}

def get_property_version(section_name, key, schema):
    """
    Finds the version_added for a key in a section.
    """
    if not schema: return None
    
    # 1. Find section schema
    sec_schema = schema.get('properties', {}).get(section_name)
    if not sec_schema:
        return None
        
    # Handle OneOf wrapper for sections
    if 'oneOf' in sec_schema:
        for opt in sec_schema['oneOf']:
            if opt.get('type') == 'object':
                 sec_schema = opt
                 break
            if opt.get('type') == 'array' and opt.get('items', {}).get('type') == 'object':
                 sec_schema = opt['items']
                 break
                 
    prop_schema = sec_schema.get('properties', {}).get(key)
    if not prop_schema:
        return None
        
    # Check directly on property first
    if 'version_added' in prop_schema:
        return prop_schema['version_added']
        
    # Start resolving refs to find it deeper? 
    # Usually version_added is on the property definition itself in the section, 
    # not on the type definition (which might be shared and old).
    return None

def process_file(path):
    ext = os.path.splitext(path)[1]
    if ext not in ['.network', '.netdev', '.link']:
        return

    type_key = ext[1:] # network, netdev, link
    schema = SCHEMAS.get(type_key)
    if not schema:
        print(f"No schema found for {ext}")
        return

    with open(path, 'r') as f:
        content = f.read()

    # Parse INI
    parsed_sections = ini2json.parse_ini(content)
    
    max_version = 0
    reasons = []

    for sec in parsed_sections:
        sec_name = sec['name']
        for key in sec['props']:
            v_str = get_property_version(sec_name, key, schema)
            if v_str:
                try:
                    v = int(v_str)
                    if v > max_version:
                        max_version = v
                except ValueError:
                    pass
    
    # Check if we found a version
    if max_version > 0:
        print(f"{os.path.basename(path)}: matches v{max_version}")
        annotate_file(path, max_version)
    else:
        print(f"{os.path.basename(path)}: No specific version requirement found (or base support).")

def annotate_file(path, version):
    with open(path, 'r') as f:
        lines = f.readlines()
        
    # Check if already annotated
    existing_idx = -1
    for i, line in enumerate(lines[:10]): # Check header
        if line.strip().startswith("# Minimum Version:"):
            existing_idx = i
            break
            
    ver_string = f"# Minimum Version: systemd v{version}\n"
    
    if existing_idx != -1:
        # Update existing
        current = lines[existing_idx]
        if current != ver_string:
            lines[existing_idx] = ver_string
            write_back(path, lines)
    else:
        # Insert new
        # Strategy: Find first non-shebang line. 
        # If first line is shebang, insert after.
        # If first line is comment starting with # /path/to/file (my convention), insert after that.
        
        insert_pos = 0
        if lines and lines[0].startswith('#!'):
            insert_pos += 1
            
        # Check for my nice header comments
        # # /etc/systemd/...
        # # TITLE
        # #
        # Insert after the empty line after header block? Or just after the first filename line?
        
        # Let's put it fairly high up.
        if len(lines) > insert_pos and lines[insert_pos].strip().startswith("# /"):
             insert_pos += 1
        
        lines.insert(insert_pos, ver_string)
        write_back(path, lines)

def write_back(path, lines):
    with open(path, 'w') as f:
        f.writelines(lines)

def main():
    if not os.path.exists(SAMPLES_DIR):
        print("Samples dir not found")
        return

    for root, dirs, files in os.walk(SAMPLES_DIR):
        for f in files:
            process_file(os.path.join(root, f))

if __name__ == "__main__":
    main()
