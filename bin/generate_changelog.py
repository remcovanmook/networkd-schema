import os
import json
import argparse
import glob

def load_schema(version_dir, schema_name):
    """Loads a specific schema file from a version directory."""
    path = os.path.join(version_dir, f"{schema_name}.schema.json")
    if not os.path.exists(path):
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
    
    changes = {}
    
    for fname in files:
        # Schema name mapping
        sname = fname
        if fname == "systemd.networkd.conf": sname = "systemd.networkd.conf"
        
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

def generate_html_page(changes, current_ver, prev_ver):
    # Sidebar generation
    sidebar_html = f"""
    <div id="sidebar">
        <div class="sidebar-header">
             <h3><a href="index.html" style="color:var(--heading-color);">Documentation</a></h3>
             <div class="sidebar-links" style="padding: 0 20px; margin-top: 10px; font-size: 0.9em;">
                 <a href="index.html">Index</a> &middot; <a href="types.html">Types</a> 
                 &middot; <span style="color:var(--heading-color); font-weight:bold;">Changes</span>
             </div>
             <p style="color:var(--meta-color); font-size:0.8em; margin-bottom:20px;">Version {current_ver}</p>
             <h2>Changes</h2>
        </div>
        <div class="sidebar-content">
            <ul>
                <li><a href="#summary">Summary</a></li>
    """
    
    doc_links = []
    for doc in changes.keys():
        if any(changes[doc].values()):
            doc_links.append(f'<li><a href="#{doc}">{doc}</a></li>')
            
    sidebar_html += "".join(doc_links)
    sidebar_html += """
            </ul>
        </div>
    </div>
    """

    content_html = []
    content_html.append(f'<div class="changes-block">')
    content_html.append(f'<h2 id="summary">Changes from {prev_ver} to {current_ver}</h2>')
    
    has_changes = False
    
    for doc, doc_changes in changes.items():
        if not any(doc_changes.values()):
            continue
            
        has_changes = True
        content_html.append(f'<div id="{doc}" class="doc-changes" style="margin-bottom: 40px;">')
        content_html.append(f'<h3 style="border-bottom: 1px dashed var(--border-color); padding-bottom: 5px;">{doc}</h3>')
        
        if doc_changes['added']:
            content_html.append(f'<h4 class="added" style="color:var(--accent-color);">Added</h4><ul style="list-style-type: none; padding-left: 0;">')
            
            # Map doc name to HTML filename
            html_map = {
                "systemd.network": "systemd.network.html",
                "systemd.netdev": "systemd.netdev.html",
                "systemd.link": "systemd.link.html",
                "systemd.networkd.conf": "networkd.conf.html"
            }
            target_file = html_map.get(doc, f"{doc}.html")
            
            for item in doc_changes['added']:
                 # Item is Section.Option
                 # Display as [Section] - Option
                 parts = item.split('.', 1)
                 if len(parts) == 2:
                     anchor = f"{parts[0]}-{parts[1]}"
                     link = f"{target_file}#{anchor}"
                     display_name = f"<code>[{parts[0]}] - {parts[1]}</code>"
                     content_html.append(f'<li style="margin-bottom: 5px; padding-left: 20px; position: relative;"><span style="position: absolute; left: 0; color: var(--accent-color);">+</span> <a href="{link}">{display_name}</a></li>')
                 else:
                     content_html.append(f'<li style="margin-bottom: 5px; padding-left: 20px; position: relative;"><span style="position: absolute; left: 0; color: var(--accent-color);">+</span> <code>{item}</code></li>')
                     
            content_html.append('</ul>')
            
        if doc_changes['deprecated']:
            content_html.append(f'<h4 class="deprecated" style="color:var(--warning-color);">Deprecated</h4><ul style="list-style-type: none; padding-left: 0;">')
            for item in doc_changes['deprecated']:
                 content_html.append(f'<li style="margin-bottom: 5px; padding-left: 20px; position: relative;"><span style="position: absolute; left: 0; color: var(--warning-color);">!</span> <code>{item}</code></li>')
            content_html.append('</ul>')
            
        if doc_changes['removed']:
            content_html.append(f'<h4 class="removed" style="color:#da3633;">Removed</h4><ul style="list-style-type: none; padding-left: 0;">')
            for item in doc_changes['removed']:
                 content_html.append(f'<li style="margin-bottom: 5px; padding-left: 20px; position: relative;"><span style="position: absolute; left: 0; color: #da3633;">-</span> <code>{item}</code></li>')
            content_html.append('</ul>')
            
        content_html.append('</div>')
        
    if not has_changes:
        content_html.append('<p>No schema changes detected.</p>')
        
    content_html.append('</div>')

    full_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Changes {current_ver} vs {prev_ver}</title>
    <link rel="stylesheet" href="../css/style.css">
</head>
<body>
    {sidebar_html}
    <div id="content">
        <h1>Changelog <small style="color: var(--meta-color)">{prev_ver} &rarr; {current_ver}</small></h1>
        { "".join(content_html) }
    </div>
</body>
</html>
"""
    return full_html

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", required=True)
    parser.add_argument("--prev", required=True)
    parser.add_argument("--schemas-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true", help="Force overwrite")
    args = parser.parse_args()
    
    curr_dir = os.path.join(args.schemas_dir, args.current)
    prev_dir = os.path.join(args.schemas_dir, args.prev)
    
    if not os.path.exists(curr_dir) or not os.path.exists(prev_dir):
        print(f"Skipping changelog {args.current} vs {args.prev}: Directories not found.")
        return

    changes = compare_versions(prev_dir, curr_dir)
    html = generate_html_page(changes, args.current, args.prev)
    
    write = True
    if not args.force and os.path.exists(args.output):
        try:
           with open(args.output, 'r') as f:
               if f.read() == html:
                   write = False
                   print(f"Skipping {args.output} (unchanged)")
        except: pass
        
    if write:
        with open(args.output, 'w') as f:
            f.write(html)
        print(f"Generated {args.output}")

if __name__ == "__main__":
    main()
