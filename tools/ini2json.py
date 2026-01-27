#!/usr/bin/env python3
import sys
import json
import argparse
import re
import os
from collections import defaultdict

# Regex for basic INI parsing
SECTION_RE = re.compile(r'^\[([^\]]+)\]')
KEY_VAL_RE = re.compile(r'^([^=]+)=(.*)$')

def load_schema(schema_path):
    with open(schema_path, 'r') as f:
        return json.load(f)

def get_logical_lines(content):
    """
    Generator that yields (type, content) tuples.
    type is 'COMMENT' or 'LINE'.
    Handles backslash line continuation and comment skipping inside continuation.
    """
    buffer = []
    in_continuation = False
    
    for line in content.splitlines():
        stripped = line.strip()
        
        # Determine if this line is a comment
        is_comment = stripped.startswith('#') or stripped.startswith(';')
        
        if is_comment:
            if in_continuation:
                # Inside a continuation, comments are ignored completely (merged into the gap)
                continue
            else:
                yield ('COMMENT', line.strip()) # Preserve raw comment content (striped of whitespace around? maybe keep #)
                continue
                
        if not stripped:
            # Empty line
            if in_continuation:
                continue 
            else:
                yield ('COMMENT', "") # Treat empty lines as comments to preserve spacing?
                # Or just ignore empty lines for now to simplify? 
                # User asked to capture comments. Empty lines are style.
                # Let's ignore empty lines for structural matching, or maybe treat as comment ""?
                # Let's ignore empty lines to stay safer, unless requested.
                continue

        # Check for continuation
        if stripped.endswith('\\'):
            # Append content without the backslash
            segment = stripped[:-1].strip()
            buffer.append(segment)
            in_continuation = True
        else:
            # End of logical line
            buffer.append(stripped)
            # Join with space as per spec ("backslash is replaced by a space character")
            yield ('LINE', " ".join(buffer))
            buffer = []
            in_continuation = False
            
    # Flush remaining if file ends with backslash (edge case)
    if buffer:
        yield ('LINE', " ".join(buffer))

def unescape_value(val):
    # ... existing unescape_value implementation ...
    # (We are not replacing unescape_value here, just keeping context if needed, but the tool replaces range)
    # The user instruction implies replacing parse_ini too.
    return val # Placeholder for the diff, real code below

def parse_ini(content):
    sections = []
    current_section = None
    pending_comments = []
    
    # Use logical lines
    for kind, line in get_logical_lines(content):
        if kind == 'COMMENT':
            pending_comments.append(line)
            continue
            
        match_sec = SECTION_RE.match(line)
        if match_sec:
            # Start of a new section
            current_section = {
                "name": match_sec.group(1),
                "props": defaultdict(list)
            }
            if pending_comments:
                current_section["_comments"] = pending_comments
                pending_comments = []
            sections.append(current_section)
            continue
            
        match_kv = KEY_VAL_RE.match(line)
        if match_kv and current_section:
            k = match_kv.group(1).strip()
            v = match_kv.group(2).strip()
            v = unescape_value(v)
            current_section["props"][k].append(v)
            
            if pending_comments:
                if "_property_comments" not in current_section:
                    current_section["_property_comments"] = defaultdict(list)
                # If key repeated? Attach to list? 
                # For simplicity, just append to the list for this key.
                # But multiple props with same key? 
                # Ideally _property_comments maps "Key" -> ["Comment1", "Comment2"]?
                # But if we have Key=1, Key=2. Comment before Key=2?
                # The structure is defaultdict(list) for props.
                # Maybe _property_comments should be a list of objects or parallel structure?
                # Or simplistic: Key -> list of comments. All comments for that key key accumulated?
                # Let's append new comments to existing list for that key.
                current_section["_property_comments"][k].extend(pending_comments)
                pending_comments = []
            
    # Trailing comments?
    # If pending_comments exist at EOF, where do they go?
    # Attach to last section?
    if pending_comments and sections:
        if "_comments" not in sections[-1]:
             sections[-1]["_comments"] = []
        sections[-1]["_comments"].extend(pending_comments)
            
    return sections

def resolve_type(key, section_name, schema):
    """
    Finds the type definition for a key in a section from schema.
    """
    # 1. Find section schema
    sec_schema = schema.get('properties', {}).get(section_name)
    if not sec_schema:
        return None
        
    # Handle OneOf wrapper for sections (for repeated singleton vs list logic in schema)
    if 'oneOf' in sec_schema:
        # Usually one option is array, one is singleton object. We just want the properties.
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
        
    # Resolve $ref or allOf
    def get_effective_type(s):
        if not s: return None
        if 'allOf' in s: return get_effective_type(s['allOf'][0])
        if '$ref' in s:
            ref = s['$ref'].split('/')[-1]
            defn = schema.get('definitions', {}).get(ref)
            return get_effective_type(defn)
        return s
        
    return get_effective_type(prop_schema)

