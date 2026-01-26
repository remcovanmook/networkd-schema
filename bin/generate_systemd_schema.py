import os
import re
import json
import argparse
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import shutil
from collections import defaultdict, Counter

# --- 1. Constants & Heuristics ---

SINGLETON_SECTIONS = {
    "Match", "Network", "Link", "NetDev", "System", "General"
}

LIST_PARSERS = {
    "config_parse_strv",
    "config_parse_list",
    "config_parse_dns_servers",
    "config_parse_ntp_servers",
    "config_parse_search_domains",
    "config_parse_syscall_filter",
}

FORCE_LIST_ITEMS = {
    ("Network", "Address"),
    ("Network", "Gateway"),
    ("Network", "DNS"),
    ("Network", "NTP"),
    ("Network", "Domains"),
    ("Network", "BindCarrier"),
    ("Network", "Bridge"),
}

# --- 2. Shared Schema Definitions ---
SCHEMA_DEFINITIONS = {
    "mac_address": {
        "type": "string",
        "description": "MAC Address (Hex separated by colons or hyphens)",
        "pattern": "^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$",
        "title": "MAC Address"
    },
    "ipv4_address": {
        "type": "string",
        "description": "IPv4 Address",
        "format": "ipv4",
        "title": "IPv4 Address"
    },
    "ipv6_address": {
        "type": "string",
        "description": "IPv6 Address",
        "format": "ipv6",
        "title": "IPv6 Address"
    },
    "ip_address": {
        "description": "IPv4 or IPv6 Address",
        "oneOf": [
            { "$ref": "#/definitions/ipv4_address" },
            { "$ref": "#/definitions/ipv6_address" }
        ],
        "title": "IP Address"
    },
    "ipv4_prefix": {
        "type": "string",
        "description": "IPv4 Address with Prefix Length (CIDR), e.g., 192.168.1.1/24",
        "pattern": "^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\/(3[0-2]|[1-2]?[0-9]|[0-9])$",
        "title": "IPv4 Prefix"
    },
    "ipv6_prefix": {
        "type": "string",
        "description": "IPv6 Address with Prefix Length (CIDR), e.g., 2001:db8::1/64",
        "pattern": "^([0-9a-fA-F]{1,4}:){1,7}:?([0-9a-fA-F]{1,4}:?)*\\/(12[0-8]|1[0-1][0-9]|[1-9]?[0-9]|[0-9])$",
        "title": "IPv6 Prefix"
    },
    "ip_prefix": {
        "description": "IPv4 or IPv6 Prefix (CIDR)",
        "oneOf": [
            { "$ref": "#/definitions/ipv4_prefix" },
            { "$ref": "#/definitions/ipv6_prefix" }
        ],
        "title": "IP Prefix"
    },
    "filename": {
        "type": "string",
        "description": "Filesystem path",
        "format": "uri-reference",
        "title": "Filename"
    },
    "seconds": {
        "type": "string",
        "pattern": "^[0-9]+(\\.[0-9]+)?(us|ms|s|min|h|d|w|M|y)?$",
        "description": "Time duration (e.g. 5s, 1min, 500ms)",
        "title": "Seconds"
    },
    "bytes": {
        "description": "Size in bytes (Integer or String with suffix B, K, M, G, T, P, E)",
        "oneOf": [
            { "type": "integer", "minimum": 0 },
            { "type": "string", "pattern": "^[0-9]+(\\s*[KMGTPE]i?B?)?$" }
        ],
        "title": "Bytes"
    }
}

# --- 3. Text Processing ---

def to_ascii(text):
    if not text: return ""
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2010': "-", '\u2011': "-", '\u2012': "-", '\u2013': "-", '\u2014': "--",
        '\u2026': "...", '\u00a0': " ", '\u201f': '"'
    }
    for uni, ascii_char in replacements.items():
        text = text.replace(uni, ascii_char)
    text = unicodedata.normalize('NFKD', text)
    return text.encode('ascii', 'ignore').decode('ascii')

def clean_whitespace(text):
    if not text: return ""
    text = to_ascii(text)
    text = re.sub(r'\s+\.', '.', text) 
    return re.sub(r'\s+', ' ', text).strip()

