import json
import os
import glob

SCHEMA_DIR = "curated/v257"

def rename_types_in_file(filepath):
    print(f"Processing {filepath}...")
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    if 'definitions' not in data:
        print("  No definitions found.")
        return

    definitions = data['definitions']
    new_definitions = {}
    renamed_map = {} # old_name -> new_name

    # 1. Rename Definitions
    for key, value in definitions.items():
        if not key.endswith("Type"):
            new_name = key + "Type"
            renamed_map[key] = new_name
            new_definitions[new_name] = value
        else:
            new_definitions[key] = value
            
    data['definitions'] = new_definitions
    
    # 2. Update References
    def recursive_update_refs(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "$ref" and isinstance(v, str):
                    if v.startswith("#/definitions/"):
                        old_ref = v.split("/")[-1]
                        if old_ref in renamed_map:
                            obj[k] = f"#/definitions/{renamed_map[old_ref]}"
                else:
                    recursive_update_refs(v)
        elif isinstance(obj, list):
            for item in obj:
                recursive_update_refs(item)

    recursive_update_refs(data)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print("  Done.")

def main():
    files = glob.glob(os.path.join(SCHEMA_DIR, "*.json"))
    for f in files:
        rename_types_in_file(f)

if __name__ == "__main__":
    main()
