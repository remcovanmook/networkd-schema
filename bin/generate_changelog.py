import os
import json
import argparse
import glob

def load_schema(version_dir, schema_name):
    """Loads a specific schema file from a version directory."""
    # Pattern: schemas/v259/systemd.network.schema.json
    # Or just schemas/v259/*.schema.json and map by name
    path = os.path.join(version_dir, f"{schema_name}.schema.json")
    if not os.path.exists(path):
         # Try fallback if name differs slightly or just return empty
         return {}
    
    with open(path, 'r') as f:
        return json.load(f)

def flatten_properties(schema, definitions=None):
    """
    Returns a flat dict of "Section.Option" -> PropertySchema.
    Simplified flattener that resolves oneOf sections.
    """
    options = {}
    if definitions is None:
        definitions = schema.get('definitions', {})

    # Helper to resolve $ref
    def resolve_ref(node):
        if '$ref' in node:
            ref = node['$ref'].split('/')[-1]
            if ref in definitions:
                return resolve_ref(definitions[ref])
        return node

    # Iterate sections
    props = schema.get('properties', {})
    for section_name, section_node in props.items():
        # Resolve section if it's a ref or oneOf wrapper
        section_node = resolve_ref(section_node)
        
        if 'oneOf' in section_node:
            for variant in section_node['oneOf']:
                if variant.get('type') == 'object':
                    section_node = variant
                    break
        
        sec_props = section_node.get('properties', {})
        for opt_name, opt_node in sec_props.items():
            key = f"{section_name}.{opt_name}"
            options[key] = resolve_ref(opt_node)
            
    return options

def compare_versions(prev_dir, curr_dir):
    """
    Compares schemas in two directories.
    Returns dict of changes: { 'systemd.network': { 'added': [], 'removed': [], 'deprecated': [] } }
    """
    files = ["systemd.network", "systemd.netdev", "systemd.link", "systemd.networkd.conf"]
    # adjustments for naming conventions if needed
    
    changes = {}
    
    for fname in files:
        # Schema name mapping
        sname = fname
        if fname == "systemd.networkd.conf": sname = "systemd.networkd.conf" # matches file
        
        # In schemas dir, filenames are like systemd.network.schema.json
        # But wait, earlier I saw they might just be systemd.network.schema.json
        # Let's try to load
        
        prev_schema = load_schema(prev_dir, sname)
        curr_schema = load_schema(curr_dir, sname)
        
        if not prev_schema and not curr_schema:
            continue
            
        changes[fname] = {'added': [], 'removed': [], 'deprecated': []}
        
        prev_opts = flatten_properties(prev_schema) if prev_schema else {}
        curr_opts = flatten_properties(curr_schema) if curr_schema else {}
        
        all_keys = set(prev_opts.keys()) | set(curr_opts.keys())
        
        for key in sorted(all_keys):
            if key not in prev_opts:
                changes[fname]['added'].append(key)
            elif key not in curr_opts:
                changes[fname]['removed'].append(key)
            else:
                # Check deprecation
                is_dep_curr = curr_opts[key].get('deprecated', False)
                is_dep_prev = prev_opts[key].get('deprecated', False)
                
                if is_dep_curr and not is_dep_prev:
                     changes[fname]['deprecated'].append(key)
                     
    return changes

def generate_html_fragment(changes, current_ver, prev_ver):
    html = []
    html.append(f'<div class="changes-block">')
    html.append(f'<h3>Changes from {prev_ver} to {current_ver}</h3>')
    
    has_changes = False
    
    for doc, doc_changes in changes.items():
        if not any(doc_changes.values()):
            continue
            
        has_changes = True
        html.append(f'<div class="doc-changes">')
        html.append(f'<h4>{doc}</h4>')
        
        if doc_changes['added']:
            html.append(f'<h5 class="added">Added</h5><ul>')
            for item in doc_changes['added']:
                 html.append(f'<li><code>{item}</code></li>')
            html.append('</ul>')
            
        if doc_changes['deprecated']:
            html.append(f'<h5 class="deprecated">Deprecated</h5><ul>')
            for item in doc_changes['deprecated']:
                 html.append(f'<li><code>{item}</code></li>')
            html.append('</ul>')
            
        if doc_changes['removed']:
            html.append(f'<h5 class="removed">Removed</h5><ul>')
            for item in doc_changes['removed']:
                 html.append(f'<li><code>{item}</code></li>')
            html.append('</ul>')
            
        html.append('</div>')
        
    if not has_changes:
        html.append('<p>No schema changes detected.</p>')
        
    html.append('</div>')
    return "\n".join(html)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", required=True)
    parser.add_argument("--prev", required=True)
    parser.add_argument("--schemas-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    curr_dir = os.path.join(args.schemas_dir, args.current)
    prev_dir = os.path.join(args.schemas_dir, args.prev)
    
    if not os.path.exists(curr_dir) or not os.path.exists(prev_dir):
        print(f"Skipping changelog {args.current} vs {args.prev}: Directories not found.")
        return

    changes = compare_versions(prev_dir, curr_dir)
    html = generate_html_fragment(changes, args.current, args.prev)
    
    with open(args.output, 'w') as f:
        f.write(html)
    print(f"Generated {args.output}")

if __name__ == "__main__":
    main()
