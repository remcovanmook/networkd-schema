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

EXTERNAL_MAN_PAGES = {
    "socket": "https://man7.org/linux/man-pages/man7/socket.7.html",
    "resolv.conf": "https://man7.org/linux/man-pages/man5/resolv.conf.5.html",
    "ip": "https://man7.org/linux/man-pages/man8/ip.8.html",
    "hosts": "https://man7.org/linux/man-pages/man5/hosts.5.html",
    "fstab": "https://man7.org/linux/man-pages/man5/fstab.5.html",
    "crypttab": "https://man7.org/linux/man-pages/man5/crypttab.5.html",
    "modules-load.d": "https://man7.org/linux/man-pages/man5/modules-load.d.5.html",
    "sysctl.d": "https://man7.org/linux/man-pages/man5/sysctl.d.5.html",
    "tmpfiles.d": "https://man7.org/linux/man-pages/man5/tmpfiles.d.5.html",
    "systemd.unit": "https://man7.org/linux/man-pages/man5/systemd.unit.5.html",
    "systemd.service": "https://man7.org/linux/man-pages/man5/systemd.service.5.html",
    "systemd.socket": "https://man7.org/linux/man-pages/man5/systemd.socket.5.html",
    "systemd.device": "https://man7.org/linux/man-pages/man5/systemd.device.5.html",
    "systemd.mount": "https://man7.org/linux/man-pages/man5/systemd.mount.5.html",
    "systemd.automount": "https://man7.org/linux/man-pages/man5/systemd.automount.5.html",
    "systemd.swap": "https://man7.org/linux/man-pages/man5/systemd.swap.5.html",
    "systemd.target": "https://man7.org/linux/man-pages/man5/systemd.target.5.html",
    "systemd.path": "https://man7.org/linux/man-pages/man5/systemd.path.5.html",
    "systemd.timer": "https://man7.org/linux/man-pages/man5/systemd.timer.5.html",
    "systemd.slice": "https://man7.org/linux/man-pages/man5/systemd.slice.5.html",
    "systemd.scope": "https://man7.org/linux/man-pages/man5/systemd.scope.5.html",
    "systemd.nspawn": "https://man7.org/linux/man-pages/man5/systemd.nspawn.5.html",
    "systemd.exec": "https://man7.org/linux/man-pages/man5/systemd.exec.5.html",
    "systemd.kill": "https://man7.org/linux/man-pages/man5/systemd.kill.5.html",
    "systemd.resource-control": "https://man7.org/linux/man-pages/man5/systemd.resource-control.5.html",
    "systemd.time": "https://man7.org/linux/man-pages/man7/systemd.time.7.html",
    "locale.conf": "https://man7.org/linux/man-pages/man5/locale.conf.5.html",
    "localtime": "https://man7.org/linux/man-pages/man5/localtime.5.html",
    "machine-id": "https://man7.org/linux/man-pages/man5/machine-id.5.html",
    "machine-info": "https://man7.org/linux/man-pages/man5/machine-info.5.html",
    "os-release": "https://man7.org/linux/man-pages/man5/os-release.5.html",
    "systemd-system.conf": "https://man7.org/linux/man-pages/man5/systemd-system.conf.5.html",
    "systemd-user.conf": "https://man7.org/linux/man-pages/man5/systemd-user.conf.5.html",
    "user.conf.d": "https://man7.org/linux/man-pages/man5/user.conf.d.5.html",
    "journald.conf": "https://man7.org/linux/man-pages/man5/journald.conf.5.html",
    "logind.conf": "https://man7.org/linux/man-pages/man5/logind.conf.5.html",
    "coredump.conf": "https://man7.org/linux/man-pages/man5/coredump.conf.5.html",
    "timesyncd.conf": "https://man7.org/linux/man-pages/man5/timesyncd.conf.5.html",
    "resolved.conf": "https://man7.org/linux/man-pages/man5/resolved.conf.5.html",
    "batctl": "https://man.archlinux.org/man/batctl.8",
    "wg": "https://man7.org/linux/man-pages/man8/wg.8.html",
    "resolvconf": "https://man7.org/linux/man-pages/man8/resolvconf.8.html",
    "udev": "https://man7.org/linux/man-pages/man7/udev.7.html"
}

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

