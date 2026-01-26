import os
import re
import json
import argparse
import html
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

# --- Constants ---

CSS_STYLES = """
:root {
    --bg-color: #0f111a;
    --text-color: #c9d1d9;
    --heading-color: #58a6ff;
    --link-color: #58a6ff;
    --code-bg: #161b22;
    --border-color: #30363d;
    --accent-color: #238636;
    --meta-color: #8b949e;
    --warning-color: #d29922;
    --font-main: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    --font-mono: 'Consolas', 'Monaco', 'Courier New', monospace;
}

body {
    background-color: var(--bg-color);
    color: var(--text-color);
    font-family: var(--font-main);
    line-height: 1.6;
    margin: 0;
    display: flex;
    height: 100vh;
    overflow: hidden;
}

a { color: var(--link-color); text-decoration: none; }
a:hover { text-decoration: underline; }
code { font-family: var(--font-mono); background: var(--code-bg); padding: 0.2em 0.4em; border-radius: 4px; font-size: 0.9em; }
pre { background: var(--code-bg); padding: 1em; border-radius: 6px; overflow-x: auto; border: 1px solid var(--border-color); }
pre code { background: none; padding: 0; }

/* Sidebar */
#sidebar {
    width: 300px;
    background: #0d1117;
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
}
.sidebar-header {
    padding: 20px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
}
.sidebar-content {
    overflow-y: auto;
    padding: 20px;
    flex-grow: 1;
}
.version-selector {
    width: 100%;
    background: var(--code-bg);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    padding: 8px;
    border-radius: 6px;
    margin-top: 10px;
    font-family: var(--font-main);
    cursor: pointer;
}
#sidebar h2 { font-size: 1.2em; margin-top: 0; color: var(--text-color); margin-bottom: 0; }
#sidebar ul { list-style: none; padding: 0; margin: 0; }
#sidebar li { margin-bottom: 8px; }
#sidebar li a { display: block; color: var(--meta-color); padding: 4px 8px; border-radius: 4px; transition: all 0.2s; }
#sidebar li a:hover, #sidebar li a.active { background: var(--code-bg); color: var(--heading-color); }
#sidebar .sub-menu { margin-left: 15px; border-left: 1px solid var(--border-color); padding-left: 10px; margin-top: 5px; font-size: 0.9em; }

summary { cursor: pointer; color: var(--text-color); font-weight: 600; padding: 5px 0; user-select: none; }
summary:hover { color: var(--heading-color); }
summary a { display: inline-block !important; width: auto !important; }
details > summary { list-style: none; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: '▶'; display: inline-block; margin-right: 8px; font-size: 0.8em; transition: transform 0.2s; }
details[open] > summary::before { transform: rotate(90deg); }

/* Anchor Links */
.anchor-link { opacity: 0; color: var(--meta-color); margin-right: 8px; text-decoration: none !important; transition: opacity 0.2s; user-select: none; }
.option-header:hover .anchor-link { opacity: 1; }
.anchor-link:hover { color: var(--link-color); }

/* Main Content */
#content {
    flex-grow: 1;
    overflow-y: auto;
    padding: 40px;
    max-width: 1000px;
}

h1, h2, h3 { color: var(--heading-color); margin-top: 1.5em; }
h1 { border-bottom: 1px solid var(--border-color); padding-bottom: 15px; margin-top: 0; }
h2 { border-bottom: 1px dashed var(--border-color); padding-bottom: 8px; }

.subcategory-header {
    margin-top: 30px;
    margin-bottom: 15px;
    font-size: 1.1em;
    color: var(--accent-color);
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 5px;
}

.nav-subcat {
    margin-top: 10px;
    margin-bottom: 5px;
    padding-left: 10px;
    color: var(--accent-color);
    font-weight: 600;
    font-size: 0.8em;
    text-transform: uppercase;
}

/* Option Blocks */
.option-block {
    background: #151920;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-bottom: 25px;
    padding: 20px;
    position: relative;
    transition: transform 0.2s, box-shadow 0.2s;
}
.option-block:hover {
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    border-color: #58a6ff;
}
.option-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-color);
}
.option-title {
    font-family: var(--font-mono);
    font-size: 1.2em;
    font-weight: bold;
    color: #e2b93d;
}
.option-meta {
    display: flex;
    gap: 10px;
    font-size: 0.85em;
}
.badge {
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.75em;
    letter-spacing: 0.5px;
}
.badge-type { background: #1f6feb; color: #fff; }
.badge-version { background: #238636; color: #fff; }
.badge-mandatory { background: #da3633; color: #fff; }
.badge-default { background: #6e7681; color: #fff; }
.badge-schema { background: #6f42c1; color: #fff; text-decoration: none; }
.badge-deprecated { background: #9e6a03; color: #fff; }

.option-desc { color: var(--text-color); }
.option-desc p { margin-top: 0; }

/* Tables */
table { width: 100%; border-collapse: collapse; margin: 20px 0; background: #161b22; border-radius: 6px; overflow: hidden; }
th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border-color); }
th { background: #21262d; font-weight: 600; color: var(--heading-color); }
tr:last-child td { border-bottom: none; }

/* Responsive */
@media (max-width: 800px) {
    body { flex-direction: column; overflow: auto; }
    #sidebar { width: 100%; height: auto; border-right: none; border-bottom: 1px solid var(--border-color); }
    #content { padding: 20px; overflow: visible; }
}
"""

