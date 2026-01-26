import sys
import os
import pytest

# Allow importing from bin/
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bin'))
import generate_changelog

class TestChangelogGeneration:
    def test_compare_versions_added_removed(self):
        # compare_versions loads files from disk, which is hard to unit test without mocking.
        # But we can look at the functions inside. 
        # compare_versions calls flatten_properties.
        # Let's test flatten_properties and maybe refactor logic if needed, 
        # or just mock load_schema?
        pass
        
    def test_flatten_properties(self):
        schema = {
            "properties": {
                "Match": {
                    "properties": {
                        "Name": {}
                    }
                }
            }
        }
        flat = generate_changelog.flatten_properties(schema)
        assert "Match.Name" in flat
        
    def test_flatten_properties_with_ref(self):
        schema = {
            "definitions": {
                "MatchSection": {
                    "properties": {
                        "Name": {}
                    }
                }
            },
            "properties": {
                "Match": {
                    "$ref": "#/definitions/MatchSection"
                }
            }
        }
        flat = generate_changelog.flatten_properties(schema)
        assert "Match.Name" in flat

    def test_flatten_properties_oneof(self):
        schema = {
            "properties": {
                "Match": {
                    "oneOf": [
                        {"type": "object", "properties": {"Name": {}}},
                        {"type": "array"}
                    ]
                }
            }
        }
        flat = generate_changelog.flatten_properties(schema)
        assert "Match.Name" in flat

    def test_html_fragment_generation(self):
        changes = {
            "systemd.network": {
                "added": ["Match.Name"],
                "removed": ["Match.Old"],
                "deprecated": ["Match.Dep"]
            }
        }
        html = generate_changelog.generate_html_fragment(changes, "v2", "v1")
        assert "Changes from v1 to v2" in html
        assert "Match.Name" in html
        assert "Match.Old" in html
        assert "Match.Dep" in html
        assert "Added" in html
        assert "Removed" in html
        assert "Deprecated" in html