def convert_value(val, type_def):
    if not type_def: return val
    
    tgt_type = type_def.get('type')
    
    if tgt_type == 'boolean':
        lower = val.lower()
        if lower in ['1', 'yes', 'true', 'on']: return True
        if lower in ['0', 'no', 'false', 'off']: return False
        return val # Fallback?
        
    if tgt_type == 'integer':
        try:
             return int(val)
        except:
             return val
             
    return val

def convert_to_json(sections, schema):
    output = {}
    
    # Analyze Schema for Singletons vs Arrays
    # We looked at schema: "Network", "Match", "Link", "NetDev" are singletons in `properties` directly?
    # Actually schema usually defines them.
    # From generate_systemd_schema.py: SINGLETON_SECTIONS = {"Match", "Network", "Link", "NetDev", "System", "General"}
    
    # We can detect if schema["properties"][Sec] has "type": "array" or "oneOf" -> "array"...
    
    singleton_sections = set()
    for sec_name, sec_def in schema.get('properties', {}).items():
        # Heuristic: if explicit "type": "object" at top level, it's singleton
        if sec_def.get('type') == 'object':
            singleton_sections.add(sec_name)
    
    # Group by name
    # Group by name
    grouped = defaultdict(list)
    for sec in sections:
        grouped[sec['name']].append(sec)
        
    for name, list_of_sec_objs in grouped.items():
        processed_sections = []
        
        for sec_obj in list_of_sec_objs:
            props = sec_obj['props']
            clean_props = {}
            
            # Transfer metadata
            if "_comments" in sec_obj:
                clean_props["_comments"] = sec_obj["_comments"]
            if "_property_comments" in sec_obj:
                clean_props["_property_comments"] = sec_obj["_property_comments"]
            
            for k, vals in props.items():
                # Resolve type
                type_def = resolve_type(k, name, schema)
                converted_vals = [convert_value(v, type_def) for v in vals]
                
                # Check if array or scalar
                is_array = False
                if type_def and type_def.get('type') == 'array':
                    is_array = True
                
                # Heuristic: if multiple values, force array. If single, check schema.
                if len(converted_vals) > 1:
                    clean_props[k] = converted_vals
                else:
                    # Single value
                    if is_array:
                        clean_props[k] = converted_vals
                    else:
                        clean_props[k] = converted_vals[0]
            
            processed_sections.append(clean_props)

        if name in singleton_sections:
            # Merge logic for singletons
            merged = {}
            merged_comments = []
            merged_prop_comments = defaultdict(list)
            
            for p in processed_sections:
                # Merge metadata
                if "_comments" in p:
                    merged_comments.extend(p["_comments"])
                if "_property_comments" in p:
                    for pk, pv in p["_property_comments"].items():
                        merged_prop_comments[pk].extend(pv)
                        
                for k, v in p.items():
                    if k.startswith("_"): continue
                    
                    if k in merged:
                        # Conflict? Listify?
                        if not isinstance(merged[k], list):
                             merged[k] = [merged[k]]
                        merged[k].append(v)
                    else:
                        merged[k] = v
            
            if merged_comments:
                merged["_comments"] = merged_comments
            if merged_prop_comments:
                merged["_property_comments"] = dict(merged_prop_comments)
                
            output[name] = merged
        else:
            # Repeated sections (Address)
            output[name] = processed_sections
            
    return output

def main():
    parser = argparse.ArgumentParser(description="Convert Systemd INI to JSON")
    parser.add_argument("file", help="Input INI file")
    parser.add_argument("--schema", help="Path to JSON Schema")
    args = parser.parse_args()
    
    if not args.schema:
        # Try to find a default schema relative to script
        # Assuming we are in tools/, schemas are in ../schemas/latest/systemd.network.schema.json
        # Only if converting .network
        
        ext = os.path.splitext(args.file)[1]
        schema_name = "systemd.network.schema.json"
        if ext == ".netdev": schema_name = "systemd.netdev.schema.json"
        if ext == ".link": schema_name = "systemd.link.schema.json"
        
        # Look in known locations
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(base, "schemas", "latest", schema_name)
        if os.path.exists(candidate):
            args.schema = candidate
        else:
             print("Error: No schema provided and could not auto-detect.", file=sys.stderr)
             sys.exit(1)

    schema = load_schema(args.schema)
    
    with open(args.file, 'r') as f:
        content = f.read()
        
    parsed = parse_ini(content)
    json_output = convert_to_json(parsed, schema)
    
    print(json.dumps(json_output, indent=2))

if __name__ == "__main__":
    main()