FILES = [
    "systemd.network",
    "systemd.netdev",
    "systemd.link",
    "networkd.conf"
]

NAMESPACE = {'xi': 'http://www.w3.org/2001/XInclude'}

# --- Helpers ---

def get_text(elem):
    if elem is None:
        return ""
    text = html.escape(elem.text or "")
    for child in elem:
        # Recursive rendering? For simple text extraction we might skip complex tags
        # But for HTML we generally want to preserve structure or render it.
        # This simple helper is just for basic text extraction if needed.
        pass
    return text

def render_docbook_content(elem, context_version):
    """
    Recursively renders DocBook XML elements into HTML.
    """
    if elem is None:
        return ""
    
    out = []
    
    # Text before children
    if elem.text:
        out.append(html.escape(elem.text))
        
    for child in elem:
        tag = child.tag.split('}')[-1] # Strip namespace
        
        content = render_docbook_content(child, context_version)
        
        if tag == 'para':
            out.append(f'<p>{content}</p>')
        elif tag == 'filename':
            out.append(f'<code>{content}</code>')
        elif tag == 'literal':
            out.append(f'<code>{content}</code>')
        elif tag == 'varname':
            out.append(f'<code class="varname">{content}</code>')
        elif tag == 'command':
            out.append(f'<code class="command">{content}</code>')
        elif tag == 'constant':
            out.append(f'<code class="constant">{content}</code>')
        elif tag == 'programlisting':
            out.append(f'<pre><code>{content}</code></pre>')
        elif tag == 'listitem':
            out.append(f'<li>{content}</li>')
        elif tag == 'itemizedlist':
            out.append(f'<ul>{content}</ul>')
        elif tag == 'variablelist':
            # Variable lists are usually option definitions, which we might handle specifically
            # But inside a para they might be nested.
            out.append(f'<dl>{content}</dl>')
        elif tag == 'varlistentry':
            # This is custom handled in main loop usually, but if nested:
            term = child.find(".//term") # Basic find, namespaces might break
            listitem = child.find(".//listitem")
            # This logic is weak for general docbook, but sufficient for snippets
            out.append(f'<dt>{render_docbook_content(term, context_version)}</dt>')
            out.append(f'<dd>{render_docbook_content(listitem, context_version)}</dd>')

        elif tag == 'ulink':
            url = child.get('url', '#')
            out.append(f'<a href="{url}" target="_blank">{content}</a>')
        elif tag == 'citerefentry':
            # Cross reference
            title_elem = child.find(".//refentrytitle") # strip namespace
            if title_elem is None:
                # Try with namespace
                title_elem = child.find(f".//{{*}}refentrytitle")
            
            ref_title = title_elem.text if title_elem is not None else "Unknown"
            
            if ref_title in FILES:
                out.append(f'<a href="{ref_title}.html">{ref_title}</a>')
            else:
                out.append(f'<a href="https://www.freedesktop.org/software/systemd/man/latest/{ref_title}.html" target="_blank" class="external-link">{ref_title}</a>')

        elif tag == 'include':
            # Recursively resolving XInclude if we encounter it in content
            pass # We handle main includes at higher level, but sometimes they are inline
        
        else:
            # Default pass-through for unknown tags, just content
            out.append(f'<span class="docbook-{tag}">{content}</span>')

        # Text after child (tail)
        if child.tail:
            out.append(html.escape(child.tail))
            
    return "".join(out)


