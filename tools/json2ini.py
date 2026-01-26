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
    return str(val)

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
             out_file.write(f"[{section_name}]\n")
             for k, v in content.items():
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
                 out_file.write(f"[{section_name}]\n")
                 for k, v in item.items():
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
