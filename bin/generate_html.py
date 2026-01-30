import os
import re
import json
import argparse
import html
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape


# --- Constants ---

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
            # Security: Prevent javascript: links
            if url.lower().strip().startswith('javascript:'):
                print(f"Security Warning: Blocked potentially unsafe URL: {url}")
                url = '#'
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
                
                # Security: Prevent Path Traversal
                # Ensure the resolved path is inside the base_path
                try:
                    abs_target = os.path.abspath(target_path)
                    abs_base = os.path.abspath(base_path)
                    if not abs_target.startswith(abs_base):
                        print(f"Security Warning: Skipped include {href} (Path Traversal detected)")
                        continue
                except Exception:
                    continue

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

def generate_page(doc_name, version, src_dir, schema_dir, output_dir, web_schemas=False, available_versions=None, force=False):
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
        nav_items.append(f'<li><details><summary><a href="#{section_id}">{section_name}</a></summary><ul class="sub-menu">')
        
        html_content.append(f'<div id="{section_id}" class="section-block">')
        html_content.append(f'<h2>{section_name} Section</h2>')
        
        # Dependency Info
        deps = schema.get('dependencies', {}).get(section_name)
        if deps:
            req_sections = []
            if isinstance(deps, list):
                req_sections = deps
            elif isinstance(deps, dict) and 'required' in deps:
                req_sections = deps['required']
            
            if req_sections:
                links = []
                for req in req_sections:
                     links.append(f'<a href="#section-{req}" class="dependency-link">[{req}]</a>')
                
                html_content.append(f'<div class="section-dependency" style="margin-bottom: 20px; padding: 10px; background: rgba(56, 139, 253, 0.15); border: 1px solid rgba(56, 139, 253, 0.4); border-radius: 6px; color: #c9d1d9;"><strong>Depends on:</strong> {", ".join(links)}</div>')
        
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
            
            # Helper: Calculate Type Label (Recursive)
            def calculate_type_label(s, depth=0):
                if depth > 3: return "complex"
                
                # Check Refs first
                if '$ref' in s:
                    ref_name = s['$ref'].split('/')[-1]
                    if ref_name in schema['definitions']:
                         def_schema = schema['definitions'][ref_name]
                         if 'title' in def_schema:
                             return def_schema['title']
                         return calculate_type_label(def_schema, depth+1)
                    return ref_name

                # Check allOf matches
                if 'allOf' in s and len(s['allOf']) > 0:
                     return calculate_type_label(s['allOf'][0], depth+1)

                # Check oneOf/anyOf matches
                variants = []
                if 'oneOf' in s: variants = s['oneOf']
                elif 'anyOf' in s: variants = s['anyOf']
                
                if variants:
                    labels = []
                    for v in variants:
                        lbl = calculate_type_label(v, depth+1)
                        if lbl and lbl not in labels:
                            labels.append(lbl)
                    if labels:
                        return " | ".join(sorted(labels))
                
                # Enum
                if 'enum' in s:
                    return "enum"
                    
                # Base types
                t = s.get('type')
                if t == 'array':
                    # User Request: Unwrap Array ("Array of X" -> "X")
                    # The "Multiple" indicator will handle the array aspect.
                    if 'items' in s:
                        return calculate_type_label(s['items'], depth+1)
                    return "complex" # Array without items?
                    
                if t: return t
                
                return "string" # Fallback

            # Helper to get deep property even through refs for x-subcategory or default
            def get_deep_prop(s, key):
                if key in s: return s[key]
                if 'allOf' in s and len(s['allOf']) > 0: return get_deep_prop(s['allOf'][0], key)
                if '$ref' in s:
                    ref = s['$ref'].split('/')[-1]
                    if ref in schema['definitions']:
                        return get_deep_prop(schema['definitions'][ref], key)
                return None
                
            # Helper to check if type is/contains array (for Multiple indicator)
            def check_is_multiple(s, depth=0):
                 if depth > 3: return False
                 if '$ref' in s:
                    ref_name = s['$ref'].split('/')[-1]
                    if ref_name in schema['definitions']:
                        return check_is_multiple(schema['definitions'][ref_name], depth+1)
                 
                 if s.get('type') == 'array': return True
                 
                 if 'oneOf' in s:
                     return any(check_is_multiple(v, depth+1) for v in s['oneOf'])
                 if 'anyOf' in s:
                     return any(check_is_multiple(v, depth+1) for v in s['anyOf'])
                 
                 return False

            # Extract Metadata
            value_type = calculate_type_label(prop_schema)
            if value_type == 'complex' and res_schema.get('type') == 'array':
                 # Fallback if unwrap failed or top level array without obvious items
                 pass
            
            is_multiple = check_is_multiple(prop_schema)
            # If resolve returned enum but calculate returned string (maybe missed?), re-check?
            # calculate_type_label handles enum check.
            
            is_mandatory = name in section_schema.get('required', [])
            
            default_val = res_schema.get('default')
            if default_val is None:
                default_val = get_deep_prop(prop_schema, 'default')
            
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
            # Validate Examples if we have restricted values
            if has_enum_restriction and examples:
                 valid_examples = []
                 for ex in examples:
                     # Normalize boolean to string for comparison
                     ex_str = str(ex).lower() if isinstance(ex, bool) else str(ex)
                     
                     # Normalize boolean examples to yes/no for display
                     if value_type == 'boolean':
                         if ex_str == 'true' or ex_str == 'yes' or ex_str == '1':
                             valid_examples.append("yes")
                             continue
                         elif ex_str == 'false' or ex_str == 'no' or ex_str == '0':
                             valid_examples.append("no")
                             continue
                     
                     # Case-sensitive check usually for enums? But 'true'/'false' are case-insensitive in systemd mostly,
                     # here we stick to schema strictness or loose equality.
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
                if value_type == 'boolean':
                     # User Request: Prefer yes/no
                     if default_val is not None:
                         # Normalize default
                         d_str = str(default_val).lower()
                         if d_str in ['true', '1', 'yes']: examples.append("yes")
                         else: examples.append("no")
                     else:
                         examples.append("yes")
                         
                elif has_enum_restriction:
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
            
            # User Request: Remove redundant boolean text
            # Ensure we don't match complex types (like oneOf where one option is boolean)
            # Only filter if it's a simple boolean without variants.
            if value_type == 'boolean' and 'oneOf' not in res_schema and 'anyOf' not in res_schema:
                # Remove common phrases. Use Regex.
                # "Takes a boolean..." "A boolean..."
                # We need to be careful not to break HTML.
                # Regex for "Takes a boolean argument." "Takes a boolean." "A boolean." 
                # Case insensitive.
                patterns = [
                    r'Takes a boolean argument\.?\s*',
                    r'Takes a boolean value\.?\s*',
                    r'Takes a boolean\.?\s*',
                    r'A boolean argument\.?\s*',
                    r'A boolean value\.?\s*',
                    r'A boolean\.?\s*'
                ]
                for pat in patterns:
                    desc_html = re.sub(pat, '', desc_html, flags=re.IGNORECASE)
            
            # Map type to linkable name
            type_slug = value_type
            
            # Helper to find ref in prop_schema or allOf
            def find_ref(s):
                if '$ref' in s: return s['$ref']
                if 'allOf' in s and len(s['allOf']) > 0:
                     # Check first element of allOf?
                     return find_ref(s['allOf'][0])
                return None
                
            ref_str = find_ref(prop_schema)
            
            if ref_str:
                 ref_name = ref_str.split('/')[-1]
                 if ref_name in schema.get('definitions', {}):
                     type_slug = ref_name
                     # Use title or ref name as label
                     def_schema = schema['definitions'][ref_name]
                     value_type = def_schema.get('title', ref_name)
                     # Strip 'Type' suffix from ref name if used as label (e.g. secondsType -> seconds)
                     if value_type == ref_name and value_type.endswith('Type'):
                         value_type = value_type[:-4]
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
                'section_name': section_name, # Stored for link generation
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
                'schema_url': schema_url,
                'is_multiple': is_multiple # Added
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
                            <a href="{opt['schema_url']}" target="_blank" class="badge badge-schema">Schema</a>
                            {f'<span class="badge badge-version">v{opt["version_added"]}+</span>' if opt["version_added"] else ''}
                            {f'<span class="badge badge-mandatory">Required</span>' if opt['required'] else '<span class="badge badge-default">Optional</span>'}
                            {f'<span class="badge badge-warning">Deprecated</span>' if 'deprecated' in str(opt['full_schema']).lower() else ''}
                        </div>
                    </div>
                    <!-- Type Prominence (User Request) -->
                    <div class="option-type-line">
                         <!-- Dynamically assign class based on type -->
                         <!-- boolean, integer, string, enum, complex -->
                         <!-- Logic: -->
                         <!-- If type is 'boolean' -> badge-type-boolean -->
                         <!-- If type is 'integer' -> badge-type-integer -->
                         <!-- If type contains '|' -> badge-type-complex -->
                         <!-- If type is 'string' or similar -> badge-type-string -->
                         <!-- Fallback -> badge-type-complex -->
                         
                         { 
                             (lambda t, disp: 
                                f'<a href="types.html#{opt["type_slug"]}" class="badge badge-type-prominent badge-type-boolean">{disp}</a>' if t == "boolean" else
                                f'<a href="types.html#{opt["type_slug"]}" class="badge badge-type-prominent badge-type-integer">{disp}</a>' if t == "integer" else
                                f'<a href="types.html#{opt["type_slug"]}" class="badge badge-type-prominent badge-type-enum">{disp}</a>' if t == "enum" else
                                f'<a href="types.html#{opt["type_slug"]}" class="badge badge-type-prominent badge-type-string">{disp}</a>' if "string" in t or t == "filename" or t == "path" else
                                f'<a href="types.html#{opt["type_slug"]}" class="badge badge-type-prominent badge-type-complex">{disp}</a>'
                             )(opt['type'].lower(), opt['type'])
                         }
                         {
                             f'<span class="badge badge-multiple" title="Can be specified multiple times">Multiple</span>' if opt.get('is_multiple') else ''
                         }
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
                     default_disp = opt['default']
                     if opt['type'] == 'boolean':
                         d_str = str(default_disp).lower()
                         if d_str in ['true', '1', 'yes']: default_disp = "yes"
                         elif d_str in ['false', '0', 'no']: default_disp = "no"
                     
                     html_content.append(f'<div class="option-default" style="margin-top:10px; font-size:0.9em; color:#8b949e;"><strong>Default:</strong> <code>{default_disp}</code></div>')
                     
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

    # Return options for search index
    searchable_items = []
    for opt in options_data:
        # Minimal data for search
        # We need: name, link (file#anchor), desc_snippet?, file_title
        searchable_items.append({
            'name': opt['name'],
            'section': opt['subcategory'],
            'file': f"{doc_name}.html",
            'anchor': f"#{opt['section_name']}-{opt['name']}",
            # Strip HTML from description for search
            'desc': re.sub('<[^<]+?>', '', opt['desc_html'])[:150] # Snippet
        })

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
             <div id="search-container">
                 <input type="text" id="search-input" placeholder="Search options... (e.g. DHCP)">
                 <div id="search-results"></div>
             </div>
             <div class="sidebar-links" style="padding: 0 20px; margin-top: 10px; font-size: 0.9em;">
                 <a href="index.html">Index</a> &middot; <a href="types.html">Types</a> 
                 {f'&middot; <a href="changes.html">Changes</a>' if available_versions and version != sorted(available_versions)[0] and version != 'latest' else ''}
             </div>
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
    <title>Systemd {doc_name} ({version})</title>
    <link rel="stylesheet" href="../css/style.css">
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
                                if (parent.tagName === 'SUMMARY') {
                                     // Should not happen as summary is sibling
                                } else if (parent.tagName === 'LI') {
                                     // Check if it has details child?
                                     // The structure is li > details > summary
                                }
                                parent = parent.parentElement;
                            }
                        }
                    }
                });
            }, {
                root: null, // Use viewport
                threshold: 0.1,
                rootMargin: "-40% 0px -40% 0px" // Trigger when element is in middle of screen
            });

            sections.forEach(section => observer.observe(section));
        });
    </script>
    <script src="../js/search.js"></script>