def resolve_xincludes(element, base_path, known_xml_files):
    """
    Recursively resolve xi:include tags.
    """
    # Create a list of children to iterate over to allow modification
    children = list(element)
    
    for i, child in enumerate(children):
        if child.tag.endswith('include'):
            href = child.get('href')
            xpointer = child.get('xpointer')
            
            # If it's version-info, we might want to just parse the version number
            # But here we want the content.
            
            if href in known_xml_files:
                target_path = os.path.join(base_path, href)
                if os.path.exists(target_path):
                    try:
                        # Parse the included file
                        parser = ET.XMLParser(encoding="utf-8")
                        inc_tree = ET.parse(target_path, parser=parser)
                        inc_root = inc_tree.getroot()
                        
                        # Find the element pointed to by xpointer
                        # Simple xpointer support (ID lookup)
                        if xpointer:
                            # Assuming xpointer is just an ID for now
                            target_elem = None
                            for elem in inc_root.iter():
                                if elem.get('id') == xpointer:
                                    target_elem = elem
                                    break
                                # Also check for simple exact matches of terms if it's a list entry
                                # But standard DocBook uses IDs. 
                                
                            if target_elem is not None:
                                # Replace the include tag with the content of the target element
                                # Caution: we can't easily replace "in place" in ElementTree during iteration easily
                                # But we can append content.
                                
                                # Actually, usually we replace the <xi:include> node with the *nodes* from the result.
                                # This is hard in standard ElementTree.
                                # Strategy: Gather all children, including expanded ones, and rebuild parent.
                                pass 
                            else:
                                 # Fallback: if no ID found, maybe it's a version pointer
                                 pass
                        else:
                            # Include whole root?
                            pass
                    except Exception as e:
                        print(f"Warning: Failed to process include {href}: {e}")
            
        else:
            resolve_xincludes(child, base_path, known_xml_files)


# Simplified XInclude resolver that specifically targets our use case (flattening options)
def flatten_sections(root_element, base_path):
    """
    Returns a dictionary of Section -> {OptionName -> Element}
    Resolving Includes on the fly.
    """
    sections = {} # 'Network': {'Address': elem, ...}
    
    # Find all refsect1
    # Handle namespaces
    # DocBook standard usually no namespace or custom. The files have xmlns:xi
    
    # We iterate manually to handle includes
    
    def process_node(node, current_section=None):
        tag = node.tag.split('}')[-1]
        
        if tag == 'refsect1':
            # Check title
            title = node.find("{*}title")
            if title is None: title = node.find("title") 
            
            if title is not None:
                title_text = "".join(title.itertext()).strip()
                match = re.search(r'\[(.*?)\]', title_text)
                if match:
                    current_section = match.group(1)
                    if current_section not in sections:
                        sections[current_section] = [] # List of entries (allowing duplicates for merging)
        
        elif tag == 'varlistentry':
            if current_section:
                sections[current_section].append(node)
                
        elif tag == 'include': # xi:include
            href = node.get('href')
            xpointer = node.get('xpointer')
            
            if href and os.path.exists(os.path.join(base_path, href)):
                try:
                    inc_tree = ET.parse(os.path.join(base_path, href))
                    inc_root = inc_tree.getroot()
                    
                    found = []
                    if xpointer:
                        # Find by ID usually, but systemd uses xpointer to point to specific terms/lists sometimes
                        # We try to find specific ID
                        for el in inc_root.iter():
                           if el.get('id') == xpointer:
                               found.append(el)
                               break
                           
                        # Heuristic: if xpointer is like "v220", it's just version info, usually inside a para.
                        # We are looking for structure includes here.
                    else:
                        # Include all children of root if no xpointer? Or the root itself?
                        found = [inc_root]
                        
                    for f in found:
                        process_node(f, current_section)
                        
                except Exception as e:
                    print(f"Include Warning: {href} - {e}")
            return # Don't process children of include

        for child in node:
            process_node(child, current_section)

    process_node(root_element)
    return sections

def get_option_name(varlistentry):
    term = varlistentry.find(".//{*}term")
    if term is None: return None
    # Usually <varname>Name=</varname>
    raw = "".join(term.itertext()).strip()
    return raw.split('=')[0].strip()

def get_description(varlistentry, version_context):
    listitem = varlistentry.find(".//{*}listitem")
    if listitem is None: return ""
    return render_docbook_content(listitem, version_context)

def get_version_added(varlistentry, base_path):
    # Look for xi:include href="version-info.xml" xpointer="vXXX"
    ns = {'xi': 'http://www.w3.org/2001/XInclude'}
    includes = varlistentry.findall(".//xi:include", ns)
    for inc in includes:
        if "version-info.xml" in inc.get('href', ''):
            xp = inc.get('xpointer', '') # e.g. v220
            if xp.startswith('v'):
                return xp[1:]
    return None


# --- Main ---

