import sys
import os
import pytest
from unittest.mock import MagicMock

# Allow importing from tools/
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'tools'))
import ini2json

class TestIniParsing:
    def test_parse_simple_ini(self):
        content = """
        [Match]
        Name=eth0
        """
        sections = ini2json.parse_ini(content)
        assert len(sections) == 1
        assert sections[0]['name'] == 'Match'
        assert sections[0]['props']['Name'] == ['eth0']

    def test_parse_repeated_keys(self):
        content = """
        [Network]
        DNS=8.8.8.8
        DNS=1.1.1.1
        """
        sections = ini2json.parse_ini(content)
        assert len(sections) == 1
        assert sections[0]['props']['DNS'] == ['8.8.8.8', '1.1.1.1']

    def test_parse_multiple_sections(self):
        content = """
        [Match]
        Name=eth0
        
        [Network]
        DHCP=yes
        """
        sections = ini2json.parse_ini(content)
        assert len(sections) == 2
        assert sections[0]['name'] == 'Match'
        assert sections[1]['name'] == 'Network'

class TestTypeConversion:
    def test_convert_boolean(self):
        # type_def = {'type': 'boolean'}
        assert ini2json.convert_value('yes', {'type': 'boolean'}) is True
        assert ini2json.convert_value('no', {'type': 'boolean'}) is False
        assert ini2json.convert_value('true', {'type': 'boolean'}) is True
        assert ini2json.convert_value('0', {'type': 'boolean'}) is False
        
    def test_convert_integer(self):
        assert ini2json.convert_value('123', {'type': 'integer'}) == 123
        assert ini2json.convert_value('invalid', {'type': 'integer'}) == 'invalid' # Fallback

class TestResolveType:
    def test_resolve_simple(self):
        schema = {
            'properties': {
                'Match': {
                    'properties': {
                        'Name': {'type': 'string'}
                    }
                }
            }
        }
        res = ini2json.resolve_type('Name', 'Match', schema)
        assert res['type'] == 'string'

    def test_resolve_nested_ref(self):
        schema = {
            'definitions': {
                'nameType': {'type': 'string'}
            },
            'properties': {
                'Match': {
                    'properties': {
                        'Name': {'$ref': '#/definitions/nameType'}
                    }
                }
            }
        }
        res = ini2json.resolve_type('Name', 'Match', schema)
        assert res['type'] == 'string'

class TestJsonConversion:
    def test_singleton_section_merge(self):
        # Verify that multiple [Match] sections get merged if schema says it's singleton
        schema = {
            'properties': {
                'Match': {'type': 'object', 'properties': {'Name': {'type': 'string'}, 'Type': {'type': 'string'}}}
            }
        }
        sections = [
            {'name': 'Match', 'props': {'Name': ['eth0']}},
            {'name': 'Match', 'props': {'Type': ['wired']}}
        ]
        
        output = ini2json.convert_to_json(sections, schema)
        # Should be { "Match": { "Name": "eth0", "Type": "wired" } }
        assert output['Match']['Name'] == 'eth0'
        assert output['Match']['Type'] == 'wired'

    def test_array_conversion(self):
        schema = {
             'properties': {
                 'Network': {'type': 'object', 'properties': {'DNS': {'type': 'array', 'items': {'type': 'string'}}}}
             }
        }
        sections = [
            {'name': 'Network', 'props': {'DNS': ['8.8.8.8', '1.1.1.1']}}
        ]
        output = ini2json.convert_to_json(sections, schema)
        assert output['Network']['DNS'] == ['8.8.8.8', '1.1.1.1']