def linkify_section_references(text, in_code_block=False):
    """
    Convert bracketed section references like [DHCPServer] to clickable links.
    Only converts references outside of code blocks.

    References can point to:
    - Sections in the same document: [DHCPServer] -> #section-DHCPServer
    - We assume all references are to sections in the same document.
    """
    if in_code_block or not text:
        return text

    # Pattern: [SectionName] where SectionName starts with uppercase letter
    # and contains only alphanumeric characters
    # Negative lookbehind for = to avoid matching things like "Address=[Address]" in examples
    pattern = r'(?<!=)\[([A-Z][a-zA-Z0-9]+)\]'

    def replace_ref(match):
        section_name = match.group(1)
        return f'<a href="#section-{section_name}" class="section-ref">[{section_name}]</a>'

    return re.sub(pattern, replace_ref, text)


def render_docbook_content(elem, context_version, in_code_block=False, attribute_map=None, current_option=None):
    """
    Recursively renders DocBook XML elements into HTML.

    Args:
        elem: The XML element to render
        context_version: The systemd version context
        in_code_block: Whether we're inside a code block (no linking)
        attribute_map: Dict mapping attribute names to their anchor IDs (e.g. {'IPv6SendRA': 'Network-IPv6SendRA'})
        current_option: The current option being documented (to avoid self-links)
    """
    if elem is None:
        return ""

    out = []

    # Text before children
    if elem.text:
        escaped_text = html.escape(elem.text)
        out.append(linkify_section_references(escaped_text, in_code_block))

    for child in elem:
        tag = child.tag.split('}')[-1] # Strip namespace

        # Determine if this tag creates a code block context
        is_code_tag = tag in ('programlisting', 'literal', 'filename', 'command', 'constant')
        child_in_code = in_code_block or is_code_tag

        content = render_docbook_content(child, context_version, child_in_code, attribute_map, current_option)

        if tag == 'para':
            out.append(f'<p>{content}</p>')
        elif tag == 'filename':
            out.append(f'<code>{content}</code>')
        elif tag == 'literal':
            out.append(f'<code>{content}</code>')
        elif tag == 'varname':
            # Check if this is a reference to another attribute we can link to
            # Extract attribute name: handle "Name=", "Name=value", "Name=val1/val2"
            # Split on '=' and take the first part as the attribute name
            attr_name = content.split('=')[0]

            if (not in_code_block and
                attribute_map and
                attr_name in attribute_map and
                attr_name != current_option):
                # Create a link to the attribute
                anchor_id = attribute_map[attr_name]
                out.append(f'<a href="#{anchor_id}" class="attribute-ref"><code class="varname">{content}</code></a>')
            else:
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
            out.append(f'<dt>{render_docbook_content(term, context_version, in_code_block, attribute_map, current_option)}</dt>')
            out.append(f'<dd>{render_docbook_content(listitem, context_version, in_code_block, attribute_map, current_option)}</dd>')

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
            elif ref_title in EXTERNAL_MAN_PAGES:
                out.append(f'<a href="{EXTERNAL_MAN_PAGES[ref_title]}" target="_blank" class="external-link">{ref_title}</a>')
            else:
                out.append(f'<a href="https://www.freedesktop.org/software/systemd/man/latest/{ref_title}.html" target="_blank" class="external-link">{ref_title}</a>')

        elif tag == 'include':
            # Recursively resolving XInclude if we encounter it in content
            pass # We handle main includes at higher level, but sometimes they are inline

        else:
            # Default pass-through for unknown tags, just content
            out.append(f'<span class="docbook-{tag}">{content}</span>')

        # Text after child (tail) - apply linkification based on current context, not child context
        if child.tail:
            escaped_tail = html.escape(child.tail)
            out.append(linkify_section_references(escaped_tail, in_code_block))
            
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