def generate_page(doc_name, version, src_dir, schema_dir, output_dir, web_schemas=False, available_versions=None):
    xml_file = os.path.join(src_dir, f"{doc_name}.xml")
    
    # Determine Schema Name
    schema_name = doc_name
    if doc_name == "networkd.conf":
        # Specific mapping for this file
        schema_name = "systemd.networkd.conf"
        
    # Load JSON Schema
    # Load JSON Schema
    # UPDATED: schemas filename format {schema_name}.schema.json (no version infix in schemas/ dir)
    schema_file = os.path.join(schema_dir, f"{schema_name}.schema.json")
    if not os.path.exists(schema_file):
        print(f"Skipping {doc_name}: Schema not found at {schema_file}")
        return

    if not os.path.exists(xml_file):
        print(f"Skipping {doc_name}: Source XML missing at {xml_file}")
        return

    print(f"Processing {doc_name}...")
    
    with open(schema_file, 'r') as f:
        schema = json.load(f)
        
    # ... (rest of function until schema_url usage)
    
    # (Checking where schema_url is used, I will update that usage in a separate chunk to be safe or verify line numbers)
    # The traceback said line 644 for schema_url.
    # The function start is around 426? No, the diff block showed 426.
    
    # I will replace the START of the function here.

    
    # Load Schema
    with open(schema_file, 'r') as f:
        schema = json.load(f)
    
    # Load XML
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Extract Title and Description
    # ...
    
    # Flatten Content
    sections_xml = flatten_sections(root, src_dir)
    
    # Build HTML Content
    html_content = []
    
    # Sidebar Navigation
    nav_items = []
    
    for section_name, entries in sections_xml.items():
        if section_name not in schema['properties']:
             continue # Skip sections not in schema (e.g. legacy/internal?)
        
        section_id = f"section-{section_name}"
        nav_items.append(f'<li><details><summary><a href="#{section_id}">[{section_name}]</a></summary><ul class="sub-menu">')
        
        html_content.append(f'<div id="{section_id}" class="section-block">')
        html_content.append(f'<h2>[{section_name}] Section</h2>')
        
        section_schema = schema['properties'][section_name]
        # Handle oneOf wrapper for sections that can be repeated
        if 'oneOf' in section_schema:
             # Find the object variant
             for v in section_schema['oneOf']:
                 if v.get('type') == 'object':
                     section_schema = v
                     break
                     
        # Order by Subcategory -> Required -> Name
        
        # 1. Collect all valid options first
        options_data = [] # List of dicts
        
        props_schema_map = section_schema.get('properties', {})
        processed_options = set()
        
        for entry in entries:
            name = get_option_name(entry)
            if not name or name in processed_options: continue
            processed_options.add(name)
            
            # Lookup in schema
            prop_schema = props_schema_map.get(name)
            if not prop_schema: continue
            
            # Resolve Refs for metadata
            def resolve(s):
                if 'allOf' in s: return resolve(s['allOf'][0])
                if '$ref' in s:
                    ref = s['$ref'].split('/')[-1]
                    if ref in schema['definitions']:
                        return resolve(schema['definitions'][ref])
                return s

            res_schema = resolve(prop_schema)
            
            # Extract Metadata
            value_type = res_schema.get('type', 'string')
            if 'enum' in res_schema: value_type = "enum"
            
            is_mandatory = name in section_schema.get('required', [])
            default_val = res_schema.get('default')
            
            # Helper to get deep property even through refs for x-subcategory
            def get_deep_prop(s, key):
                if key in s: return s[key]
                if 'allOf' in s: return get_deep_prop(s['allOf'][0], key)
                if '$ref' in s:
                    ref = s['$ref'].split('/')[-1]
                    if ref in schema['definitions']:
                        return get_deep_prop(schema['definitions'][ref], key)
                return None
            
            subcategory = get_deep_prop(prop_schema, 'x-subcategory') or "General"
            
            # Override subcategory if required
            if is_mandatory:
                subcategory = "Required"
            
            version_added = prop_schema.get('version_added') 
            if not version_added:
                version_added = get_version_added(entry, src_dir)
                
            # Extract examples (prefer property level, fallback to resolved schema)
            examples = prop_schema.get('examples')
            if not examples:
                examples = res_schema.get('examples', [])
                
            # Collect Allowed Values for validation and synthetic generation
            allowed_values = set()
            has_enum_restriction = False
            
            def collect_allowed(s):
                s_res = resolve(s)
                found = False
                if 'enum' in s_res:
                    for e in s_res['enum']:
                        allowed_values.add(str(e))
                    found = True
                
                t = s_res.get('type')
                if t == 'boolean':
                    allowed_values.add('true')
                    allowed_values.add('false')
                    found = True
                
                # Recurse
                if 'oneOf' in s_res:
                    for sub in s_res['oneOf']:
                        if collect_allowed(sub): found = True
                if 'anyOf' in s_res:
                    for sub in s_res['anyOf']:
                        if collect_allowed(sub): found = True
                        
                return found

            has_enum_restriction = collect_allowed(res_schema)
            
            # Validate Examples if we have restricted values
            if has_enum_restriction and examples:
                 valid_examples = []
                 for ex in examples:
                     # Normalize boolean to string for comparison
                     ex_str = str(ex).lower() if isinstance(ex, bool) else str(ex)
                     # Case-sensitive check usually for enums? But 'true'/'false' are case-insensitive in systemd mostly,
                     # here we stick to schema strictness or loose equality.
                     # Let's try exact match in set first.
                     if ex_str in allowed_values:
                         valid_examples.append(ex)
                     # Maybe case mismatch?
                     elif value_type == 'boolean' and ex_str in allowed_values:
                          valid_examples.append(ex_str) # Normalized
                          
                 # Replace with filtered list if we are enforcing strictness
                 # User Request: "In case of an enum, only use example values from the enum accepted values."
                 examples = valid_examples

            # Synthetic Examples (if empty after filter or not present)
            if not examples:
                if has_enum_restriction:
                     # Pick from allowed values
                     # Sort for determinism
                     sorted_allowed = sorted(list(allowed_values))
                     
                     # Try to pick default if exists
                     if default_val is not None and str(default_val) in allowed_values:
                          examples.append(str(default_val))
                     
                     for val in sorted_allowed:
                         if val not in examples:
                             examples.append(val)
                             if len(examples) >= 2: break
                else:
                    # No Restriction (String, Integer w/o enum)
                    if value_type == 'integer':
                        if default_val is not None:
                             examples.append(str(default_val))
                        else:
                             examples.append("0")
                    else: # string
                        if default_val is not None:
                             examples.append(str(default_val))
                        else:
                             examples.append("SomeString")
            
            # Enforce Limits
            # Refined limit logic:
            is_simple_bool = value_type == 'boolean'
            
            if is_simple_bool:
                examples = examples[:1]
            else:
                examples = examples[:2]
                
            desc_html = get_description(entry, version)
            
            # Map type to linkable name
            type_slug = value_type
            if '$ref' in prop_schema:
                 ref_name = prop_schema['$ref'].split('/')[-1]
                 if ref_name in schema.get('definitions', {}):
                     type_slug = ref_name
                     # Use title or ref name as label
                     def_schema = schema['definitions'][ref_name]
                     value_type = def_schema.get('title', ref_name)
            elif 'format' in res_schema:
                 type_slug = res_schema['format']
                 
            # Schema Link
            # Schema Link
            # Base logic: https://github.com/remcovanmook/networkd-schema/blob/main/schemas/{version}/{schema_name}.schema.json
            # Refined: point to curated raw with text fragment
            
            # If web_schemas is True, we use a relative path to the schemas folder we deploy
            # Structure: 
            #   docs/html/v257/index.html
            #   docs/html/schemas/v257/systemd.network.schema.json
            # Relative link from html: ../../schemas/v257/systemd.network.schema.json
            if web_schemas:
                 base_url = f"../schemas/{version}/{schema_name}.schema.json"
            else:
                 # Fallback to GitHub Raw? User requested schemas in /schemas/.
                 # We assume main branch schemas structure
                 base_url = f"https://raw.githubusercontent.com/remcovanmook/networkd-schema/main/schemas/{version}/{schema_name}.schema.json"

            schema_url = f"{base_url}#:~:text=%22{name}%22"
                 
            options_data.append({
                'name': name,
                'subcategory': subcategory,
                'type': value_type,
                'type_slug': type_slug,
                'required': is_mandatory,
                'default': default_val,
                'version_added': version_added,
                'examples': examples,
                'desc_html': desc_html,
                'schema': res_schema,
                'full_schema': prop_schema,
                'schema_url': schema_url
            })
            
        # 2. Group and Sort
        # Group by subcategory
        from collections import defaultdict
        grouped = defaultdict(list)
        for opt in options_data:
            grouped[opt['subcategory']].append(opt)
            
        # Sort keys: Required first, then General, then alphabetical
        sorted_subcategories = sorted(grouped.keys())
        
        priority_order = ["Required", "General"]
        final_order = []
        
        for p in priority_order:
            if p in sorted_subcategories:
                final_order.append(p)
                sorted_subcategories.remove(p)
        
        final_order.extend(sorted_subcategories)
        sorted_subcategories = final_order
            
        for subcat in sorted_subcategories:
            group_opts = grouped[subcat]
            if not group_opts: continue
            
            # Sort: Alphabetical Name (Required already handled by group)
            # group_opts.sort(key=lambda x: x['name'])
            # User Request: Use XML order (which is preserved by default as we iterate entries)
            pass
            
            # Render Subcategory Header if meaningful?
            # Or just visual separator?
            if len(sorted_subcategories) > 1:
                # For Sidebar (now inside a UL inside details)
                # We want to insert subheaders into the nav items list?
                # The current structure append directly to nav_items
                nav_items.append(f'<li class="nav-subcat"><span>{subcat}</span></li>')
                
                # For Content
                html_content.append(f'<h3 class="subcategory-header">{subcat}</h3>')

            for opt in group_opts:
                name = opt['name']
                
                # Render Option Block
                html_content.append(f'''
                <div id="{section_name}-{name}" class="option-block">
                    <div class="option-header">
                        <div class="option-title">
                            <a href="#{section_name}-{name}" class="anchor-link">#</a>{name}
                        </div>
                        <div class="option-meta">
                            <a href="types.html#{opt['type_slug']}" class="badge badge-type">{opt['type']}</a>
                            <a href="{opt['schema_url']}" target="_blank" class="badge badge-schema">Schema</a>
                            {f'<span class="badge badge-version">v{opt["version_added"]}+</span>' if opt["version_added"] else ''}
                            {f'<span class="badge badge-mandatory">Required</span>' if opt['required'] else '<span class="badge badge-default">Optional</span>'}
                            {f'<span class="badge badge-warning">Deprecated</span>' if 'deprecated' in str(opt['full_schema']).lower() else ''}
                        </div>
                    </div>
                    <div class="option-desc">
                        {opt['desc_html']}
                    </div>
                ''')
                
                # Show allowed values (Enum)
                if 'enum' in opt['schema']:
                    html_content.append('<div class="option-values"><strong>Allowed:</strong> ')
                    html_content.append(", ".join([f'<code>{e}</code>' for e in opt['schema']['enum']]))
                    html_content.append('</div>')
                    
                # Show Default
                if opt['default'] is not None:
                     html_content.append(f'<div class="option-default" style="margin-top:10px; font-size:0.9em; color:#8b949e;"><strong>Default:</strong> <code>{opt["default"]}</code></div>')
                     
                # Show Examples
                if opt['examples']:
                    html_content.append('<div class="option-examples" style="margin-top:10px;">')
                    html_content.append('<strong>Examples:</strong>')
                    html_content.append('<pre><code>')
                    for ex in opt['examples']:
                        html_content.append(f'{name}={ex}\n')
                    html_content.append('</code></pre></div>')

                html_content.append('</div>')
                
                nav_items.append(f'<li><a href="#{section_name}-{name}" style="font-size: 0.9em; margin-left: 20px;">{name}</a></li>')

        html_content.append('</div>') 
        nav_items.append('</ul></details></li>')

    # Complete HTML Page
    # Build Version Options
    version_options_html = ""
    if available_versions:
        # Sort: move 'latest' to top, then descending
        versions = list(available_versions)
        if 'latest' in versions:
             versions.remove('latest')
        versions.sort(reverse=True)
        if available_versions and 'latest' in available_versions:
             versions.insert(0, 'latest')

        for v in versions:
            selected = 'selected' if v == version else ''
            # Link to same page in other version
            val = f"../{v}/{doc_name}.html"
            version_options_html += f'<option value="{val}" {selected}>{v}</option>'

    sidebar_html = f"""
    <div id="sidebar">
        <div class="sidebar-header">
             <h3><a href="index.html" style="color:var(--heading-color);">Documentation</a></h3>
             {f'''<select class="version-selector" onchange="window.location.href=this.value;">
                {version_options_html}
            </select>''' if available_versions else f'<p style="color:var(--meta-color); font-size:0.8em; margin-bottom:20px;">Version {version}</p>'}
             <h2>{doc_name}</h2>
        </div>
        <div class="sidebar-content">
            <ul>
                {"".join(nav_items)}
            </ul>
        </div>
    </div>
    """

    html_header = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Systemd {doc_name} (v{version})</title>
    <link rel="stylesheet" href="style.css">
    <style>
        .docbook-para {{ margin-bottom: 1em; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div id="content">
        <h1>{doc_name} <span style="font-size:0.5em; color:var(--meta-color); font-weight:normal;">/ {version}</span></h1>
        { "".join(html_content) }
    </div>
"""

    html_scripts = """
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const sidebarLinks = document.querySelectorAll('#sidebar a');
            const sections = document.querySelectorAll('.section-block, .option-block');
            const sidebar = document.getElementById('sidebar');
            
            // Map IDs to sidebar links
            const linkMap = new Map();
            sidebarLinks.forEach(link => {
                const href = link.getAttribute('href');
                if (href && href.startsWith('#')) {
                    linkMap.set(href.substring(1), link);
                }
            });

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const id = entry.target.id;
                        const link = linkMap.get(id);
                        if (link) {
                            // Remove active from all
                            sidebarLinks.forEach(l => l.classList.remove('active'));
                            
                            // Add active to current
                            link.classList.add('active');
                            
                            // Open parent details
                            let parent = link.parentElement;
                            while (parent) {
                                if (parent.tagName === 'DETAILS') {
                                    parent.open = true;
                                }
                                parent = parent.parentElement;
                            }
                            
                            // Scroll sidebar to keep active link in view
                            const rect = link.getBoundingClientRect();
                            const sidebarRect = sidebar.getBoundingClientRect();
                            if (rect.top < sidebarRect.top || rect.bottom > sidebarRect.bottom) {
                                link.scrollIntoView({ block: 'center', behavior: 'smooth' });
                            }
                        }
                    }
                });
            }, {
                root: document.getElementById('content'),
                threshold: 0.1,
                rootMargin: "-40% 0px -40% 0px" // Trigger when element is in middle of screen
            });

            sections.forEach(section => observer.observe(section));
        });
    </script>
