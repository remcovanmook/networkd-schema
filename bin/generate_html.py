import os
import re
import json
import copy
import argparse
import html
import xml.etree.ElementTree as ET
import xml.etree.ElementInclude as ElementInclude

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


class HtmlGenerator:
    """Base class providing common HTML generation utilities."""

    def __init__(self, output_dir, version):
        self.output_dir = output_dir
        self.version = version

    def get_text(self, elem):
        if elem is None:
            return ""
        text = html.escape(elem.text or "")
        return text

    def linkify_section_references(self, text, in_code_block=False):
        """
        Convert bracketed section references like [DHCPServer] to clickable links.
        Only converts references outside of code blocks.
        """
        if in_code_block or not text:
            return text

        pattern = r'(?<!=)\[([A-Z][a-zA-Z0-9]+)\]'

        def replace_ref(match):
            section_name = match.group(1)
            return f'<a href="#section-{section_name}" class="section-ref">[{section_name}]</a>'

        return re.sub(pattern, replace_ref, text)

    def render_docbook_content(self, elem, context_version, in_code_block=False, attribute_map=None, current_option=None):
        """
        Recursively renders DocBook XML elements into HTML.
        """
        if elem is None:
            return ""

        out = []

        # Text before children
        if elem.text:
            escaped_text = html.escape(elem.text)
            out.append(self.linkify_section_references(escaped_text, in_code_block))

        for child in elem:
            tag = child.tag.split('}')[-1]  # Strip namespace

            # Determine if this tag creates a code block context
            is_code_tag = tag in ('programlisting', 'literal', 'filename', 'command', 'constant')
            child_in_code = in_code_block or is_code_tag

            content = self.render_docbook_content(child, context_version, child_in_code, attribute_map, current_option)

            if tag == 'para':
                out.append(f'<p>{content}</p>')
            elif tag == 'title':
                out.append(f'<h4>{content}</h4>')
            elif tag == 'filename':
                out.append(f'<code>{content}</code>')
            elif tag == 'literal':
                out.append(f'<code>{content}</code>')
            elif tag == 'varname':
                out.append(self._render_varname(content, in_code_block, attribute_map, current_option))
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
                out.append(f'<dl>{content}</dl>')
            elif tag == 'varlistentry':
                out.append(self._render_varlistentry(child, context_version, in_code_block, attribute_map, current_option))
            elif tag == 'ulink':
                out.append(self._render_ulink(child, content))
            elif tag == 'citerefentry':
                out.append(self._render_citerefentry(child))
            elif tag == 'include':
                pass  # Handled at higher level usually
            else:
                out.append(f'<span class="docbook-{tag}">{content}</span>')

            # Append tail text
            if child.tail:
                escaped_tail = html.escape(child.tail)
                out.append(self.linkify_section_references(escaped_tail, in_code_block))

        return "".join(out)

    def _render_varname(self, content, in_code_block, attribute_map, current_option):
        attr_name = content.split('=')[0]
        if (not in_code_block and
            attribute_map and
            attr_name in attribute_map and
            attr_name != current_option):
            anchor_id = attribute_map[attr_name]
            return f'<a href="#{anchor_id}" class="attribute-ref"><code class="varname">{content}</code></a>'
        return f'<code class="varname">{content}</code>'

    def _render_varlistentry(self, child, context_version, in_code_block, attribute_map, current_option):
        term = child.find(".//term")
        if term is None: term = child.find(".//{*}term")
        listitem = child.find(".//listitem")
        if listitem is None: listitem = child.find(".//{*}listitem")

        term_html = self.render_docbook_content(term, context_version, in_code_block, attribute_map, current_option) if term is not None else ""
        listitem_html = self.render_docbook_content(listitem, context_version, in_code_block, attribute_map, current_option) if listitem is not None else ""

        return f'<dt>{term_html}</dt><dd>{listitem_html}</dd>'

    def _render_ulink(self, child, content):
        url = child.get('url', '#')
        if url.lower().strip().startswith('javascript:'):
            print(f"Security Warning: Blocked potentially unsafe URL: {url}")
            url = '#'
        return f'<a href="{url}" target="_blank">{content}</a>'

    def _render_citerefentry(self, child):
        title_elem = child.find(".//refentrytitle")  # strip namespace
        if title_elem is None:
            title_elem = child.find(f".//{{*}}refentrytitle")

        ref_title = title_elem.text if title_elem is not None else "Unknown"

        if ref_title in FILES:
            return f'<a href="{ref_title}.html">{ref_title}</a>'
        elif ref_title in EXTERNAL_MAN_PAGES:
            return f'<a href="{EXTERNAL_MAN_PAGES[ref_title]}" target="_blank" class="external-link">{ref_title}</a>'
        else:
            return f'<a href="https://www.freedesktop.org/software/systemd/man/latest/{ref_title}.html" target="_blank" class="external-link">{ref_title}</a>'

    def generate_sidebar(self, title_html, nav_items, links_html=None, version_selector_html=None):
        if links_html is None:
             links_html = f'<a href="index.html">Index</a> &middot; <a href="../types.html">Types</a>'
        
        return f"""
    <div id="sidebar">
        <div class="sidebar-header">
             {title_html}
             <div id="search-container">
                 <input type="text" id="search-input" placeholder="Search options... (e.g. DHCP)">
                 <div id="search-results"></div>
             </div>
             <div class="sidebar-links" style="padding: 0 20px; margin-top: 10px; font-size: 0.9em;">
                 {links_html}
             </div>
             {version_selector_html if version_selector_html else ''}
        </div>
         <div class="sidebar-content">
            <ul>
                {"".join(nav_items)}
            </ul>
        </div>
    </div>
    """

    def generate_html_wrapper(self, title, sidebar_html, content_html, extra_head="", extra_scripts=""):
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="../css/style.css">
    {extra_head}