</body>
</html>
    """

    full_html = html_header + html_scripts
    
    full_html = html_header + html_scripts
    out_path = os.path.join(output_dir, f"{doc_name}.html")
    
    write = True
    if not force and os.path.exists(out_path):
        try:
           with open(out_path, 'r') as f:
               if f.read() == full_html:
                   write = False
                   print(f" -> Skipping {doc_name}.html (unchanged)")
        except: pass
        
    if write:
        with open(out_path, 'w') as f:
            f.write(full_html)
        print(f" -> Generated {doc_name}.html")
    
    return searchable_items


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
    <title>Systemd Configuration Types {version}</title>
    <link rel="stylesheet" href="../css/style.css">
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
    <title>Systemd Network Configuration {version}</title>
    <link rel="stylesheet" href="../css/style.css">
    <style>
        body {{ display: block; max-width: 800px; margin: 0 auto; padding: 50px; overflow: auto; }}
        .card {{ background: #161b22; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #30363d; }}
        .card h2 {{ margin-top: 0; border: none; }}
        .card a {{ font-size: 1.2em; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Systemd Network Configuration <small style="color: #8b949e">{version}</small></h1>
    
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
    parser.add_argument("--out", help="Output directory")
    parser.add_argument("--force", action="store_true", help="Force overwrite")
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, "src", "original", args.version)
    # UPDATED: Use schemas directory (user request)
    schema_dir = os.path.join(base_dir, "schemas", args.version)
    
    if args.out:
        output_dir = args.out
    else:
        output_dir = os.path.join(base_dir, "docs", "html", args.version)
    
    if not os.path.exists(src_dir):
        print(f"Error: Source directory {src_dir} does not exist. Run build.py first.")
        return
 
    os.makedirs(output_dir, exist_ok=True)
    
    
    # Write CSS - Removed in favor of centralized CSS
    # with open(os.path.join(output_dir, "style.css"), "w") as f:
    #     f.write(CSS_STYLES)
        
    search_index = []
    
    for doc in FILES:
        try:
            page_options = generate_page(doc, args.version, src_dir, schema_dir, output_dir, web_schemas=args.web_schemas, available_versions=args.available_versions, force=args.force)
            if page_options:
                search_index.extend(page_options)
        except Exception as e:
            print(f"Error processing {doc}: {e}")
            import traceback
            traceback.print_exc()
            
    # Write Search Index
    with open(os.path.join(output_dir, "search_index.json"), "w") as f:
        json.dump(search_index, f, indent=None)
    print(f"Generated search_index.json with {len(search_index)} entries.")

    generate_types_page(output_dir, args.version, schema_dir)
    generate_index(output_dir, args.version)
    print("\nDocumentation Generation Complete.")

 
if __name__ == "__main__":
    main()