</body>
</html>
    """

    full_html = html_header + html_scripts
    
    with open(os.path.join(output_dir, f"{doc_name}.html"), 'w') as f:
        f.write(full_html)
    print(f" -> Generated {doc_name}.html")


def generate_types_page(output_dir, version, schema_dir):
    # Load schema for definitions
    # UPDATED: schemas filename format
    schema_file = os.path.join(schema_dir, "systemd.network.schema.json")
    if not os.path.exists(schema_file):
        print(f"Warning: Schema file not found for types generation: {schema_file}")
        return

    with open(schema_file, 'r') as f:
        schema = json.load(f)
        
    definitions = schema.get('definitions', {})
    
    # Common types manually added if not in definitions
    common_types = {
        'string': {'description': 'A sequence of characters.', 'type': 'string'},
        'boolean': {'description': 'A boolean value (true or false).', 'type': 'boolean'},
        'integer': {'description': 'A whole number.', 'type': 'integer'},
        'enum': {'description': 'A value chosen from a specific set of allowed strings.', 'enum': []} # Pseudo-enum
    }
    
    html_content = []
    
    # Merge
    all_types = {}
    all_types.update(common_types)
    all_types.update(definitions)
    
    for type_name, type_def in sorted(all_types.items()):
        
        desc = type_def.get('description', 'No description available.')
        title = type_def.get('title', type_name)
        
        html_content.append(f'<div id="{type_name}" class="type-block" style="margin-bottom:30px; border-bottom:1px solid #30363d; padding-bottom:20px;">')
        html_content.append(f'<h3 style="margin-top:0;">{title} <code style="font-size:0.7em; color:#8b949e">{type_name}</code></h3>')
        html_content.append(f'<p>{desc}</p>')
        
        # Helper to generate natural language description of type constraints
        def describe_type(s):
            constraints = []
            
            # Resolve Ref
            if '$ref' in s:
                ref_name = s['$ref'].split('/')[-1]
                if ref_name in definitions:
                    target = definitions[ref_name]
                    # If the target has a Title, use it (e.g. "IPv4 Address")
                    # Unless it's just a generic type wrapper?
                    # Generally titles are good.
                    if 'title' in target:
                        return target['title']
                    return describe_type(target)
                return ref_name # Fallback
            
            # recursive combinators
            if 'oneOf' in s:
                sub_descs = [describe_type(sub) for sub in s['oneOf']]
                # Unique filtering
                sub_descs = sorted(list(set([d for d in sub_descs if d])))
                return " OR ".join(sub_descs)
            
            if 'allOf' in s:
                sub_descs = [describe_type(sub) for sub in s['allOf']]
                return " AND ".join([d for d in sub_descs if d])
            
            # Base Types
            t = s.get('type')
            
            # Enum
            if 'enum' in s:
                if not s['enum']:
                    return "Enum"
                vals = ", ".join([f"<code>{v}</code>" for v in s['enum']])
                return f"Enum: {vals}"
            
            # String Pattern
            if 'pattern' in s:
                 # If type is missing but pattern exists, implies string
                 constraints.append(f"matching regular expression <code>{s['pattern']}</code>")
            
            if t == 'integer':
                mn = s.get('minimum')
                mx = s.get('maximum')
                range_str = ""
                if mn is not None and mx is not None:
                    range_str = f" ({mn}...{mx})"
                elif mn is not None:
                    range_str = f" (min: {mn})"
                elif mx is not None:
                    range_str = f" (max: {mx})"
                
                return f"Integer{range_str}"
            
            elif t == 'string':
                # length constraints?
                min_l = s.get('minLength')
                max_l = s.get('maxLength')
                if min_l or max_l:
                     constraints.append(f"length {min_l or '0'}...{max_l or 'inf'}")
                
                if 'format' in s:
                     constraints.append(f"format <code>{s['format']}</code>")
                
                base = "String"
                if constraints:
                    return f"{base} {' '.join(constraints)}"
                return base

            elif t == 'boolean':
                return "Boolean"
            
            elif t == 'array':
                return "Array"
                
            # If no type but we have pattern (caught above?)
            if 'pattern' in s and not t:
                 return f"String matching <code>{s['pattern']}</code>"
            
            # Fallback
            return "Unknown Type"

        type_desc_str = describe_type(type_def)
        
        # Check if description offers more than just the basics? 
        # For now, always append it as the "Structure" info
        if type_desc_str:
            html_content.append(f'<p style="font-size: 0.9em; color: #8b949e; border-left: 2px solid #30363d; padding-left: 10px;"><em>Structure:</em> {type_desc_str}</p>')

        if 'examples' in type_def:
             html_content.append('<strong>Examples:</strong>')
             html_content.append('<ul>')
             for ex in type_def['examples']:
                 html_content.append(f'<li><code>{ex}</code></li>')
             html_content.append('</ul>')
             
        html_content.append('</div>')

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Systemd Configuration Types v{version}</title>
    <link rel="stylesheet" href="style.css">
    <style>
        body {{ display: block; max-width: 800px; margin: 0 auto; padding: 50px; overflow: auto; }}
        h1 {{ border-bottom: 1px solid var(--border-color); padding-bottom: 15px; }}
    </style>
</head>
<body>
    <h1>Configuration Types <small style="color: #8b949e">{version}</small></h1>
    <p><a href="index.html">Back to Documentation Index</a></p>
    
    { "".join(html_content) }
</body>
</html>
    """
    
    with open(os.path.join(output_dir, "types.html"), 'w') as f:
        f.write(html)
    print(" -> Generated types.html")