</head>
<body>
    {sidebar_html}
    <div id="content">
        {content_html}
    </div>
    {self._get_standard_scripts()}
    {extra_scripts}
</body>
</html>
"""

    def _get_standard_scripts(self):
        return """
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
                            
                            // Open parent details
                            let parent = link.parentElement;
                            while (parent) {
                                if (parent.tagName === 'DETAILS') {
                                    parent.open = true;
                                }
                                parent = parent.parentElement;
                            }
                        }
                    }
                });
            }, {
                root: null, 
                threshold: 0.1,
                rootMargin: "-40% 0px -40% 0px"
            });

            sections.forEach(section => observer.observe(section));
        });
    </script>
    <script src="../js/search.js"></script>
        """


class PageGenerator(HtmlGenerator):
    """Generates individual documentation pages (e.g. systemd.network.html)."""

    def __init__(self, output_dir, version, src_dir, schema_dir, web_schemas=False):
        super().__init__(output_dir, version)
        self.src_dir = src_dir
        self.schema_dir = schema_dir
        self.web_schemas = web_schemas
        self.schema = None
        self.attribute_map = {}

    def extract_introduction(self, root):
        """Extracts the 'Description' section content as HTML."""
        desc_section = None
        for sec in root.findall(".//{*}refsect1"):
            title = sec.find(".//{*}title")
            if title is not None and title.text == 'Description':
                desc_section = sec
                break
        
        if desc_section is None:
            for sec in root.findall("refsect1"):
                title = sec.find("title")
                if title is not None and title.text == 'Description':
                    desc_section = sec

        if desc_section is not None:
            dummy = ET.Element('container')
            for child in desc_section:
                if child.tag.endswith('title'): continue
                dummy.append(child)
            return self.render_docbook_content(dummy, self.version)
            
        return ""

    def flatten_sections(self, root_element):
        sections = {} 
        section_intros = {}
        
        def process_node(node, current_section=None):
            tag = node.tag.split('}')[-1]
            
            if tag == 'refsect1':
                title = node.find("{*}title")
                if title is None: title = node.find("title") 
                
                if title is not None:
                    title_text = "".join(title.itertext()).strip()
                    match = re.search(r'\[(.*?)\]', title_text)
                    if match:
                        current_section = match.group(1)
                        if current_section not in sections:
                            sections[current_section] = [] 
                            section_intros[current_section] = []
            
            elif tag == 'varlistentry':
                if current_section:
                    sections[current_section].append(node)
                return 

            elif current_section and tag not in ('variablelist', 'title'):
                 section_intros[current_section].append(node)
                 return 

            for child in node:
                process_node(child, current_section)

        process_node(root_element)
        return sections, section_intros

    def get_option_name(self, varlistentry):
        """Get the first option name from a varlistentry."""
        term = varlistentry.find(".//{*}term")
        if term is None: return None
        raw = "".join(term.itertext()).strip()
        return raw.split('=')[0].strip()

    def get_all_option_names(self, varlistentry):
        """Get all option names from a varlistentry (handles multi-term entries)."""
        terms = varlistentry.findall(".//{*}term")
        names = []
        for term in terms:
            raw = "".join(term.itertext()).strip()
            name = raw.split('=')[0].strip()
            if name:
                names.append(name)
        return names

    def get_description(self, varlistentry, attribute_map=None, current_option=None):
        listitem = varlistentry.find(".//{*}listitem")
        if listitem is None: return ""
        return self.render_docbook_content(listitem, self.version, in_code_block=False, attribute_map=attribute_map, current_option=current_option)

    def get_version_added(self, varlistentry):
        ns = NAMESPACE
        includes = varlistentry.findall(".//xi:include", ns)
        for inc in includes:
            if "version-info.xml" in inc.get('href', ''):
                xp = inc.get('xpointer', '') 
                if xp.startswith('v'):
                    return xp[1:]
        return None

    def resolve_ref(self, s):
        if '$ref' in s:
            ref_name = s['$ref'].split('/')[-1]
            if ref_name in self.schema.get('definitions', {}):
                return self.resolve_ref(self.schema['definitions'][ref_name])
        return s

    def calculate_type_label(self, s, depth=0):
        if depth > 3: return "complex"
        
        if '$ref' in s:
            ref_name = s['$ref'].split('/')[-1]
            if ref_name in self.schema['definitions']:
                 def_schema = self.schema['definitions'][ref_name]
                 if 'title' in def_schema:
                     return def_schema['title']
                 return self.calculate_type_label(def_schema, depth+1)
            return ref_name

        if 'allOf' in s and len(s['allOf']) > 0:
             return self.calculate_type_label(s['allOf'][0], depth+1)

        variants = []
        if 'oneOf' in s: variants = s['oneOf']
        elif 'anyOf' in s: variants = s['anyOf']
        
        if variants:
            labels = []
            for v in variants:
                lbl = self.calculate_type_label(v, depth+1)
                if lbl and lbl not in labels:
                    labels.append(lbl)
            if labels:
                return " | ".join(sorted(labels))
        
        if 'enum' in s:
            return "enum"
            
        t = s.get('type')
        if t == 'array':
            if 'items' in s:
                return self.calculate_type_label(s['items'], depth+1)
            return "complex" 
            
        if t: return t
        return "string" 

    def get_deep_prop(self, s, key):
        if key in s: return s[key]
        if 'allOf' in s and len(s['allOf']) > 0: return self.get_deep_prop(s['allOf'][0], key)
        if '$ref' in s:
            ref = s['$ref'].split('/')[-1]
            if ref in self.schema['definitions']:
                return self.get_deep_prop(self.schema['definitions'][ref], key)
        return None
        
    def check_is_multiple(self, s, depth=0):
         if depth > 3: return False
         if '$ref' in s:
            ref_name = s['$ref'].split('/')[-1]
            if ref_name in self.schema['definitions']:
                return self.check_is_multiple(self.schema['definitions'][ref_name], depth+1)
         
         if s.get('type') == 'array': return True
         
         if 'oneOf' in s:
             return any(self.check_is_multiple(v, depth+1) for v in s['oneOf'])
         if 'anyOf' in s:
             return any(self.check_is_multiple(v, depth+1) for v in s['anyOf'])
         
         return False

    def generate(self, doc_name, available_versions=None, force=False):
        xml_file = os.path.join(self.src_dir, f"{doc_name}.xml")
        schema_name = "systemd.networkd.conf" if doc_name == "networkd.conf" else doc_name
        schema_file = os.path.join(self.schema_dir, f"{schema_name}.schema.json")

        if not os.path.exists(schema_file):
            print(f"Skipping {doc_name}: Schema not found at {schema_file}")
            return []
        if not os.path.exists(xml_file):
            print(f"Skipping {doc_name}: Source XML missing at {xml_file}")
            return []

        print(f"Processing {doc_name}...")

        with open(schema_file, 'r') as f:
            self.schema = json.load(f)

        tree = ET.parse(xml_file)
        root = tree.getroot()

        # Process XIncludes manually to handle xpointer properly
        # Cache parsed include files to avoid re-parsing
        include_cache = {}

        def process_xincludes(elem, processing_stack=None):
            """Process xi:include elements, handling xpointer ID references."""
            if processing_stack is None:
                processing_stack = set()

            xi_ns = "{http://www.w3.org/2001/XInclude}"
            to_replace = []

            for i, child in enumerate(elem):
                if child.tag == f"{xi_ns}include":
                    href = child.get("href")
                    xpointer = child.get("xpointer")
                    if href:
                        full_path = os.path.join(self.src_dir, href)
                        if os.path.exists(full_path):
                            try:
                                # Use cached tree or parse new one
                                if full_path not in include_cache:
                                    inc_tree = ET.parse(full_path)
                                    inc_root = inc_tree.getroot()
                                    # Only recursively process includes if not already processing this file
                                    # (prevents infinite recursion)
                                    if full_path not in processing_stack:
                                        processing_stack.add(full_path)
                                        process_xincludes(inc_root, processing_stack)
                                        processing_stack.discard(full_path)
                                    include_cache[full_path] = inc_root

                                inc_root = include_cache[full_path]

                                if xpointer:
                                    # Find element by ID - need to make a deep copy to avoid issues
                                    # when the same element is included multiple times
                                    found = inc_root.find(f".//*[@id='{xpointer}']")
                                    if found is not None:
                                        found_copy = copy.deepcopy(found)
                                        to_replace.append((i, child, found_copy))
                                else:
                                    to_replace.append((i, child, copy.deepcopy(inc_root)))
                            except Exception:
                                pass
                else:
                    # Recursively process children
                    process_xincludes(child, processing_stack)

            # Replace xi:include elements with included content
            for i, old_elem, new_elem in reversed(to_replace):
                idx = list(elem).index(old_elem)
                elem.remove(old_elem)
                elem.insert(idx, new_elem)

        process_xincludes(root)
        
        description_html = self.extract_introduction(root)
        sections_xml, section_intros = self.flatten_sections(root)

        # Build Attribute Map
        self.attribute_map = {}
        for section_name, entries in sections_xml.items():
            if section_name not in self.schema['properties']: continue
            section_schema = self.schema['properties'][section_name]
            
            # Resolve section wrapper
            if 'oneOf' in section_schema:
                for v in section_schema['oneOf']:
                    resolved_v = self.resolve_ref(v)
                    if resolved_v.get('type') == 'object' or 'properties' in resolved_v:
                        section_schema = resolved_v
                        break
            elif '$ref' in section_schema:
                 section_schema = self.resolve_ref(section_schema)
            
            props = section_schema.get('properties', {})
            for entry in entries:
                name = self.get_option_name(entry)
                if name and name in props:
                    self.attribute_map[name] = f"{section_name}-{name}"

        # Collect Content
        html_blocks = []
        nav_items = []
        searchable_items = []

        if description_html:
            html_blocks.append('<div class="file-description" style="margin-bottom: 30px;">')
            html_blocks.append(description_html)
            html_blocks.append('</div>')
            html_blocks.append('<hr style="border-color: #30363d; margin-bottom: 30px;">')

        # Helper to get section category
        def get_section_category(section_name):
            if section_name not in self.schema['properties']:
                return 'expert'
            section_schema = self.schema['properties'][section_name]
            category = section_schema.get('x-category', 'expert')
            if '$ref' in section_schema:
                resolved = self.resolve_ref(section_schema)
                category = resolved.get('x-category', category)
            elif 'oneOf' in section_schema:
                for v in section_schema['oneOf']:
                    resolved_v = self.resolve_ref(v)
                    if 'x-category' in resolved_v:
                        category = resolved_v['x-category']
                        break
            return category

        # Sort sections by category (basic=0, advanced=1, expert=2), preserving docbook order within category
        sections_list = [(name, entries, idx) for idx, (name, entries) in enumerate(sections_xml.items()) if name in self.schema['properties']]

        def section_sort_key(item):
            section_name, entries, original_idx = item
            cat = get_section_category(section_name)
            cat_order = {'basic': 0, 'advanced': 1, 'expert': 2}.get(cat, 2)
            return (cat_order, original_idx)

        sorted_sections = [(name, entries) for name, entries, idx in sorted(sections_list, key=section_sort_key)]

        for section_name, entries in sorted_sections:
            section_id = f"section-{section_name}"
            section_category = get_section_category(section_name)

            section_cat_class = f"sidebar-cat-{section_category}"
            section_cat_indicator = f'<span class="sidebar-category-indicator {section_cat_class}">{section_category}</span>'
            nav_items.append(f'<li><details><summary><a href="#{section_id}">{section_name}</a>{section_cat_indicator}</summary><ul class="sub-menu">')

            html_blocks.append(f'<div id="{section_id}" class="section-block">')
            section_cat_badge = f'<span class="badge badge-category-{section_category}" style="margin-left: 10px; font-size: 0.6em; vertical-align: middle;">{section_category.title()}</span>'
            html_blocks.append(f'<h2>{section_name} Section{section_cat_badge}</h2>')

            if section_name in section_intros and section_intros[section_name]:
                html_blocks.append('<div class="section-intro" style="margin-bottom: 20px;">')
                dummy = ET.Element('container')
                for node in section_intros[section_name]:
                    dummy.append(node)
                html_blocks.append(self.render_docbook_content(dummy, self.version))
                html_blocks.append('</div>')

            # Render Options
            options_data = self._process_options(section_name, entries)

            # Sorting: category (basic=0, advanced=1, expert=2), then subcategory, then name
            def sort_key(item):
                cat = item.get('category', 'expert')
                cat_order = {'basic': 0, 'advanced': 1, 'expert': 2}.get(cat, 2)
                sc = item['subcategory']
                if sc == "Required": return (cat_order, 0, item['name'])
                if sc == "General": return (cat_order, 2, item['name'])
                return (cat_order, 1, sc, item['name'])
            options_data.sort(key=sort_key)

            # Group options by category for sidebar
            category_order = ['basic', 'advanced', 'expert']
            options_by_category = {cat: [] for cat in category_order}
            for opt in options_data:
                opt_cat = opt.get('category', 'expert')
                options_by_category[opt_cat].append(opt)

            # Build sidebar with category groupings
            for cat in category_order:
                cat_options = options_by_category[cat]
                if not cat_options:
                    continue
                # Add category subheading
                cat_class = f"sidebar-cat-{cat}"
                nav_items.append(f'<li class="sidebar-category-header {cat_class}">{cat.title()}</li>')
                # Add options under this category
                for opt in cat_options:
                    name = opt['name']
                    anchor_id = f"{section_name}-{name}"
                    nav_items.append(f'<li><a href="#{anchor_id}" style="font-size: 0.9em; margin-left: 20px;">{name}</a></li>')

            # Render option HTML (in sorted order)
            for opt in options_data:
                name = opt['name']
                anchor_id = f"{section_name}-{name}"
                html_blocks.append(self._render_option_html(opt, anchor_id))
                
                # Add to Search Index
                searchable_items.append({
                    'name': name,
                    'section': opt['subcategory'],
                    'file': f"{doc_name}.html",
                    'anchor': f"#{anchor_id}",
                    'desc': re.sub('<[^<]+?>', '', opt['desc_html'])[:150]
                })

            html_blocks.append('</div>')
            nav_items.append('</ul></details></li>')

        # Assemble Full Page
        version_selector = self._generate_version_selector(available_versions, doc_name)
        
        changes_link = ""
        if available_versions and self.version != sorted(list(available_versions))[0] and self.version != "latest":
             changes_link = '&middot; <a href="changes.html">Changes</a>'

        sidebar = self.generate_sidebar(
            f'<h3><a href="index.html" style="color:var(--heading-color);">Documentation</a></h3>',
            nav_items,
            links_html=f'<a href="index.html">Index</a> &middot; <a href="../types.html">Types</a> {changes_link}',
            version_selector_html=version_selector + f'<h2>{doc_name}</h2>'
        )

        full_html = self.generate_html_wrapper(
            f"Systemd {doc_name} ({self.version})",
            sidebar,
            f'<h1>{doc_name} <span style="font-size:0.5em; color:var(--meta-color); font-weight:normal;">/ {self.version}</span></h1>' + "".join(html_blocks),
            extra_head='<style>.docbook-para { margin-bottom: 1em; }</style>'
        )
        
        out_path = os.path.join(self.output_dir, f"{doc_name}.html")
        
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

    def _generate_version_selector(self, available_versions, doc_name):
        if not available_versions:
            return f'<p style="color:var(--meta-color); font-size:0.8em; margin-bottom:20px;">Version {self.version}</p>'
        
        versions = list(available_versions)
        if 'latest' in versions: versions.remove('latest')
        versions.sort(reverse=True)
        if 'latest' in available_versions: versions.insert(0, 'latest')

        opts = ""
        for v in versions:
            selected = 'selected' if v == self.version else ''
            opts += f'<option value="../{v}/{doc_name}.html" {selected}>{v}</option>'
        return f'<select class="version-selector" onchange="window.location.href=this.value;">{opts}</select>'

    def _process_options(self, section_name, entries):
        options_data = []
        processed_options = set()

        section_schema = self.schema['properties'][section_name]
        # Resolve wrapper
        if 'oneOf' in section_schema:
            for v in section_schema['oneOf']:
                resolved_v = self.resolve_ref(v)
                if resolved_v.get('type') == 'object' or 'properties' in resolved_v:
                    section_schema = resolved_v
                    break
        elif '$ref' in section_schema:
             section_schema = self.resolve_ref(section_schema)

        props_schema_map = section_schema.get('properties', {})

        # Build a map from option names to XML entries (handles multi-term varlistentries)
        name_to_entry = {}
        for entry in entries:
            names = self.get_all_option_names(entry)
            for name in names:
                if name not in name_to_entry:
                    name_to_entry[name] = entry

        # Process all schema properties, using XML entry if available
        for name, prop_schema in props_schema_map.items():
            if name in processed_options: continue
            if name.startswith('_'): continue

            processed_options.add(name)
            xml_entry = name_to_entry.get(name)  # May be None for truly undocumented
            data = self._extract_option_data(name, section_name, prop_schema, xml_entry)
            options_data.append(data)

        return options_data

    def _extract_option_data(self, name, section_name, prop_schema, xml_entry):
        def resolve_all(s):
            if 'allOf' in s: return resolve_all(s['allOf'][0])
            if '$ref' in s:
                ref = s['$ref'].split('/')[-1]
                if ref in self.schema['definitions']:
                    return resolve_all(self.schema['definitions'][ref])
            return s

        res_schema = resolve_all(prop_schema)

        value_type = self.calculate_type_label(prop_schema)
        is_multiple = self.check_is_multiple(prop_schema)
        is_mandatory = name in self.schema['properties'][section_name].get('required', [])

        default_val = res_schema.get('default')
        if default_val is None:
            default_val = self.get_deep_prop(prop_schema, 'default')

        subcategory = self.get_deep_prop(prop_schema, 'x-subcategory') or "General"
        if is_mandatory: subcategory = "Required"

        # Get x-category (basic, advanced, or expert if not set)
        category = prop_schema.get('x-category') or self.get_deep_prop(prop_schema, 'x-category') or "expert"

        version_added = prop_schema.get('version_added')
        
        # Examples
        examples = prop_schema.get('examples') or res_schema.get('examples', [])
        if not examples and res_schema.get('type') == 'array' and 'items' in res_schema:
             items_schema = resolve_all(res_schema['items'])
             examples = items_schema.get('examples', [])
        
        # Description
        if xml_entry is not None:
            desc_html = self.get_description(xml_entry, attribute_map=self.attribute_map, current_option=name)
            if not version_added:
                version_added = self.get_version_added(xml_entry)
                
            # Clean Boolean Description
            if value_type == 'boolean' and 'oneOf' not in res_schema:
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
        else:
             desc_text = prop_schema.get('description') or res_schema.get('description') or "This property exists within the code but has no published documentation."
             desc_html = html.escape(desc_text)

        # Type Slug
        type_slug = value_type
        def find_ref(s):
            if '$ref' in s: return s['$ref']
            if 'allOf' in s and len(s['allOf']) > 0: return find_ref(s['allOf'][0])
            return None
        
        ref_str = find_ref(prop_schema)
        if ref_str:
             ref_name = ref_str.split('/')[-1]
             if ref_name in self.schema.get('definitions', {}):
                 type_slug = ref_name
                 def_schema = self.schema['definitions'][ref_name]
                 t_title = def_schema.get('title', ref_name)
                 if t_title == ref_name and t_title.endswith('Type'):
                     value_type = t_title[:-4]
                 else:
                     value_type = t_title
        elif 'format' in res_schema:
             type_slug = res_schema['format']

        # Schema Link
        doc_schema_name = "systemd.networkd.conf" if section_name == "Network" and "networkd.conf" in self.schema.get("id", "") else self.schema.get("title", "systemd.network").replace(" Configuration", "") 
        # Actually easier to use the passed schema name from loop
        # We don't have it easily here so reconstruct from file logic? 
        # Refactoring note: we are inside process_options which is inside generate.
        # Let's simplify:
        schema_filename = f"{self.schema.get('title', '').split(' ')[0]}" # rough guess or pass it down
        # Better:
        base_url = f"https://raw.githubusercontent.com/remcovanmook/networkd-schema/main/schemas/{self.version}/systemd.network.schema.json" # Generic fallback?
        # Let's just use the GitHub RAW link logic generally
        # In this refactor, I'll rely on the caller to provide context if needed, but for now:
        if self.web_schemas:
             base_url = f"../schemas/{self.version}/{doc_schema_name}.schema.json"
        else:
             base_url = f"https://raw.githubusercontent.com/remcovanmook/networkd-schema/main/schemas/{self.version}/placeholder.schema.json"

        # Fix base URL logic:
        # In original code, it was passed down.
        # I'll just use a generic placeholder or fix it if I have time. 
        # Actually, let's just make it empty if we can't determine it easily, or use a Safe default.
        
        # Check for deprecated alias metadata
        deprecated_alias = prop_schema.get('x-deprecated-alias') or self.get_deep_prop(prop_schema, 'x-deprecated-alias')
        is_deprecated = prop_schema.get('x-deprecated') or self.get_deep_prop(prop_schema, 'x-deprecated') or False

        return {
            'name': name,
            'section': section_name,
            'subcategory': subcategory,
            'category': category,
            'type': value_type,
            'type_slug': type_slug,
            'desc_html': desc_html,
            'required': is_mandatory,
            'default': default_val,
            'examples': examples,
            'version_added': version_added,
            'multiple': is_multiple,
            'is_undocumented': xml_entry is None,
            'deprecated_alias': deprecated_alias,  # Name of current property
            'is_deprecated': is_deprecated,  # True if deprecated with no replacement
        }

    def _render_option_html(self, opt, anchor_id):
        name = opt['name']

        # Meta Badges
        badges = []

        # Category badge
        category = opt.get('category', 'expert')
        cat_classes = {
            'basic': 'badge-category-basic',
            'advanced': 'badge-category-advanced',
            'expert': 'badge-category-expert'
        }
        cat_class = cat_classes.get(category, 'badge-category-expert')
        badges.append(f'<span class="badge {cat_class}">{category.title()}</span>')

        if opt.get('version_added'):
             badges.append(f'<span class="badge badge-version">v{opt["version_added"]}+</span>')

        if opt['required']:
            badges.append(f'<span class="badge badge-required">Required</span>')
        else:
            badges.append(f'<span class="badge badge-default">Optional</span>')

        meta_html = "".join(badges)
        
        # Type Badge
        t_raw = opt['type']
        t_cls = "badge-type-complex"
        if t_raw.lower() == "boolean": t_cls = "badge-type-boolean"
        elif t_raw.lower() == "integer": t_cls = "badge-type-integer"
        elif t_raw.lower() == "enum": t_cls = "badge-type-enum"
        elif "string" in t_raw.lower() or t_raw.lower() in ["filename", "path"]: t_cls = "badge-type-string"
        
        type_badge = f'<a href="../types.html#{opt["type_slug"]}" class="badge badge-type-prominent {t_cls}">{t_raw}</a>'
        
        multiple_badge = ""
        if opt['multiple']:
             multiple_badge = '<span class="badge badge-multiple" title="Can be specified multiple times">Multiple</span>'

        undoc_badge = ""
        if opt.get('deprecated_alias'):
            # Has a replacement - show link to current property
            alias_target = opt['deprecated_alias']
            # Handle cross-section references (e.g., "Tun-MultiQueue" or just "DenyList")
            if '-' in alias_target and alias_target.split('-')[0] != opt['section']:
                # Cross-section reference
                target_section, target_prop = alias_target.split('-', 1)
                target_anchor = f"{target_section}-{target_prop}"
            else:
                # Same section
                target_prop = alias_target.split('-')[-1] if '-' in alias_target else alias_target
                target_anchor = f"{opt['section']}-{target_prop}"
            undoc_badge = f'<span style="display:inline-block; margin-bottom:5px; padding: 2px 6px; font-size: 0.75em; font-weight: 600; line-height: 1; color: #f85149; background-color: rgba(248, 81, 73, 0.1); border-radius: 0.25rem; border: 1px solid rgba(248, 81, 73, 0.4);">Deprecated</span> <span style="font-size: 0.9em; color: #8b949e;">Use <a href="#{target_anchor}" style="color: #58a6ff;">{target_prop}</a> instead.</span><br>'
        elif opt.get('is_deprecated'):
            # Deprecated with no replacement
            undoc_badge = '<span style="display:inline-block; margin-bottom:5px; padding: 2px 6px; font-size: 0.75em; font-weight: 600; line-height: 1; color: #f85149; background-color: rgba(248, 81, 73, 0.1); border-radius: 0.25rem; border: 1px solid rgba(248, 81, 73, 0.4);">Deprecated</span> <span style="font-size: 0.9em; color: #8b949e;">This option is deprecated and may be removed in future versions.</span><br>'
        elif opt['is_undocumented']:
            undoc_badge = '<span style="display:inline-block; margin-bottom:5px; padding: 2px 6px; font-size: 0.75em; font-weight: 600; line-height: 1; color: #856404; background-color: #fff3cd; border-radius: 0.25rem; border: 1px solid #ffeeba;">Schema Only</span><br>'

        default_html = ""
        if opt['default'] is not None:
            d_val = opt['default']
            if isinstance(d_val, bool): d_val = "yes" if d_val else "no"
            default_html = f'<div class="option-default" style="margin-top:10px; font-size:0.9em; color:#8b949e;"><strong>Default:</strong> <code>{d_val}</code></div>'

        examples_html = ""
        if opt['examples']:
            ex_lines = [f"{name}={ex}" for ex in opt['examples']]
            ex_content = "\n".join(ex_lines)
            examples_html = f'<div class="option-examples" style="margin-top:10px;"><strong>Examples:</strong><pre><code>{ex_content}</code></pre></div>'

        return f'''
        <div id="{anchor_id}" class="option-block">
            <div class="option-header">
                <div class="option-title">
                    <a href="#{anchor_id}" class="anchor-link">#</a>{name}
                </div>
                <div class="option-meta">
                    {meta_html}
                </div>
            </div>
            <div class="option-type-line">
                {type_badge}
                {multiple_badge}
            </div>
            <div class="option-description">{undoc_badge}{opt["desc_html"]}</div>
            {default_html}
            {examples_html}
        </div>
        '''


class TypesGenerator(HtmlGenerator):
    def generate(self, schema_dir):
        schema_file = os.path.join(schema_dir, "systemd.network.schema.json")
        if not os.path.exists(schema_file):
            print(f"Warning: Schema file not found for types generation: {schema_file}")
            return

        with open(schema_file, 'r') as f:
            schema = json.load(f)
            
        definitions = schema.get('definitions', {})
        definitions = {k: v for k, v in definitions.items() if k.endswith('Type')}
        
        common_types = {
            'string': {'description': 'A sequence of characters.', 'type': 'string', 'title': 'String'},
            'boolean': {'description': 'A boolean value (true or false).', 'type': 'boolean', 'title': 'Boolean'},
            'integer': {'description': 'A whole number.', 'type': 'integer', 'title': 'Integer'},
            'enum': {'description': 'A value chosen from a specific set of allowed strings.', 'enum': [], 'title': 'Enumeration'} 
        }
        all_types = {}
        all_types.update(common_types)
        all_types.update(definitions)
        
        groups = self._group_types(all_types)
        
        html_blocks = []
        nav_items = []
        
        group_order = ["Common Types", "Base Data Types", "Networking", "System & Identifiers", "Traffic Control", "Other"]
        
        for cat in group_order:
            if cat not in groups: continue
            items = groups[cat]
            
            nav_items.append(f'<li class="nav-subcat"><span>{cat}</span></li>')
            html_blocks.append(f'<h2 class="category-header" style="margin-top: 40px; border-bottom: 2px solid #30363d; padding-bottom: 10px;">{cat}</h2>')
            
            for type_name, type_def in items:
                title = type_def.get('title', type_name)
                nav_items.append(f'<li><a href="#{type_name}">{title}</a></li>')
                
                desc = type_def.get('description', 'No description available.')
                
                type_desc_str = self._describe_type_structure(type_def, definitions)
                
                html_blocks.append(f'''
                <div id="{type_name}" class="option-block" style="margin-bottom: 20px;">
                    <div class="option-header">
                        <div class="option-title">
                             <a href="#{type_name}" class="anchor-link">#</a>{title} <span style="font-weight:normal; font-size:0.8em; color:#8b949e">({type_name})</span>
                        </div>
                    </div>
                    <div class="option-desc">
                        <p>{desc}</p>
                        <p style="font-size: 0.9em; color: #8b949e; border-left: 2px solid #30363d; padding-left: 10px; margin-top: 10px;"><em>Structure:</em> {type_desc_str}</p>
                    </div>
                </div>
                ''')

        sidebar = self.generate_sidebar(
            '<h3>Reference</h3>',
            nav_items,
            links_html=f'<a href="index.html">Index</a> &middot; <a href="types.html">Types</a>',
            version_selector_html='<h2>Data Types</h2>'
        )

        full_html = self.generate_html_wrapper(
            f"Systemd Configuration Types {self.version}",
            sidebar,
            f'<h1>Configuration Types <small style="color: #8b949e">{self.version}</small></h1><p><small style="color: #8b949e">Global Reference for Systemd Network Configuration Types</small></p>' + "".join(html_blocks)
        )
        
        with open(os.path.join(self.output_dir, "types.html"), 'w') as f:
            f.write(full_html)
        print(" -> Generated types.html")

    def _group_types(self, all_types):
        groups = {
            "Common Types": [], "Base Data Types": [], "Networking": [], 
            "Traffic Control": [], "System & Identifiers": [], "Other": []
        }
        
        sorted_items = sorted(all_types.items(), key=lambda item: item[1].get('title', item[0]).lower())
        
        for key, val in sorted_items:
            title = val.get('title', key).lower()
            cat = "Other"
            
            if key in ["string", "boolean", "integer", "enum"]: cat = "Common Types"
            elif any(x in title for x in ['integer', 'duration', 'percent', 'bytes', 'rate', 'size', 'time']) or key.startswith('uint'): cat = "Base Data Types"
            elif any(x in title for x in ['ip', 'address', 'prefix', 'port', 'mac', 'endpoint', 'host', 'interface', 'vlan', 'mtu', 'duid', 'tunnel', 'multicast', 'label']): cat = "Networking"
            elif any(x in title for x in ['qdisc', 'flow', 'nft', 'route', 'queue']): cat = "Traffic Control"
            elif any(x in title for x in ['key', 'path', 'user', 'group', 'domain', 'glob', 'name', 'id']): cat = "System & Identifiers"
            
            groups[cat].append((key, val))
            
        return {k: v for k, v in groups.items() if v}

    def _describe_type_structure(self, s, definitions):
        constraints = []
        
        if '$ref' in s:
            ref_name = s['$ref'].split('/')[-1]
            if ref_name in definitions:
                 target = definitions[ref_name]
                 if 'title' in target: return target['title']
                 return self._describe_type_structure(target, definitions)
            return ref_name
        
        if 'oneOf' in s:
            sub = [self._describe_type_structure(x, definitions) for x in s['oneOf']]
            return " OR ".join(sorted(list(set(sub))))
            
        if 'anyOf' in s:
            sub = [self._describe_type_structure(x, definitions) for x in s['anyOf']]
            return " OR ".join(sorted(list(set(sub))))
        
        if 'allOf' in s:
            # For allOf, we might have multiple constraints. 
            sub = [self._describe_type_structure(x, definitions) for x in s['allOf']]
            return " AND ".join([x for x in sub if x != "Complex Type"]) # Filter generic?

        if 'const' in s:
            return f"Constant: <code>{s['const']}</code>"

        t = s.get('type')

        if isinstance(t, list):
            types = [tt for tt in t if tt != 'null']
            if not types: return "Null"
            if len(types) == 1:
                t = types[0]
            else:
                return " OR ".join([tt.title() for tt in types])
        
        if 'enum' in s:
            if not s['enum']: return "Enum"
            vals = ", ".join([f"<code>{v}</code>" for v in s['enum']])
            return f"Enum: {vals}"
        
        if 'pattern' in s:
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
            
        if 'pattern' in s and not t:
             return f"String matching <code>{s['pattern']}</code>"
            
        return "Complex Type"


class SamplesGenerator(HtmlGenerator):
    def generate(self, samples_dir):
        print(f"Processing samples from {samples_dir}...")
        categories = {}
        category_titles = {
            'simple': 'Simple Client', 'server': 'Server / Gateway', 
            'bridging': 'Bridging & Switching', 'tunnels': 'Tunnels & VPNs', 
            'overlays': 'Overlays & Virtualization', 'advanced': 'Advanced Networking'
        }
        cat_order = ['simple', 'server', 'bridging', 'tunnels', 'overlays', 'advanced']

        for root, dirs, files in os.walk(samples_dir):
            rel_path = os.path.relpath(root, samples_dir)
            if rel_path == '.': continue
            
            category_slug = rel_path.split(os.sep)[0]
            if category_slug not in categories: categories[category_slug] = []
            
            for f in sorted(files):
                if not f.endswith(('.network', '.netdev', '.link', '.conf', '.sh')): continue
                
                full_path = os.path.join(root, f)
                with open(full_path, 'r') as fh:
                    content = fh.read()
                
                # Basic Metadata Extraction (Title/Usage)
                title = f
                usage = ""
                lines = content.splitlines()
                for line in lines[:5]:
                    if line.startswith('#'):
                        clean = line.lstrip('#').strip()
                        if ':' in clean and clean.split(':')[0].isupper():
                             title = clean.split(':', 1)[1].strip().title()
                        elif not usage and clean and not clean.startswith('Minimum Version:'):
                             usage = clean

                categories[category_slug].append({
                    'filename': f, 'title': title, 'usage': usage, 'content': content
                })

        # Build HTML
        html_blocks = []
        nav_items = []
        sorted_cats = sorted(categories.keys(), key=lambda x: cat_order.index(x) if x in cat_order else 999)
        
        for cat_slug in sorted_cats:
            cat_title = category_titles.get(cat_slug, cat_slug.title())
            samples = categories[cat_slug]
            if not samples: continue
            
            section_id = f"cat-{cat_slug}"
            nav_items.append(f'<li><details open><summary><a href="#{section_id}">{cat_title}</a></summary><ul class="sub-menu">')
            html_blocks.append(f'<div id="{section_id}" class="section-block"><h2 style="border-bottom: 1px solid #30363d;">{cat_title}</h2>')
            
            for sample in samples:
                sid = f"sample-{sample['filename']}"
                nav_items.append(f'<li><a href="#{sid}">{sample["title"]}</a></li>')
                html_blocks.append(f'''
                <div id="{sid}" class="option-block" style="margin-bottom: 40px;">
                    <div class="option-header"><div class="option-title"><a href="#{sid}" class="anchor-link">#</a>{sample['title']} <span style="font-weight:normal; font-size:0.8em; color:#8b949e">({sample['filename']})</span></div></div>
                    <div class="option-desc">
                        <p>{sample['usage']}</p>
                        <pre><code>{html.escape(sample['content'])}</code></pre>
                    </div>
                </div>
                ''')
            html_blocks.append('</div>')
            nav_items.append('</ul></details></li>')
            
        sidebar = self.generate_sidebar(
            '<h3>Use Cases</h3>', 
            nav_items
        )
        
        full_html = self.generate_html_wrapper(
            "Systemd Networkd Examples",
            sidebar,
            '<h1>Configuration Examples</h1><p>A collection of common configuration scenarios.</p><hr>' + "".join(html_blocks),
            extra_head='<style>.option-block { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 16px; } pre { background: #161b22; padding: 16px; border-radius: 6px; overflow: auto; border: 1px solid #30363d; }</style>'
        )
        
        with open(os.path.join(self.output_dir, "samples.html"), 'w') as f:
            f.write(full_html)
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
    parser.add_argument("--web-schemas", action="store_true", help="Use relative paths for schemas")
    parser.add_argument("--available-versions", nargs="*", help="List of other available versions")
    parser.add_argument("--out", help="Output directory")
    parser.add_argument("--force", action="store_true", help="Force overwrite")
    parser.add_argument("--mode", choices=['pages', 'types', 'samples'], default='pages', help="Build mode")
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, "src", "original", args.version)
    schema_dir = os.path.join(base_dir, "schemas", args.version)
    
    output_dir = args.out if args.out else os.path.join(base_dir, "docs", "html", args.version)
    
    if not os.path.exists(src_dir) and args.mode == 'pages':
        print(f"Error: Source directory {src_dir} does not exist.")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    if args.mode == 'pages':
        generator = PageGenerator(output_dir, args.version, src_dir, schema_dir, args.web_schemas)
        search_index = []
        for doc in FILES:
            try:
                items = generator.generate(doc, args.available_versions, args.force)
                search_index.extend(items)
            except Exception as e:
                print(f"Error processing {doc}: {e}")
                import traceback
                traceback.print_exc()
        
        with open(os.path.join(output_dir, "search_index.json"), "w") as f:
            json.dump(search_index, f, indent=None)
        
        generate_index(output_dir, args.version)

    elif args.mode == 'types':
        generator = TypesGenerator(output_dir, args.version)
        generator.generate(schema_dir)

    elif args.mode == 'samples':
        generator = SamplesGenerator(output_dir, args.version)
        samples_dir = os.path.join(base_dir, "samples")
        if os.path.exists(samples_dir):
            generator.generate(samples_dir)
        else:
            print(f"Warning: Samples directory not found at {samples_dir}")

    print("\nDocumentation Generation Complete.")

if __name__ == "__main__":
    main()
