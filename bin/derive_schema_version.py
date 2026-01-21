import json
import argparse
import sys
import copy

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def deep_diff_structure(base, target):
    """
    Returns a diff of properties that should be ADDED or REMOVED to align base with target.
    We care about:
    1. Properties present in target but not in base (ADD).
    2. Properties present in base but not in target (REMOVE).
    
    We do NOT care about definition details (type, description) because we assume Curated (base)
    properties have the correct curated definition, and we want to preserve that.
    
    We only look at the presence/absence of keys in "properties" dictionaries recursively.
    """
    diff = {
        "add": {},
        "remove": {}
    }
    
    # Check sections (top-level properties)
    base_props = base.get("properties", {})
    target_props = target.get("properties", {})
    
    # 1. Properties to Remove (in Base but not in Target)
    for key in list(base_props.keys()):
        if key not in target_props:
           diff["remove"][key] = True
        else:
            # Recurse if object
             base_sub = base_props[key]
             target_sub = target_props[key]
             
             # Handle OneOf wrappers in Generated schemas (Curated might have simplified)
             # The generated schema wraps repeated sections in OneOf [Array, Object].
             # Curated usually simplifies or keeps consistent.
             # We need to unwrap to compare the actual object properties.
             
             def unwrap(s):
                 if "properties" in s: return s
                 if "oneOf" in s:
                     for opt in s["oneOf"]:
                         if "properties" in opt: return opt
                         if "items" in opt and "properties" in opt["items"]: return opt["items"]
                 return s

             base_obj = unwrap(base_sub)
             target_obj = unwrap(target_sub)
             
             if "properties" in base_obj and "properties" in target_obj:
                 sub_diff = deep_diff_structure(base_obj, target_obj)
                 if sub_diff["add"] or sub_diff["remove"]:
                     diff["add"][key] = sub_diff["add"]
                     diff["remove"][key] = sub_diff["remove"]

    # 2. Properties to Add (in Target but not in Base)
    for key in target_props:
        if key not in base_props:
             diff["add"][key] = target_props[key] # Take the whole definition from target
             
    return diff

def apply_diff(curated, diff):
    result = copy.deepcopy(curated)
    
    def apply_recursive(obj, d_add, d_remove):
        if "properties" not in obj: return
        
        props = obj["properties"]
        
        # Remove
        for k, v in d_remove.items():
            if v is True: # Leaf removal
                if k in props:
                    print(f"  - Removing {k}")
                    del props[k]
            elif isinstance(v, dict): # Recursive removal
                if k in props:
                    # Unwrap Curated if needed
                     def unwrap(s):
                         if "properties" in s: return s
                         if "oneOf" in s:
                             for opt in s["oneOf"]:
                                 if "properties" in opt: return opt
                                 if "items" in opt and "properties" in opt["items"]: return opt["items"]
                         if "allOf" in s: # Curated often uses allOf $ref
                             # This is tricky. If it's a ref, we can't delete a property *inside* the ref definition easily.
                             # But here we are usually comparing Sections or Properties of Sections.
                             # If 'k' is a Section, it has properties.
                             return s
                         return s
                    
                     sub = unwrap(props[k])
                     if sub and "properties" in sub:
                         apply_recursive(sub, {}, v)
                         
        # Add property
        for k, v in d_add.items():
             if isinstance(v, dict) and "properties" not in v and "type" not in v and "oneOf" not in v:
                 # It's a nested diff
                 if k in props:
                     sub = unwrap(props[k])
                     if sub and "properties" in sub:
                         apply_recursive(sub, v, {})
             else:
                 # It's a new property definition
                 print(f"  + Adding {k}")
                 props[k] = v

    apply_recursive(result, diff["add"], diff["remove"])
    return result

def main():
    parser = argparse.ArgumentParser(description="Derive a curated schema for a target version.")
    parser.add_argument("--curated-base", required=True, help="Path to Curated vBase schema")
    parser.add_argument("--generated-base", required=True, help="Path to Generated vBase schema")
    parser.add_argument("--generated-target", required=True, help="Path to Generated vTarget schema")
    parser.add_argument("--out", required=True, help="Output path for Curated vTarget schema")
    parser.add_argument("--id-url", required=True, help="The $id URL for the new schema")
    
    args = parser.parse_args()
    
    print(f"Loading schemas...")
    curated_base = load_json(args.curated_base)
    generated_base = load_json(args.generated_base)
    generated_target = load_json(args.generated_target)
    
    # ... (diff computation)
    
    diff = deep_diff_structure(generated_base, generated_target)
    
    print(f"Applying diff to Curated Base...")
    new_schema = apply_diff(curated_base, diff)
    
    # Update Metadata
    if "title" in new_schema:
        # Update version in title "Systemd ... (v257)" -> (vTarget)
        # We assume generated_target['title'] has the correct version string
        target_ver = args.generated_target.split('.')[-3] # naive file parsing or extract from title
        new_schema["title"] = f"{new_schema['title'].split('(')[0].strip()} ({target_ver})"
        
    new_schema["$id"] = args.id_url

    # Update documentation links to point to the correct version
    target_ver_clean = args.generated_target.split('.')[-3].replace('v', '') # extract "241" from "...v241..."
    
    def update_doc_links(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "documentation" and isinstance(v, string_types):
                     # specific replace for the version in the URL
                     # Match: .../man/257/... -> .../man/{target_ver_clean}/...
                     # We only replace 257 if it follows /man/
                     obj[k] = v.replace("/man/257/", f"/man/{target_ver_clean}/")
                else:
                    update_doc_links(v)
        elif isinstance(obj, list):
            for item in obj:
                update_doc_links(item)

    # Python 3 compatibility for string check
    string_types = (str,)
    update_doc_links(new_schema)

    print(f"Saving to {args.out}")
    save_json(new_schema, args.out)

if __name__ == "__main__":
    main()
