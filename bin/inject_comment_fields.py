
import json
import glob
import os

def inject_comment_fields(path):
    print(f"Ensuring comment fields in {path}...")
    with open(path, 'r') as f:
        data = json.load(f)

    # Walk through properties and inject _comments/_property_comments
    # We look for objects with "additionalProperties": false or just any logical section
    
    properties = data.get("properties", {})
    
    for section_name, section_def in properties.items():
        if not isinstance(section_def, dict):
            continue
            
        # Helper to inject into a single object definition
        def inject_into_object(obj_def):
            if "properties" not in obj_def:
                obj_def["properties"] = {}
                
            props = obj_def["properties"]
            
            # Upsert the references
            props["_comments"] = { "$ref": "#/definitions/section_comments" }
            props["_property_comments"] = { "$ref": "#/definitions/property_comments" }
            
        # Logic to handle Object, Array of Objects, oneOf
        if section_def.get("type") == "object" and "properties" in section_def:
            inject_into_object(section_def)
            
        elif section_def.get("type") == "array" and section_def.get("items", {}).get("type") == "object":
            item_def = section_def["items"]
            if "properties" in item_def:
                inject_into_object(item_def)
                
        elif "oneOf" in section_def:
            for opt in section_def["oneOf"]:
                if opt.get("type") == "object" and "properties" in opt:
                    inject_into_object(opt)
                elif opt.get("type") == "array" and opt.get("items", {}).get("type") == "object":
                    item_def = opt["items"]
                    if "properties" in item_def:
                         inject_into_object(item_def)

    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    print(f"Updated {path}")

def main():
    # Find all curated schemas
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pattern = os.path.join(base_dir, "curated", "v*", "*.schema.json")
    files = glob.glob(pattern)
    
    for f in files:
        inject_comment_fields(f)

if __name__ == "__main__":
    main()
