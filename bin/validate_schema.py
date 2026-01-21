import json
import sys
import os

try:
    import jsonschema
    from jsonschema import Draft7Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

def validate_file(path):
    print(f"Validating {path}...")
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            
        # Basic JSON Check passed if we are here
        
        if HAS_JSONSCHEMA:
            # 1. Check if it is a valid schema against the Meta-Schema (Draft 7)
            try:
                Draft7Validator.check_schema(data)
                print("  [Meta-Schema] Valid Draft-07 Schema.")
            except jsonschema.exceptions.SchemaError as e:
                print(f"FAILED: {path } - Meta-Schema Validation Error")
                print(e.message)
                return False
                
            # 2. Check if the schema claims to be draft-07
            if data.get("$schema") != "http://json-schema.org/draft-07/schema#":
                 print(f"WARNING: $schema is not set to draft-07 in {path}")
                 
        else:
            print("  [Warning] 'jsonschema' library not found. Performing structural checks only.")
            # Basic Structural Checks
            errors = []
            if "$schema" not in data:
                errors.append("Missing $schema")
            if "definitions" not in data:
                errors.append("Missing definitions")
            if "properties" not in data:
                errors.append("Missing properties")
                
            if errors:
                print(f"FAILED: {path}")
                for e in errors:
                    print(f"  - {e}")
                return False
            
        print("OK")
        return True
        
    except json.JSONDecodeError as e:
        print(f"FAILED: {path} - Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"FAILED: {path} - {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: validate_schema.py <file1> <file2> ...")
        sys.exit(1)
        
    success = True
    for f in sys.argv[1:]:
        if not validate_file(f):
            success = False
            
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