def generate_index(output_dir, version):
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Systemd Network Configuration v{version}</title>
    <link rel="stylesheet" href="style.css">
    <style>
        body {{ display: block; max-width: 800px; margin: 0 auto; padding: 50px; overflow: auto; }}
        .card {{ background: #161b22; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #30363d; }}
        .card h2 {{ margin-top: 0; border: none; }}
        .card a {{ font-size: 1.2em; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Systemd Network Configuration <small style="color: #8b949e">v{version}</small></h1>
    
    <div class="card">
        <h2><a href="systemd.network.html">systemd.network</a></h2>
        <p>Configuration for network matching and basic IP settings.</p>
    </div>
    
    <div class="card">
        <h2><a href="systemd.netdev.html">systemd.netdev</a></h2>
        <p>Configuration for virtual network devices (Bridges, VLANs, Tunels, etc).</p>
    </div>
    
    <div class="card">
        <h2><a href="systemd.link.html">systemd.link</a></h2>
        <p>Low-level link configuration (MAC Address, MTU).</p>
    </div>
    
    <div class="card">
        <h2><a href="networkd.conf.html">networkd.conf</a></h2>
        <p>Global system-wide network configuration.</p>
    </div>
    
    <hr style="border-color: #30363d; margin: 40px 0;">
    <p><a href="types.html">See all Data Types</a></p>
</body>
</html>
    """
    with open(os.path.join(output_dir, "index.html"), 'w') as f:
        f.write(html)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="e.g. v257")
    parser.add_argument("--web-schemas", action="store_true", help="Use relative paths for schemas (for GitHub Pages)")
    parser.add_argument("--available-versions", nargs="*", help="List of other available versions for the switcher")
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, "src", "original", args.version)
    # UPDATED: Use schemas directory (user request)
    schema_dir = os.path.join(base_dir, "schemas", args.version)
    output_dir = os.path.join(base_dir, "docs", "html", args.version)
    
    if not os.path.exists(src_dir):
        print(f"Error: Source directory {src_dir} does not exist. Run build.py first.")
        return
 
    os.makedirs(output_dir, exist_ok=True)
    
    # Write CSS
    with open(os.path.join(output_dir, "style.css"), "w") as f:
        f.write(CSS_STYLES)
        
    for doc in FILES:
        try:
            generate_page(doc, args.version, src_dir, schema_dir, output_dir, web_schemas=args.web_schemas, available_versions=args.available_versions)
        except Exception as e:
            print(f"Error processing {doc}: {e}")
            import traceback
            traceback.print_exc()
            
    generate_types_page(output_dir, args.version, schema_dir)
    generate_index(output_dir, args.version)
    print("\nDocumentation Generation Complete.")

 
if __name__ == "__main__":
    main()