def get_text_with_semantics(elem):
    out = []
    if elem.text: out.append(elem.text)
    for child in elem:
        child_text = get_text_with_semantics(child)
        tag = child.tag.split('}')[-1]
        if tag in ['literal', 'constant', 'option', 'filename']:
            if not (child_text.startswith("'") or child_text.startswith('"')):
                out.append(f"'{child_text}'")
            else:
                out.append(child_text)
        else:
            out.append(child_text)
        if child.tail: out.append(child.tail)
    return "".join(out)

def extract_enum_from_text(text):
    if not text: return None, ""
    intro_pattern = r"(?i)(?:Takes|Accepts|Values?|Defaults?|Supported)\s+(?:a|an|the)?\s*(?:\w+\s+){0,3}?(?:one of|:|are|following)(.*?)(\.|$)"
    match = re.search(intro_pattern, text)
    if match:
        content = match.group(1)
        values = re.findall(r'[\'"]([^\'"]+)[\'"]', content)
        if not values:
            clean_content = re.sub(r'\s+(?:or|and)\s+', ',', content)
            candidates = re.split(r'[,|]', clean_content)
            for c in candidates:
                c = c.strip()
                if re.match(r'^[a-zA-Z0-9\-\._]+$', c):
                    values.append(c)
                else:
                    values = []
                    break
        if values:
            unique_values = sorted(list(set(values)))
            cleaned_text = text.replace(match.group(0), "").strip()
            return unique_values, clean_whitespace(cleaned_text)
    return None, text

def extract_range_from_text(text):
    if not text: return None, None, ""
    p1 = r"(?i)(?:Takes|Accepts|Must\s+be)\s+(?:a|an|the)?\s*(?:integer|number|value)?\s*(?:in\s+the\s+)?range\s+(?:of\s+)?(-?\d+)(?:\.\.\.|\.\.|…)(-?\d+)\.?"
    p2 = r"(?i)(?:Takes|Accepts|Must\s+be)\s+(?:a|an|the)?\s*(?:integer|number|value)\s*between\s+(-?\d+)\s+and\s+(-?\d+)\.?"
    p3 = r"(?i)(?:^|\.\s+)Range\s+(?:of\s+)?(-?\d+)(?:\.\.\.|\.\.|…)(-?\d+)\.?"

    for pat in [p1, p2]:
        match = re.search(pat, text)
        if match:
            try:
                min_v, max_v = int(match.group(1)), int(match.group(2))
                cleaned = text.replace(match.group(0), "").strip()
                return min_v, max_v, clean_whitespace(cleaned)
            except ValueError: pass
            
    match = re.search(p3, text)
    if match:
        try:
             min_v, max_v = int(match.group(1)), int(match.group(2))
             cleaned = text.replace(match.group(0), ".").strip() 
             return min_v, max_v, clean_whitespace(cleaned)
        except ValueError: pass

    return None, None, text

def extract_default_value(text, schema_type):
    if not text: return None
    patterns = [
        r'(?i)Defaults?\s+to\s+(?:the\s+)?[\'"]?([^\s"\',]+)[\'"]?',
        r'(?i)The\s+default\s+is\s+(?:the\s+)?[\'"]?([^\s"\',]+)[\'"]?',
        r'(?i)Default:\s+[\'"]?([^\s"\',]+)[\'"]?'
    ]
    val_str = None
    for p in patterns:
        match = re.search(p, text)
        if match:
            candidate = match.group(1).rstrip('.').strip()
            if candidate.lower() not in ['unset', 'empty', 'none', 'n/a', 'ignored']:
                val_str = candidate
            break
    if val_str is None: return None

    if schema_type == 'boolean':
        if val_str.lower() in ['yes', 'true', 'on', 'enabled', '1']: return True
        if val_str.lower() in ['no', 'false', 'off', 'disabled', '0']: return False
        return None
    elif schema_type == 'integer':
        if val_str.isdigit(): return int(val_str)
        return None
    else:
        return val_str

def is_mandatory(text):
    if not text: return False
    patterns = [
        r'(?i)\b(?:is|are)\s+(?:mandatory|compulsory)\b',
        r'(?i)\bmust\s+be\s+specified\b',
        r'(?i)\bthis\s+option\s+is\s+required\b',
        r'(?i)\bsetting\s+is\s+required\b',
    ]
    for p in patterns:
        if re.search(p, text): return True
    return False