def get_description(varlistentry, version_context, attribute_map=None, current_option=None):
    listitem = varlistentry.find(".//{*}listitem")
    if listitem is None: return ""
    return render_docbook_content(listitem, version_context, in_code_block=False, attribute_map=attribute_map, current_option=current_option)

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
        
    # Helper to resolve schema references
    def resolve_ref(s):
        if '$ref' in s:
            ref_name = s['$ref'].split('/')[-1]
            if ref_name in schema.get('definitions', {}):
                return resolve_ref(schema['definitions'][ref_name])
        return s

    # Load XML
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Extract Title and Description
    # ...
    
    # Flatten Content
    sections_xml = flatten_sections(root, src_dir)

    # Build attribute map for cross-referencing
    # Maps attribute name -> anchor ID (e.g. 'IPv6SendRA' -> 'Network-IPv6SendRA')
    attribute_map = {}
    for section_name, entries in sections_xml.items():
        if section_name not in schema['properties']:
            continue
            
        section_schema = schema['properties'][section_name]
        
        # Handle oneOf wrapper (which may contain refs)
        if 'oneOf' in section_schema:
            for v in section_schema['oneOf']:
                resolved_v = resolve_ref(v)
                if resolved_v.get('type') == 'object' or 'properties' in resolved_v:
                    section_schema = resolved_v
                    break
        elif '$ref' in section_schema:
             section_schema = resolve_ref(section_schema)
             
        props = section_schema.get('properties', {})
        
        for entry in entries:
            name = get_option_name(entry)
            if name and name in props:
                attribute_map[name] = f"{section_name}-{name}"


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
                 resolved_v = resolve_ref(v)
                 if resolved_v.get('type') == 'object' or 'properties' in resolved_v:
                     section_schema = resolved_v
                     break
        elif '$ref' in section_schema:
             section_schema = resolve_ref(section_schema)
                     
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
            # For arrays, also check items ref for examples
            examples = prop_schema.get('examples')
            if not examples:
                examples = res_schema.get('examples', [])
            if not examples and res_schema.get('type') == 'array' and 'items' in res_schema:
                items_schema = resolve(res_schema['items'])
                examples = items_schema.get('examples', [])
                
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
            
            # Limit boolean examples to 1 (yes or no is sufficient)
            if value_type == 'boolean':
                examples = examples[:1]

            desc_html = get_description(entry, version, attribute_map=attribute_map, current_option=name)

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
            
            # Mark this property as processed
            processed_options.add(name)

            # --- Existing Property Rendering Logic Here ---
            # (We keep it as is, just ensuring we tracked the name)
            # ... <existing logic> ...

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
                 # Let's link to the deployed schemas if possible or github
                 base_url = f"schemas/{version}/{schema_name}.schema.json" # Relative from where?
                 # Actually, let's just stick to the GitHub RAW URL for now for simplicity if not web_schemas
                 base_url = f"https://raw.githubusercontent.com/remcovanmook/networkd-schema/main/schemas/{version}/{schema_name}.schema.json"

            schema_link = f'{base_url}#:~:text="{name}"'

            options_data.append({
                'name': name,
                'section_name': section_name,
                'type': value_type,
                'type_slug': type_slug,
                'desc_html': desc_html,
                'required': is_mandatory,
                'default': default_val,
                'examples': examples,
                'subcategory': subcategory,
                'version_added': version_added,
                'multiple': is_multiple,
                'schema_link': schema_link,
                'is_undocumented': False
            })

        # --- PROCESS SCHEMA-ONLY PROPERTIES ---
        # Identify properties in the schema that were NOT in the XML
        for name, prop_schema in props_schema_map.items():
            if name in processed_options:
                continue
            
            # Skip internal properties starting with _
            if name.startswith('_'):
                continue
                
            processed_options.add(name)
            
            # Resolve Refs for metadata (Similar logic to above, ideally refactored but inline for now)
            def resolve(s):
                if 'allOf' in s: return resolve(s['allOf'][0])
                if '$ref' in s:
                    ref = s['$ref'].split('/')[-1]
                    if ref in schema['definitions']:
                        return resolve(schema['definitions'][ref])
                return s

            res_schema = resolve(prop_schema)
            
            # Reuse helper functions defined in the loop above? Closures capture them.
            # calculate_type_label, check_is_multiple, get_deep_prop are available.
            
            value_type = calculate_type_label(prop_schema)
            is_multiple = check_is_multiple(prop_schema)
            is_mandatory = name in section_schema.get('required', [])
            
            default_val = res_schema.get('default')
            if default_val is None:
                default_val = get_deep_prop(prop_schema, 'default')
                
            subcategory = get_deep_prop(prop_schema, 'x-subcategory') or "General"
            if is_mandatory:
                subcategory = "Required"
                
            version_added = prop_schema.get('version_added')
            
            examples = prop_schema.get('examples')
            if not examples:
                examples = res_schema.get('examples', [])
                
            # No XML description, use schema description
            desc_text = prop_schema.get('description') or res_schema.get('description') or "This property exists within the code but has no published documentation."
            desc_html = html.escape(desc_text)
            
            # Try to linkify types in description? Maybe later.
            
            # Map type to linkable name
            type_slug = value_type
            
            def find_ref(s):
                if '$ref' in s: return s['$ref']
                if 'allOf' in s and len(s['allOf']) > 0:
                     return find_ref(s['allOf'][0])
                return None
                
            ref_str = find_ref(prop_schema)
            
            if ref_str:
                 ref_name = ref_str.split('/')[-1]
                 if ref_name in schema.get('definitions', {}):
                     type_slug = ref_name
                     def_schema = schema['definitions'][ref_name]
                     value_type = def_schema.get('title', ref_name)
                     if value_type == ref_name and value_type.endswith('Type'):
                         value_type = value_type[:-4]
            elif 'format' in res_schema:
                 type_slug = res_schema['format']
                 
            if web_schemas:
                 base_url = f"../schemas/{version}/{schema_name}.schema.json"
            else:
                 base_url = f"https://raw.githubusercontent.com/remcovanmook/networkd-schema/main/schemas/{version}/{schema_name}.schema.json"

            schema_link = f'{base_url}#:~:text="{name}"'
            
            options_data.append({
                'name': name,
                'section_name': section_name,
                'type': value_type,
                'type_slug': type_slug,
                'desc_html': desc_html,
                'required': is_mandatory,
                'default': default_val,
                'examples': examples,
                'subcategory': subcategory,
                'version_added': version_added,
                'multiple': is_multiple,
                'schema_link': schema_link,
                'is_undocumented': True # Flag for UI
            })

        # Sort options_data by Subcategory then Name (Required first is handled by subcategory naming)
        # Custom Sort Key
        def sort_key(item):
            # Order: Required -> Hardware -> Network ... -> General
            # We want specific order?
            # 1. Required
            # 2. General (or last?) 
            # Alphabetical subcategories otherwise
            
            sc = item['subcategory']
            if sc == "Required": return (0, item['name'])
            if sc == "General": return (2, item['name'])
            return (1, sc, item['name'])
            
        options_data.sort(key=sort_key)
        
        # Render HTML for Options
        for opt in options_data:
            name = opt['name']
            
            # Anchor
            anchor_id = f"{section_name}-{name}"
            
            # Sidebar Link
            nav_items.append(f'<li><a href="#{anchor_id}" style="font-size: 0.9em; margin-left: 20px;">{name}</a></li>')
            
            # Block
            html_content.append(f'<div id="{anchor_id}" class="option-block">')
            
            # Header
            html_content.append(f'<div class="option-header">')
            html_content.append(f'<div class="option-title">')
            html_content.append(f'<a href="#{anchor_id}" class="anchor-link">#</a>{name}')
            html_content.append(f'</div>')
            
            # Meta Badges
            html_content.append(f'<div class="option-meta">')
            
            # Schema Link Badge
            if opt.get('schema_link'):
                html_content.append(f'<a href="{opt["schema_link"]}" target="_blank" class="badge badge-schema">Schema</a>')
            
            # Version Added Badge
            if opt.get('version_added'):
                 html_content.append(f'<span class="badge badge-version">v{opt["version_added"]}+</span>')
                 
            # Required / Subcategory Badge
            if opt['required']:
                html_content.append(f'<span class="badge badge-required">Required</span>')
            else:
                html_content.append(f'<span class="badge badge-default">Optional</span>')
            
            html_content.append(f'</div>') # End Meta
            html_content.append(f'</div>') # End Header
            
            # Type Prominence (User Request)
            html_content.append(f'<div class="option-type-line">')
            
            # Helper for badges
            def get_type_badge(t_raw, t_disp):
                t = t_raw.lower()
                href = f'../types.html#{opt["type_slug"]}'
                cls = "badge-type-complex"
                if t == "boolean": cls = "badge-type-boolean"
                elif t == "integer": cls = "badge-type-integer"
                elif t == "enum": cls = "badge-type-enum"
                elif "string" in t or t in ["filename", "path"]: cls = "badge-type-string"
                return f'<a href="{href}" class="badge badge-type-prominent {cls}">{t_disp}</a>'

            html_content.append(get_type_badge(opt['type'], opt['type']))
            
            if opt.get('is_multiple'):
                 html_content.append(f'<span class="badge badge-multiple" title="Can be specified multiple times">Multiple</span>')
            
            html_content.append(f'</div>')
            
            # Description
            # Add Schema Only badge if needed
            undoc_badge = ""
            if opt.get('is_undocumented'):
                 undoc_badge = '<span style="display:inline-block; margin-bottom:5px; padding: 2px 6px; font-size: 0.75em; font-weight: 600; line-height: 1; color: #856404; background-color: #fff3cd; border-radius: 0.25rem; border: 1px solid #ffeeba;">Schema Only</span><br>'
            
            html_content.append(f'<div class="option-description">{undoc_badge}{opt["desc_html"]}</div>')
            
            # Constraints Info (Type, Default)
            if opt['default'] is not None:
                d_val = opt['default']
                if isinstance(d_val, bool):
                    d_val = "yes" if d_val else "no"
                html_content.append(f'<div class="option-default" style="margin-top:10px; font-size:0.9em; color:#8b949e;"><strong>Default:</strong> <code>{d_val}</code></div>')
                
            # Examples (if any)
            if opt['examples']:
                html_content.append(f'<div class="option-examples" style="margin-top:10px;"><strong>Examples:</strong><pre><code>')
                for ex in opt['examples']:
                     html_content.append(f'{name}={ex}\n')
                html_content.append(f'</code></pre></div>')
            
            html_content.append(f'</div>') # End Option Block

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
                 <a href="index.html">Index</a> &middot; <a href="../types.html">Types</a> 
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
    schema_file = os.path.join(schema_dir, "systemd.network.schema.json")
    if not os.path.exists(schema_file):
        print(f"Warning: Schema file not found for types generation: {schema_file}")
        return

    with open(schema_file, 'r') as f:
        schema = json.load(f)
        
    definitions = schema.get('definitions', {})
    
    # Filter definitions to only those ending in 'Type'
    definitions = {k: v for k, v in definitions.items() if k.endswith('Type')}
    
    # Common types manually added if not in definitions
    common_types = {
        'string': {'description': 'A sequence of characters.', 'type': 'string', 'title': 'String'},
        'boolean': {'description': 'A boolean value (true or false).', 'type': 'boolean', 'title': 'Boolean'},
        'integer': {'description': 'A whole number.', 'type': 'integer', 'title': 'Integer'},
        'enum': {'description': 'A value chosen from a specific set of allowed strings.', 'enum': [], 'title': 'Enumeration'} 
    }
    
    # Merge
    all_types = {}
    all_types.update(common_types)
    all_types.update(definitions)

    # Helper to categorize types
    def categorize_type(key, title_lower):
        if key in common_types: return "Common Types"
        
        # Base Data Types
        if any(x in title_lower for x in ['integer', 'duration', 'percent', 'bytes', 'rate', 'size', 'time']): return "Base Data Types"
        if key.startswith('uint') or 'uint' in title_lower: return "Base Data Types"
        
        # Networking
        if any(x in title_lower for x in ['ip', 'address', 'prefix', 'port', 'mac', 'endpoint', 'host', 'interface', 'vlan', 'mtu', 'duid', 'tunnel', 'multicast', 'label']): return "Networking"
        
        # Traffic Control
        if any(x in title_lower for x in ['qdisc', 'flow', 'nft', 'route', 'queue']): return "Traffic Control"
        
        # System & Identifiers
        if any(x in title_lower for x in ['key', 'path', 'user', 'group', 'domain', 'glob', 'name', 'id']): return "System & Identifiers"

        return "Other"

    # Grouping
    groups = {
        "Common Types": [],
        "Base Data Types": [],
        "Networking": [],
        "Traffic Control": [],
        "System & Identifiers": [],
        "Other": []
    }
    
    # Sort types by title first
    sorted_items = sorted(all_types.items(), key=lambda item: item[1].get('title', item[0]).lower())
    
    for key, val in sorted_items:
        title = val.get('title', key)
        cat = categorize_type(key, title.lower())
        if cat not in groups: cat = "Other"
        groups[cat].append((key, val))

    # Remove empty groups
    groups = {k: v for k, v in groups.items() if v}
    
    html_content = []
    nav_items = []

    # Helper to get range from type definition
    def get_range(s):
        # Direct integer
        if s.get('type') == 'integer':
            return s.get('minimum'), s.get('maximum')
        
        # oneOf with integer
        if 'oneOf' in s:
            for sub in s['oneOf']:
                if sub.get('type') == 'integer':
                    return sub.get('minimum'), sub.get('maximum')
        return None, None

    # Render Groups
    # Define order
    group_order = ["Common Types", "Base Data Types", "Networking", "System & Identifiers", "Traffic Control", "Other"]
    
    for cat in group_order:
        if cat not in groups: continue
        items = groups[cat]
        
        # Sidebar Header
        nav_items.append(f'<li class="nav-subcat"><span>{cat}</span></li>')
        
        # Content Group Header
        html_content.append(f'<h2 class="category-header" style="margin-top: 40px; border-bottom: 2px solid #30363d; padding-bottom: 10px;">{cat}</h2>')
        
        for type_name, type_def in items:
            title = type_def.get('title', type_name)
            
            # Sidebar Item
            nav_items.append(f'<li><a href="#{type_name}">{title}</a></li>')

            desc = type_def.get('description', 'No description available.')
            
            # Check for range and append if not in description
            mn, mx = get_range(type_def)
            if mn is not None and mx is not None:
                # Naive check to see if numbers are already in description
                # Avoid "Unsigned 16-bit integer (0...65535) (Range: 0...65535)"
                if str(mn) not in desc or str(mx) not in desc:
                    desc += f" (Range: {mn}...{mx})"
            
            # Style as option-block for consistency
            html_content.append(f'''
            <div id="{type_name}" class="option-block" style="margin-bottom: 20px;">
                <div class="option-header">
                    <div class="option-title">
                         <a href="#{type_name}" class="anchor-link">#</a>{title} <span style="font-weight:normal; font-size:0.8em; color:#8b949e">({type_name})</span>
                    </div>
                </div>
                <div class="option-desc">
                    <p>{desc}</p>
            ''')
            
            # Helper to generate natural language description of type constraints
            def describe_type(s):
                constraints = []
                
                # Resolve Ref
                if '$ref' in s:
                    ref_name = s['$ref'].split('/')[-1]
                    if ref_name in definitions:
                        target = definitions[ref_name]
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
                
                if 'anyOf' in s:
                    sub_descs = [describe_type(sub) for sub in s['anyOf']]
                    sub_descs = sorted(list(set([d for d in sub_descs if d])))
                    return " OR ".join(sub_descs) # anyOf is technically OR logic for description
                
                if 'allOf' in s:
                    sub_descs = [describe_type(sub) for sub in s['allOf']]
                    return " AND ".join([d for d in sub_descs if d])
                
                # Const
                if 'const' in s:
                    return f"Constant: <code>{s['const']}</code>"
    
                # Base Types
                t = s.get('type')
                
                # Type List (e.g. ["string", "null"])
                if isinstance(t, list):
                    # Filter out null for description usually
                    types = [tt for tt in t if tt != 'null']
                    if not types: return "Null"
                    if len(types) == 1:
                        t = types[0] # Handle as single type
                    else:
                        return " OR ".join([tt.title() for tt in types]) # Simple join
                
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
                
                elif t == 'object' or 'properties' in s or 'additionalProperties' in s:
                    return "Object (Dictionary)"
                
                elif t == 'null':
                    return "Null"
                    
                # If no type but we have pattern (caught above?)
                if 'pattern' in s and not t:
                     return f"String matching <code>{s['pattern']}</code>"
                
                # Fallback
                return "Complex Type"
    
            type_desc_str = describe_type(type_def)
            
            if type_desc_str:
                html_content.append(f'<p style="font-size: 0.9em; color: #8b949e; border-left: 2px solid #30363d; padding-left: 10px; margin-top: 10px;"><em>Structure:</em> {type_desc_str}</p>')
    
            if 'examples' in type_def:
                 html_content.append('<div class="option-examples" style="margin-top:10px;"><strong>Examples:</strong>')
                 html_content.append('<ul style="margin-top:5px;">')
                 for ex in type_def['examples']:
                     html_content.append(f'<li><code>{ex}</code></li>')
                 html_content.append('</ul></div>')
                 
            html_content.append('</div></div>')

    sidebar_html = f"""
    <div id="sidebar">
        <div class="sidebar-header">
             <h3>Reference</h3>
             <div class="sidebar-links" style="padding: 0 20px; margin-top: 10px; font-size: 0.9em;">
                 <a href="index.html">Index</a> &middot; <a href="types.html">Types</a> 
             </div>
             <h2>Data Types</h2>
        </div>
         <div class="sidebar-content">
            <ul>
                {"".join(nav_items)}
            </ul>
        </div>
    </div>
    """

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Systemd Configuration Types {version}</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    {sidebar_html}
    <div id="content">
        <h1>Configuration Types <small style="color: #8b949e">{version}</small></h1>
        <p><small style="color: #8b949e">Global Reference for Systemd Network Configuration Types</small></p>
        
        { "".join(html_content) }
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            const sidebarLinks = document.querySelectorAll('#sidebar a');
            const sections = document.querySelectorAll('.option-block');
            
            // Map IDs to sidebar links
            const linkMap = new Map();
            sidebarLinks.forEach(link => {{
                const href = link.getAttribute('href');
                if (href && href.startsWith('#')) {{
                    linkMap.set(href.substring(1), link);
                }}
            }});

            const observer = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        const id = entry.target.id;
                        const link = linkMap.get(id);
                        if (link) {{
                            sidebarLinks.forEach(l => l.classList.remove('active'));
                            link.classList.add('active');
                            
                            // Scroll sidebar if needed
                            link.scrollIntoView({{ block: 'nearest', inline: 'nearest' }});
                        }}
                    }}
                }});
            }}, {{ root: null, threshold: 0.1, rootMargin: "-40% 0px -40% 0px" }});

            sections.forEach(section => observer.observe(section));
        }});
    </script>
