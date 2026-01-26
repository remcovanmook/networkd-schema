import json
import os

FILES = [
    "curated/v257/systemd.link.v257.schema.json",
    "curated/v257/systemd.network.v257.schema.json"
]

GLOBS_TYPE = {
    "type": "string",
    "description": "A whitespace-separated list of shell-style globs.",
    "title": "Shell Globs",
    "pattern": "^(!\\s*)?\\S+(\\s+\\S+)*$",
    "examples": [
        "eth*",
        "en* wlan*",
        "!virbr*",
        "!eth0 eth1"
    ]
}

def refactor_file(filepath):
    print(f"Processing {filepath}...")
    with open(filepath, 'r') as f:
        data = json.load(f)

    # 1. Clean existing definition to avoid recursion or double processing
    if "definitions" in data and "globsType" in data["definitions"]:
        del data["definitions"]["globsType"]
    
    # 2. Refactor Properties
    def recursive_refactor(obj):
        if isinstance(obj, dict):
            # Check if this object is a property definition that needs refactor
            if "description" in obj and "shell-style globs" in obj["description"]:
                # It's a target!
                # Remove 'type' if present
                if "type" in obj:
                    del obj["type"]
                
                # Add $ref
                obj["$ref"] = "#/definitions/globsType"
                
                # We interpret "Consolidate strings" as "Use the type".
                # We KEEP the specific description.
                
            for k, v in obj.items():
                recursive_refactor(v)
        elif isinstance(obj, list):
            for item in obj:
                recursive_refactor(item)

    recursive_refactor(data)
    
    # 3. Add Definition (Safe from self-refactor now)
    if "definitions" not in data:
        data["definitions"] = {}
    data["definitions"]["globsType"] = GLOBS_TYPE
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print("  Done.")

def main():
    for f in FILES:
        if os.path.exists(f):
            refactor_file(f)
        else:
            print(f"File not found: {f}")

if __name__ == "__main__":
    main()