def clean_redundant_phrases(text, schema_type, ref_name=None):
    if not text: return ""
    if schema_type == 'boolean':
        text = re.sub(r'(?i)^Takes a boolean\s*(?:argument|value)?\.?', '', text)
    elif ref_name:
        cleanup_map = {
            'ipv4_address': r'IPv4 address', 'ipv6_address': r'IPv6 address',
            'ip_address': r'IP address', 'mac_address': r'(?:MAC|hardware) address',
            'filename': r'(?:file system )?path', 'seconds': r'time (?:span|duration|interval)',
            'bytes': r'(?:size|value) in bytes'
        }
        if ref_name in cleanup_map:
            term = cleanup_map[ref_name]
            text = re.sub(fr'(?i)^Takes a\s+{term}\.?', '', text)
    return clean_whitespace(text)

def infer_type_from_description(desc):
    if not desc: return None
    if re.search(r'(?i)Takes a boolean', desc): return 'boolean'
    rules = [
        (r'Takes an IPv4 address', 'ipv4_address'),
        (r'Takes an IPv6 address', 'ipv6_address'),
        (r'Takes an IP address', 'ip_address'),
        (r'Takes a MAC address', 'mac_address'),
        (r'Takes a path', 'filename'),
        (r'in seconds', 'seconds'),
        (r'in bytes', 'bytes'),
        (r'suffixes K, M, G', 'bytes'),
    ]
    for pattern, def_name in rules:
        if re.search(pattern, desc, re.IGNORECASE):
            return def_name
    return None

# --- 4. Parser Mapping ---
PARSER_TYPE_MAP = {
    'config_parse_bool': {'type': 'boolean'},
    'config_parse_tristate': {'type': 'boolean'}, 
    'config_parse_unsigned': {'type': 'integer', 'minimum': 0},
    'config_parse_int': {'type': 'integer'},
    'config_parse_ip_port': {'type': 'integer', 'minimum': 0, 'maximum': 65535},
    'config_parse_mtu': {'type': 'integer', 'minimum': 68},
    'config_parse_mode': {'type': 'string', 'pattern': '^[0-7]{3,4}$'},
    
    # Byte Sizes
    'config_parse_iec_size': {'REF': 'bytes'},
    'config_parse_si_size': {'REF': 'bytes'},
    'config_parse_bytes_size': {'REF': 'bytes'},
    
    'config_parse_mac_addr': {'REF': 'mac_address'},
    'config_parse_hwaddr': {'REF': 'mac_address'},
    'config_parse_ipv4_addr': {'REF': 'ipv4_address'},
    'config_parse_ipv6_addr': {'REF': 'ipv6_address'},
    'config_parse_in_addr_non_null': {'REF': 'ip_address'},
    'config_parse_in_addr_data': {'REF': 'ip_address'},
    'config_parse_in_addr_prefix': {'REF': 'ip_prefix'},
    'config_parse_sec': {'REF': 'seconds'},
    
    'config_parse_dns_servers': {'REF': 'ip_address'},
    'config_parse_ntp_servers': {'REF': 'ip_address'},
}

KEY_NAME_HEURISTICS = {
    'MACAddress': 'mac_address',
    'Address': 'ip_address',
    'Gateway': 'ip_address',
    'DNS': 'ip_address',
    'NTP': 'ip_address',
    'Destination': 'ip_prefix',
    'Description': 'string',
}

