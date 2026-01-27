#!/usr/bin/env python3
import sys
import json
import argparse
import os

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def format_value(val):
    if val is True: return "yes"
    if val is False: return "no"
    s = str(val)
    
    # Check if needs quoting
    # Characters/conditions that suggest quoting:
    # - Spaces, tabs, newlines
    # - Syntax chars: =, #, ;
    # - Backslashes or quotes
    # - Leading/trailing whitespace
    unsafe_chars = {' ', '\t', '\n', '\r', '"', "'", '=', '#', ';', '\\'}
    needs_quote = any(c in unsafe_chars for c in s) or (len(s) > 0 and (s[0].isspace() or s[-1].isspace()))
    
    if not needs_quote and len(s) > 0:
        return s
    
    if len(s) == 0:
        return '""'

    # Escaping for double-quoted string
    out = []
    for char in s:
        if char == '\\': out.append('\\\\')
        elif char == '"': out.append('\\"')
        elif char == '\n': out.append('\\n')
        elif char == '\r': out.append('\\r')
        elif char == '\t': out.append('\\t')
        elif char == '\b': out.append('\\b')
        elif char == '\f': out.append('\\f')
        # \v is not standard in python string escapes usually but systemd supports it.
        # standard printable?
        else: out.append(char)
        
    return '"' + "".join(out) + '"'

def write_ini(data, out_file):
    # Order sections? Match, Link, Network, Address, Route, etc.
    # We can try to respect standard order or alphabetical.
    # Systemd doesn't care strictly, but Match usually first.
    
    order = ["Match", "Link", "Network", "Address", "Route", "DHCPServer", "DHCPv4", "DHCPv6"]
    
    # Sort keys of data based on priority list + others alphabetical
    keys = sorted(data.keys(), key=lambda k: (order.index(k) if k in order else 999, k))
    
    first = True
    
def write_ini(data, out_file):
    # Order sections? Match, Link, Network, Address, Route, etc.
    # We can try to respect standard order or alphabetical.
    # Systemd doesn't care strictly, but Match usually first.
    
    order = ["Match", "Link", "Network", "Address", "Route", "DHCPServer", "DHCPv4", "DHCPv6"]
    
    # Sort keys of data based on priority list + others alphabetical
    keys = sorted(data.keys(), key=lambda k: (order.index(k) if k in order else 999, k))
    
    first = True
    
    for section_name in keys:
        content = data[section_name]
        
        # Singleton Section (Object)
        if isinstance(content, dict):
             if not first: out_file.write("\n")
             
             # Write Section Comments
             if "_comments" in content:
                 for c in content["_comments"]:
                     out_file.write(f"{c}\n")
                     
             out_file.write(f"[{section_name}]\n")
             
             prop_comments = content.get("_property_comments", {})
             
             for k, v in content.items():
                 if k.startswith("_"): continue # Skip metadata
                 
                 # Write Property Comments
                 if k in prop_comments:
                     for c in prop_comments[k]:
                         out_file.write(f"{c}\n")
                 
                 if isinstance(v, list):
                     for item in v:
                         out_file.write(f"{k}={format_value(item)}\n")
                 else:
                     out_file.write(f"{k}={format_value(v)}\n")
             first = False
             
        # Repeated Section (Array of Objects)
        elif isinstance(content, list):
             for item in content:
                 if not first: out_file.write("\n")
                 
                 # Write Section Comments
                 if "_comments" in item:
                     for c in item["_comments"]:
                         out_file.write(f"{c}\n")
                         
                 out_file.write(f"[{section_name}]\n")
                 
                 prop_comments = item.get("_property_comments", {})
                 
                 for k, v in item.items():
                     if k.startswith("_"): continue # Skip metadata
                     
                     # Write Property Comments
                     if k in prop_comments:
                         for c in prop_comments[k]:
                             out_file.write(f"{c}\n")
                             
                     if isinstance(v, list):
                         for sub in v:
                             out_file.write(f"{k}={format_value(sub)}\n")
                     else:
                         out_file.write(f"{k}={format_value(v)}\n")
                 first = False

def main():
    parser = argparse.ArgumentParser(description="Convert JSON to Systemd INI")
    parser.add_argument("file", help="Input JSON file")
    args = parser.parse_args()
    
    data = load_json(args.file)
    write_ini(data, sys.stdout)

if __name__ == "__main__":
    main()
