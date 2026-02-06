import sys
import os
import unittest
import xml.etree.ElementTree as ET

# Allow importing from bin/
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bin'))
from generate_html import HtmlGenerator, PageGenerator, TypesGenerator

class TestHtmlGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = HtmlGenerator("/tmp", "v257")

    def parse_xml(self, string):
        return ET.fromstring(string)

    def test_linkify_section_references(self):
        text = "See [Match] section."
        self.assertEqual(self.generator.linkify_section_references(text), 'See <a href="#section-Match" class="section-ref">[Match]</a> section.')
        self.assertEqual(self.generator.linkify_section_references(text, in_code_block=True), text)
        text_assign = "Key=[Match]"
        self.assertEqual(self.generator.linkify_section_references(text_assign), text_assign)

    def test_render_docbook_para(self):
        elem = self.parse_xml('<root><para>Hello World</para></root>')
        html = self.generator.render_docbook_content(elem, "v257")
        self.assertIn("<p>Hello World</p>", html)

    def test_render_docbook_nested(self):
        elem = self.parse_xml('<root><para>Foo <literal>in code</literal></para></root>')
        html = self.generator.render_docbook_content(elem, "v257")
        self.assertIn("<p>Foo <code>in code</code></p>", html)

    def test_render_varlistentry(self):
        elem = self.parse_xml('''
        <root>
        <varlistentry>
            <term>Term</term>
            <listitem><para>Desc</para></listitem>
        </varlistentry>
        </root>
        ''')
        html = self.generator.render_docbook_content(elem, "v257")
        self.assertIn("<dt>Term</dt>", html)
        self.assertIn("<dd><p>Desc</p></dd>", html)

class TestPageGenerator(unittest.TestCase):
    def setUp(self):
        # Mock schema needs definitions for refs
        self.generator = PageGenerator("/tmp", "v257", "/src", "/schema")
        self.generator.schema = {
            'definitions': {
                'fooType': {'title': 'Foo Object', 'type': 'object'},
                'barType': {'type': 'integer'},
            },
            'properties': {}
        }

    def test_calculate_type_label_simple(self):
        s = {'type': 'string'}
        self.assertEqual(self.generator.calculate_type_label(s), 'string')
        
    def test_calculate_type_label_ref(self):
        s = {'$ref': '#/definitions/fooType'}
        self.assertEqual(self.generator.calculate_type_label(s), 'Foo Object')
        
        s2 = {'$ref': '#/definitions/barType'}
        self.assertEqual(self.generator.calculate_type_label(s2), 'integer')

    def test_calculate_type_label_oneof(self):
        s = {'oneOf': [{'type': 'string'}, {'type': 'integer'}]}
        self.assertEqual(self.generator.calculate_type_label(s), 'integer | string')

    def test_calculate_type_label_array(self):
        s = {'type': 'array', 'items': {'type': 'string'}}
        self.assertEqual(self.generator.calculate_type_label(s), 'string')

class TestTypesGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = TypesGenerator("/tmp", "v257")

    def test_describe_type_structure(self):
        # Integer Range
        s = {'type': 'integer', 'minimum': 0, 'maximum': 100}
        self.assertEqual(self.generator._describe_type_structure(s, {}), "Integer (0...100)")
        
        # String Length
        s2 = {'type': 'string', 'minLength': 1}
        self.assertIn("length 1...inf", self.generator._describe_type_structure(s2, {}))
        
        # Enum
        s3 = {'enum': ['a', 'b']}
        self.assertIn("Enum: <code>a</code>, <code>b</code>", self.generator._describe_type_structure(s3, {}))
        
        # oneOf
        s4 = {'oneOf': [{'type': 'string'}, {'type': 'integer'}]}
        desc = self.generator._describe_type_structure(s4, {})
        self.assertIn("String", desc)
        self.assertIn("Integer", desc)
        self.assertIn(" OR ", desc)

if __name__ == '__main__':
    unittest.main()