# --- 5. Git Helper ---
def setup_sparse_repo(tag, temp_dir):
    print(f"--- Fetching systemd {tag} (Sparse Checkout) ---")
    required_dirs = ["man", "src/network", "src/basic", "src/shared", "src/fundamental", "src/libsystemd", "src/udev/net"]

    subprocess.run(["git", "init"], cwd=temp_dir, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/systemd/systemd.git"], cwd=temp_dir, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "core.sparseCheckout", "true"], cwd=temp_dir, check=True, stdout=subprocess.DEVNULL)
    
    sparse_file = os.path.join(temp_dir, ".git", "info", "sparse-checkout")
    os.makedirs(os.path.dirname(sparse_file), exist_ok=True)
    with open(sparse_file, "w") as f:
        for d in required_dirs:
            f.write(f"{d}/\n")

    try:
        subprocess.run(["git", "fetch", "--depth", "1", "origin", "tag", tag], cwd=temp_dir, check=True, capture_output=True, text=True)
        subprocess.run(["git", "checkout", "FETCH_HEAD"], cwd=temp_dir, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Git Error: {e.stderr}")
        raise RuntimeError(f"Failed to fetch tag {tag}.")

# --- 6. Parsing Logic (Section Aware) ---

def parse_man_pages(man_path, specific_file):
    docs = defaultdict(lambda: defaultdict(dict))
    file_path = os.path.join(man_path, specific_file)
    if not os.path.exists(file_path): return docs

    try:
        parser = ET.XMLParser(encoding="utf-8")
        tree = ET.parse(file_path, parser=parser)
        root = tree.getroot()

        for refsect in root.findall(".//{*}refsect1"):
            title_elem = refsect.find(".//{*}title")
            if title_elem is None: continue

            title_text = "".join(title_elem.itertext())
            section_match = re.search(r'\[([a-zA-Z0-9]+)\]', title_text)
            current_section = section_match.group(1) if section_match else "Global"

            for varlistentry in refsect.findall(".//{*}varlistentry"):
                term = varlistentry.find(".//{*}term")
                listitem = varlistentry.find(".//{*}listitem")
                
                if term is not None and listitem is not None:
                    raw_term = get_text_with_semantics(term).strip()
                    raw_term = to_ascii(raw_term)
                    
                    for t in raw_term.split(','):
                        match = re.search(r'([A-Za-z0-9]+)=', t)
                        if match:
                            key = match.group(1)
                            desc_parts = [ to_ascii(get_text_with_semantics(p)) for p in listitem.findall(".//{*}para") ]
                            cleaned_desc = clean_whitespace(" ".join(desc_parts))
                            
                            version_added = None
                            # Look for version info in XInclude (e.g. <xi:include href="version-info.xml" xpointer="v211"/>)
                            for child in listitem.findall(".//{http://www.w3.org/2001/XInclude}include"):
                                xpointer = child.get("xpointer")
                                if xpointer and xpointer.startswith("v"):
                                    match = re.match(r"^v(\d+)$", xpointer)
                                    if match:
                                        version_added = match.group(1)
                                        break
                            
                            docs[current_section][key] = {"desc": cleaned_desc, "version": version_added}
                            if key not in docs['Global']:
                                docs['Global'][key] = {"desc": cleaned_desc, "version": version_added}

    except Exception as e:
        print(f"XML Parse Warning: {e}")
        
    return docs

def find_enum_values(src_path, enum_type_name):
    search_pattern = re.compile(r'static\s+const\s+char\*\s+const\s+' + re.escape(enum_type_name) + r'_table\[\]\s*=\s*\{([^;]+)\};', re.DOTALL | re.MULTILINE)
    search_dirs = ["src/network", "src/basic", "src/shared", "src/fundamental"]
    for rel_dir in search_dirs:
        d = os.path.join(src_path, rel_dir)
        if not os.path.exists(d): continue
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith(".c") or file.endswith(".h"):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                            match = search_pattern.search(f.read())
                            if match:
                                values = re.findall(r'"([^"]+)"', match.group(1))
                                return [v for v in values if v]
                    except: continue
    return []

def find_gperf_file(root_dir, possible_names):
    for root, _, files in os.walk(root_dir):
        for name in possible_names:
            if name in files: return os.path.join(root, name)
    return None

def process_item_schema(section, key, parse_func, arg, desc, version, repo_path):
    item_schema = None
    raw_map = PARSER_TYPE_MAP.get(parse_func)
    ref_name = None
    
    if raw_map:
        if 'REF' in raw_map:
            ref_name = raw_map['REF']
            item_schema = { "$ref": f"#/definitions/{ref_name}" }
        else:
            item_schema = raw_map.copy()
    
    is_c_list = parse_func in LIST_PARSERS
    is_forced_list = (section, key) in FORCE_LIST_ITEMS
    is_generic = (item_schema is None or item_schema.get('type') == 'string')
    
    if is_generic:
        inferred_vals, cleaned_desc = extract_enum_from_text(desc)
        if inferred_vals:
            item_schema = { "type": "string", "enum": inferred_vals }
            desc = cleaned_desc
        else:
            guessed_ref = None
            for suffix, ref in KEY_NAME_HEURISTICS.items():
                if key.endswith(suffix):
                    guessed_ref = ref
                    break
            if not guessed_ref:
                guessed_ref = infer_type_from_description(desc)
            
            if guessed_ref:
                if guessed_ref == 'boolean':
                    item_schema = { "type": "boolean" }
                else:
                    ref_name = guessed_ref
                    item_schema = { "$ref": f"#/definitions/{guessed_ref}" }
            elif item_schema is None:
                item_schema = { "type": "string" }
    
    resolved_type = item_schema.get('type')
    if resolved_type in [None, 'string', 'integer']:
        min_v, max_v, cleaned_desc = extract_range_from_text(desc)
        if min_v is not None and max_v is not None:
            item_schema['type'] = 'integer'
            item_schema['minimum'] = min_v
            item_schema['maximum'] = max_v
            desc = cleaned_desc

    if parse_func in ['config_parse_enum', 'config_parse_list']:
        enum_vals = find_enum_values(repo_path, arg)
        if enum_vals:
            item_schema = {'type': 'string', 'enum': enum_vals}

    resolved_type = item_schema.get('type', 'string')
    default_val = extract_default_value(desc, resolved_type)
    if default_val is not None:
        item_schema['default'] = default_val
    
    if is_mandatory(desc):
        item_schema['_mandatory'] = True

    if is_c_list or is_forced_list:
        item_schema = { "type": "array", "items": item_schema }

    if item_schema.get('type') == 'boolean':
        desc = clean_redundant_phrases(desc, 'boolean')
    elif ref_name:
        desc = clean_redundant_phrases(desc, 'ref', ref_name)
    
    desc = clean_whitespace(desc)

    if desc:
        if "$ref" in item_schema:
                item_schema = { "allOf": [ item_schema ], "description": desc }
        else:
            item_schema["description"] = desc

    if version:
        # If we have an allOf/ref wrapper, we should put it at the top level?
        # Standard JSON schema doesn't forbid extra properties in allOf, but it's cleaner to put it in the schema dict.
        # If we just converted to allOf, item_schema is the wrapper.
        item_schema["version_added"] = version

    return item_schema

def parse_gperf_file(repo_path, target_names, docs):
    full_path = find_gperf_file(repo_path, target_names)
    if not full_path: return {}
    
    schema_structure = defaultdict(lambda: defaultdict(dict))
    
    with open(full_path, 'r') as f:
        for line in f:
            match = re.match(r'^([A-Z][a-zA-Z0-9]+)\.([A-Z][a-zA-Z0-9-]+)\s*,\s*([a-zA-Z0-9_]+)\s*,\s*[^,]+\s*,\s*([a-zA-Z0-9_]+)', line.strip())
            if match:
                section, key, parse_func, arg = match.groups()
                entry = docs[section].get(key, docs['Global'].get(key, {}))
                desc = entry.get("desc", "")
                version = entry.get("version", None)
                item_schema = process_item_schema(section, key, parse_func, arg, desc, version, repo_path)
                schema_structure[section][key] = item_schema

    for section_name, section_items in docs.items():
        if section_name == "Global": continue
        if section_name in schema_structure:
            for key, entry in section_items.items():
                if key not in schema_structure[section_name]:
                    desc = entry.get("desc", "")
                    version = entry.get("version", None)
                    item_schema = process_item_schema(
                        section_name, key, 'config_parse_string', '0', desc, version, repo_path
                    )
                    schema_structure[section_name][key] = item_schema

    return schema_structure

# --- 7. Statistics & Reporting ---

def resolve_label(schema):
    if 'allOf' in schema:
        return resolve_label(schema['allOf'][0])
    
    if '$ref' in schema:
        return f"Ref: {schema['$ref'].split('/')[-1]}"
        
    if 'type' in schema:
        t = schema['type']
        
        if t == 'array':
            return f"Array of {resolve_label(schema['items'])}"
        
        if t == 'string':
            if 'enum' in schema:
                return "String (Enum)"
            if 'pattern' in schema or 'format' in schema:
                return "String (Pattern/Format)"
            return "String (Freeform)"
            
        if t == 'integer':
            if 'minimum' in schema or 'maximum' in schema:
                return "Integer (Range)"
            return "Integer"
        
        if t == 'boolean':
            return "Boolean"
            
        return t.capitalize()
    
    return "Unknown/Generic"

def print_summary(structure, name):
    print(f"\n--- Summary for {name} ---")
    total_sections = len(structure)
    total_keys = 0
    mandatory_count = 0
    type_counts = Counter()
    
    for section, keys in structure.items():
        total_keys += len(keys)
        for key, schema in keys.items():
            if schema.get('_mandatory'):
                mandatory_count += 1
            label = resolve_label(schema)
            type_counts[label] += 1

    print(f"Sections: {total_sections}")
    print(f"Total Items: {total_keys}")
    print(f"Mandatory Items: {mandatory_count}")
    print("Type Breakdown:")
    for label, count in sorted(type_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  - {label:<25}: {count}")
    print("---------------------------------")

# --- 8. Generator ---
def generate_json_schema(structure, filename, version):
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://systemd.io/schemas/{version}/{filename}.json",
        "title": f"Systemd {filename} Configuration ({version})",
        "type": "object",
        "additionalProperties": False,
        "definitions": SCHEMA_DEFINITIONS,
        "properties": {}
    }

    for section, keys in structure.items():
        required_keys = []
        clean_properties = {}
        
        for k, v in keys.items():
            prop_schema = v.copy()
            if prop_schema.get('_mandatory'):
                required_keys.append(k)
                del prop_schema['_mandatory']
            clean_properties[k] = prop_schema

        section_schema = {
            "type": "object",
            "description": f"[{section}] section configuration",
            "properties": clean_properties,
            "additionalProperties": False
        }
        
        if required_keys:
            section_schema["required"] = required_keys
        
        if section in SINGLETON_SECTIONS:
            schema["properties"][section] = section_schema
        else:
            schema["properties"][section] = {
                "oneOf": [
                    { "type": "array", "items": section_schema },
                    section_schema
                ],
                "description": f"[{section}] configuration (Can be repeated)"
            }

    return schema

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="e.g. v257")
    parser.add_argument("--out", default=".", help="Output dir")
    parser.add_argument("--force", action="store_true", help="Force overwrite")
    args = parser.parse_args()

    targets = [
        {"name": "network", "gperf_names": ["networkd-network-gperf.gperf"], "xml": "man/systemd.network.xml"},
        {"name": "netdev", "gperf_names": ["netdev-gperf.gperf", "networkd-netdev-gperf.gperf"], "xml": "man/systemd.netdev.xml"},
        {"name": "link", "gperf_names": ["link-config-gperf.gperf"], "xml": "man/systemd.link.xml"},
        {"name": "networkd.conf", "gperf_names": ["networkd-gperf.gperf"], "xml": "man/networkd.conf.xml"}
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            setup_sparse_repo(args.version, temp_dir)
        except RuntimeError: return

        for target in targets:
            print(f"\nProcessing {target['name']}...")
            docs = parse_man_pages(temp_dir, target['xml'])
            structure = parse_gperf_file(temp_dir, target['gperf_names'], docs)
            
            if structure:
                print_summary(structure, target['name'])
                schema = generate_json_schema(structure, target['name'], args.version)
                filename = f"systemd.{target['name']}.{args.version}.schema.json"
                out_path = os.path.join(args.out, filename)
                
                new_json = json.dumps(schema, indent=2)
                write = True
                if not args.force and os.path.exists(out_path):
                    try:
                        with open(out_path, 'r') as f:
                            if f.read() == new_json:
                                write = False
                                print(f" -> Skipping {out_path} (unchanged)")
                    except: pass
                
                if write:
                    with open(out_path, 'w') as f:
                        f.write(new_json)
                    print(f" -> Created {out_path}")

                # Copy XML file
                xml_src = os.path.join(temp_dir, target['xml'])
                xml_dst = os.path.join(args.out, os.path.basename(target['xml']))
                if os.path.exists(xml_src):
                    shutil.copy2(xml_src, xml_dst)
                    print(f" -> Copied {os.path.basename(target['xml'])} to {args.out}")
                else:
                    print(f"Warning: XML source not found: {xml_src}")

if __name__ == "__main__":
    main()