</body>
</html>
    """
    
    with open(os.path.join(output_dir, "types.html"), 'w') as f:
        f.write(html)
    print(" -> Generated types.html")

def generate_samples_page(output_dir, version, samples_dir):
    print(f"Processing samples from {samples_dir}...")
    
    # 1. Scan Samples
    # Structure: category -> list of {filename, content, desc}
    categories = {}
    
    # Map folder names to Display Titles
    category_titles = {
        'simple': 'Simple Client',
        'server': 'Server / Gateway',
        'bridging': 'Bridging & Switching',
        'tunnels': 'Tunnels & VPNs',
        'overlays': 'Overlays & Virtualization',
        'advanced': 'Advanced Networking'
    }
    
    # Priority order for sidebar
    cat_order = ['simple', 'server', 'bridging', 'tunnels', 'overlays', 'advanced']
    
    for root, dirs, files in os.walk(samples_dir):
        rel_path = os.path.relpath(root, samples_dir)
        if rel_path == '.': continue
        
        category_slug = rel_path.split(os.sep)[0] # Top level folder
        if category_slug not in categories:
            categories[category_slug] = []
            
        for f in sorted(files):
            if not f.endswith(('.network', '.netdev', '.link', '.conf', '.sh')):
                continue
                
            full_path = os.path.join(root, f)
            with open(full_path, 'r') as fh:
                content = fh.read()
                
            # Extract description from first few lines if available
            desc = f
            lines = content.splitlines()
            # Look for line starting with "# [CATEGORY]: [TITLE]" or just usage
            # In my samples I used: "# [CATEGORY]: [TITLE]" style or similar
            # e.g. "# BASIC SIMPLE CLIENT: DHCP"
            title = f
            usage = ""
            
            for line in lines[:5]:
                if line.startswith('#'):
                    clean = line.lstrip('#').strip()
                    if ':' in clean:
                        # Heuristic for title
                        parts = clean.split(':', 1)
                        # Ensure it's a CATEGORY: TITLE line by checking if CATEGORY is uppercase
                        if len(parts) > 1 and parts[0].strip().isupper():
                            raw_title = parts[1].strip()
                            # Check if it looks like a title (uppercase or specific keyword?)
                            # In our samples, all titles are prefixed with CATEGORY:. 
                            # We just take it, but format it to be less shouty.
                            
                            def format_title(t):
                                # List of acronyms to keep uppercase
                                acronyms = {
                                    "DHCP", "DNS", "IP", "IPv4", "IPv6", "VLAN", "LACP", "VRF",
                                    "VXLAN", "GRE", "SIT", "VTI", "GRETAP", "GENEVE", "MACVLAN",
                                    "IPVLAN", "TAP", "VETH", "QOS", "CAKE", "SR-IOV", "VPN", "SSID",
                                    "RA", "PD", "WPA2", "WIFI"
                                }
                                
                                words = t.split()
                                new_words = []
                                for w in words:
                                    # Remove parens for checking
                                    clean_w = w.strip("()")
                                    upper_w = clean_w.upper()
                                    
                                    if upper_w in acronyms:
                                        # Keep/Force Acronym
                                        # Restore parens if needed
                                        new_words.append(w.replace(clean_w, upper_w))
                                    else:
                                        # Title Case
                                        new_words.append(w.title())
                                        
                                return " ".join(new_words)

                            title = format_title(raw_title)
                            
                    elif not usage and clean and not clean.isupper() and not clean.startswith('Minimum Version:'):
                         usage = clean
            
            # Formatting
            categories[category_slug].append({
                'filename': f,
                'path': full_path,
                'content': content,
                'title': title,
                'usage': usage
            })

    # 2. Build Sidebar Navigation
    nav_items = []
    
    # Sort categories by order if present, else alpha
    sorted_cats = sorted(categories.keys(), key=lambda x: cat_order.index(x) if x in cat_order else 999)
    
    html_content = []
    
    for cat_slug in sorted_cats:
        cat_title = category_titles.get(cat_slug, cat_slug.title())
        samples = categories[cat_slug]
        if not samples: continue
        
        section_id = f"cat-{cat_slug}"
        
        nav_items.append(f'<li><details open><summary><a href="#{section_id}">{cat_title}</a></summary><ul class="sub-menu">')
        
        html_content.append(f'<div id="{section_id}" class="section-block">')
        html_content.append(f'<h2 style="border-bottom: 1px solid #30363d; padding-bottom: 10px; margin-bottom: 20px;">{cat_title}</h2>')
        
        for sample in samples:
            sample_id = f"sample-{sample['filename']}"
            nav_items.append(f'<li><a href="#{sample_id}" style="font-size: 0.9em; margin-left: 20px;">{sample["title"]}</a></li>')
            
            html_content.append(f'''
            <div id="{sample_id}" class="option-block" style="margin-bottom: 40px;">
                <div class="option-header">
                    <div class="option-title">
                        <a href="#{sample_id}" class="anchor-link">#</a>{sample['title']} <span style="font-weight:normal; font-size:0.8em; color:#8b949e">({sample['filename']})</span>
                    </div>
                </div>
                <div class="option-desc">
                    <p>{sample['usage']}</p>
                    <pre><code>{html.escape(sample['content'])}</code></pre>
                </div>
            </div>
            ''')
            
        html_content.append('</div>')
        nav_items.append('</ul></details></li>')

    # 3. Assemble Page
    # Reuse Sidebar structure from generate_page
    
    sidebar_html = f"""
    <div id="sidebar">
        <div class="sidebar-header">
             <!-- No specific version link back for global page, or use relative to specific version if we want (e.g. {version}/index.html) 
                  But since it is global, we might just drop the deep navigation or link to the 'latest' concept if it existed.
                  For now, let's keep it simple: No versioned links in sidebar, just the samples navigation. -->
             <h3>Use Cases</h3>
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
    <title>Systemd Networkd Examples</title>
    <link rel="stylesheet" href="css/style.css">
    <style>
        .option-block {{ background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 16px; }}
        .option-title {{ font-size: 1.1em; font-weight: bold; margin-bottom: 10px; }}
        pre {{ background: #161b22; padding: 16px; border-radius: 6px; overflow: auto; border: 1px solid #30363d; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div id="content">
        <h1>Configuration Examples</h1>
        <p>A collection of common configuration scenarios ranging from simple client setups to complex overlay networks.</p>
        <hr style="border-color: #30363d; margin-bottom: 30px;">
        { "".join(html_content) }
    </div>
"""
    # Reuse scripts from generate_page for active sidebar highlighting
    html_scripts = """
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const sidebarLinks = document.querySelectorAll('#sidebar a');
            const sections = document.querySelectorAll('.section-block, .option-block');
            
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
                            sidebarLinks.forEach(l => l.classList.remove('active'));
                            link.classList.add('active');
                            
                            let parent = link.parentElement;
                            while (parent) {
                                if (parent.tagName === 'DETAILS') parent.open = true;
                                parent = parent.parentElement;
                            }
                        }
                    }
                });
            }, { root: null, threshold: 0.1, rootMargin: "-40% 0px -40% 0px" });

            sections.forEach(section => observer.observe(section));
        });
    </script>
