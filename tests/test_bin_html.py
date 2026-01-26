import sys
import os
import pytest
import xml.etree.ElementTree as ET

# Allow importing from bin/
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bin'))
import generate_html

class TestDocbookRendering:
    def parse_xml(self, string):
        return ET.fromstring(string)

    def test_render_para(self):
        elem = self.parse_xml('<root><para>Hello World</para></root>')
        html = generate_html.render_docbook_content(elem, "v257")
        assert "<p>Hello World</p>" in html

    def test_render_listitem(self):
        elem = self.parse_xml('<root><listitem><para>Item</para></listitem></root>')
        html = generate_html.render_docbook_content(elem, "v257")
        assert "<li><p>Item</p></li>" in html

    def test_render_variablelist_entry(self):
        # varlistentry handling is usually custom in main loop but helper handles nested ones
        elem = self.parse_xml('''
        <root>
        <varlistentry>
            <term>Term</term>
            <listitem><para>Desc</para></listitem>
        </varlistentry>
        </root>
        ''')
        html = generate_html.render_docbook_content(elem, "v257")
        # The helper renders <term> as generic span if not handled?
        # Let's check generate_html.py again.
        # It handles 'varlistentry' tag inside the loop.
        # Inside 'varlistentry' block:
        #   term = child.find(".//term")
        #   listitem = child.find(".//listitem")
        #   out.append(f'<dt>{render...}</dt>')
        #   out.append(f'<dd>{render...}</dd>')
        assert "<dt>Term</dt>" in html
        assert "<dd><p>Desc</p></dd>" in html

    def test_render_literal(self):
        elem = self.parse_xml('<root><literal>foo</literal></root>')
        html = generate_html.render_docbook_content(elem, "v257")
        assert "<code>foo</code>" in html

    def test_render_with_tail_text(self):
        # <para>Foo <literal>bar</literal> baz</para>
        # Here we test rendering OF para content. 
        # So input IS para.
        elem = self.parse_xml('<para>Foo <literal>bar</literal> baz</para>')
        html = generate_html.render_docbook_content(elem, "v257")
        # It renders children.
        # Text "Foo" is elem.text.
        # Child <literal>bar</literal> is processed.
        # Tail " baz" is child.tail.
        assert "Foo" in html
        assert "baz" in html
        assert "<code>bar</code>" in html
