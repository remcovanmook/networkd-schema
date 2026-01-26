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

def parse_ini(content):
    """
    Parses INI content into a structure:
    {
      "SectionName": [ {"Key": ["Val1", "Val2"]}, {"Key": ["Val"]} ] 
    }
    Wait, repeated sections...
    Structure:
    List of Section Objects. Each Section Object has a Name and Properties.
    [
        { "name": "Match", "props": {"Name": ["en*"]} },
        { "name": "Network", "props": {"DHCP": ["yes"]} },
        { "name": "Address", "props": {"Address": ["1.1.1.1/24"]} },
        { "name": "Address", "props": {"Address": ["2.2.2.2/24"]} }
    ]
    """
    sections = []
    current_section = None
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue
            
        # Check continuation (simple heuristic: ends with \) - systemd supports this? 
        # Yes, line continuation is supported.
        # But let's stick to basic processing first or assume the input is clean.
        
        match_sec = SECTION_RE.match(line)
        if match_sec:
            current_section = {
                "name": match_sec.group(1),
                "props": defaultdict(list)
            }
            sections.append(current_section)
            continue
            
        match_kv = KEY_VAL_RE.match(line)
        if match_kv and current_section:
            k = match_kv.group(1).strip()
            v = match_kv.group(2).strip()
            # Handle quotes? Systemd usually takes raw values, but quotes can be used.
            # We'll take raw for now or strip surrounding quotes if present.
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                 v = v[1:-1]
            current_section["props"][k].append(v)
            
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
    grouped = defaultdict(list)
    for sec in sections:
        grouped[sec['name']].append(sec['props'])
        
    for name, list_of_props in grouped.items():
        processed_sections = []
        
        for props in list_of_props:
            clean_props = {}
            for k, vals in props.items():
                # Resolve type
                type_def = resolve_type(k, name, schema)
                converted_vals = [convert_value(v, type_def) for v in vals]
                
                # Check if array or scalar
                # If schema accepts array, use array. If schema expects scalar, use last item?
                # Systemd: duplicate keys usually mean list.
                # If schema has "type": "array" OR logic implies list.
                # Actually our schema defines almost everything as scalar or reference.
                # Wait, "DNS" in Network is a list.
                
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
            # Merge logic for singletons?
            # User might define [Match] ... [Match] ...
            # Systemd merges them.
            merged = {}
            for p in processed_sections:
                for k, v in p.items():
                    if k in merged:
                        # Conflict? Listify?
                        if not isinstance(merged[k], list):
                             merged[k] = [merged[k]]
                        merged[k].append(v)
                    else:
                        merged[k] = v
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
