import sys
import os
import pytest

# Allow importing from bin/
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bin'))
import derive_schema_version

class TestSchemaDerivation:
    def test_deep_diff_add(self):
        base = {"properties": {"A": {}}}
        target = {"properties": {"A": {}, "B": {}}}
        
        diff = derive_schema_version.deep_diff_structure(base, target)
        
        assert "B" in diff["add"]
        assert "A" not in diff["add"]
        
    def test_deep_diff_remove(self):
        base = {"properties": {"A": {}, "B": {}}}
        target = {"properties": {"A": {}}}
        
        diff = derive_schema_version.deep_diff_structure(base, target)
        
        assert "B" in diff["remove"]
        assert diff["remove"]["B"] is True # Leaf removal
        
    def test_deep_diff_recursive(self):
        base = {"properties": {"Sec": {"properties": {"A": {}}}}}
        target = {"properties": {"Sec": {"properties": {"A": {}, "B": {}}}}}
        
        diff = derive_schema_version.deep_diff_structure(base, target)
        
        # The return structure when modifying existing key is diff["add"][key] = sub_diff["add"]
        # So diff["add"]["Sec"] is the dictionary of added properties to 'Sec'.
        
        assert "Sec" in diff["add"]
        assert "B" in diff["add"]["Sec"]
        
    def test_deep_diff_unwrap_oneof(self):
        # Target has wrapped oneOf (common in generated)
        base = {"properties": {"Sec": {"properties": {"A": {}}}}}
        target = {
            "properties": {
                "Sec": {
                    "oneOf": [
                        {"type": "array", "items": {"properties": {"A": {}, "B": {}}}},
                        {"type": "object"}
                    ]
                }
            }
        }
        # OneOf unwrapping logic in deep_diff_structure should handle this
        diff = derive_schema_version.deep_diff_structure(base, target)
        assert "Sec" in diff["add"]
        assert "B" in diff["add"]["Sec"]

    def test_apply_diff(self):
        base = {"properties": {"A": {}, "B": {}}}
        diff = {
            "add": {"C": {"type": "string"}},
            "remove": {"B": True}
        }
        
        new_schema = derive_schema_version.apply_diff(base, diff)
        
        assert "A" in new_schema["properties"]
        assert "B" not in new_schema["properties"]
        assert "C" in new_schema["properties"]
        
    def test_apply_diff_recursive(self):
        base = {"properties": {"Sec": {"properties": {"A": {}, "B": {}}}}}
        diff = {
            "add": {"Sec": {"add": {"C": {}}, "remove": {}}},
            "remove": {"Sec": {"remove": {"B": True}, "add": {}}}
        }
        # The structure of diff returned by deep_diff is {'add': {}, 'remove': {}}
        # But inside recursive calls it passes the sub-dicts.
        # Wait, apply_diff expects the root diff object structure?
        # No, apply_diff takes (curated, diff). 
        # diff["add"] is a dict of keys to add (or recursive dicts).
        # diff["remove"] is a dict of keys to remove.
        # The structure of recursive diff in deep_diff is:
        # diff["add"][key] = sub_diff["add"] if recursive
        
        # Let's verify deep_diff output structure for recursive
        # If Sec/B is added:
        # diff['add']['Sec'] = { 'B': {def} } -- this is if it's new
        # If Sec exists and we add B inside:
        # diff['add']['Sec'] = { 'B': ... } ??
        # Looking at deep_diff_structure:
        # diff["add"][key] = sub_diff["add"]
        # So yes, it nests the "add" part.
        
        # So to emulate a recursive add of C inside Sec:
        diff = {
            "add": {"Sec": {"C": {"type": "string"}}},
            "remove": {"Sec": {"B": True}}
        }
        
        # NOTE: logic in apply_diff handles nested dicts in 'add' as recursion instructions 
        # IF they don't look like property definitions (no 'type', 'properties', 'oneOf').
        
        new_schema = derive_schema_version.apply_diff(base, diff)
        
        sec_props = new_schema["properties"]["Sec"]["properties"]
        assert "A" in sec_props
        assert "B" not in sec_props
        assert "C" in sec_props