</body>
</html>
    """

    # Output directly to output_dir (global doc root)
    out_path = os.path.join(output_dir, "samples.html")
    with open(out_path, 'w') as f:
        f.write(html_header + html_scripts)
    print(" -> Generated samples.html (Global)")

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
    
    <div class="card">
        <h2><a href="../types.html">Data Types</a></h2>
        <p>Reference for all available configuration types (ranges, enums, formats).</p>
    </div>
    
    <div class="card">
        <h2><a href="../samples.html">Use Cases / Examples</a></h2>
        <p>Common network configuration scenarios (DHCP, Bridges, VLANs, WireGuard, VXLAN, etc).</p>
    </div>
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
    parser.add_argument("--mode", choices=['pages', 'types', 'samples'], default='pages', help="Build mode: pages (versioned), types (global), or samples (global)")
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
        
    if args.mode == 'pages':
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

        generate_index(output_dir, args.version)

    elif args.mode == 'types':
        print("Generating Global Types Page...")
        generate_types_page(output_dir, args.version, schema_dir)

    elif args.mode == 'samples':
        print("Generating Global Samples Page...")
        # Generate Samples
        samples_dir = os.path.join(base_dir, "samples")
        if os.path.exists(samples_dir):
            generate_samples_page(output_dir, args.version, samples_dir)
        else:
            print(f"Warning: Samples directory not found at {samples_dir}")

    print("\nDocumentation Generation Complete.")

 
if __name__ == "__main__":
    main()
