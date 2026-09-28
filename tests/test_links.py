"""Tests for the pandoc AST repairs in epub2pdf.links."""

import typst

from epub2pdf import links
from epub2pdf.cli import typeset

EXTRA = (
    '<html xmlns="http://www.w3.org/1999/xhtml"><body><p id="x">Aside</p></body></html>'
)


def test_points_dead_fragment_at_its_chapter(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<p><a href="ch2.xhtml#missing">Dead</a></p>',
            "ch2.xhtml": "<p>Two</p>",
        }
    )
    assert "#link(<ch2.xhtml>)[Dead]" in typeset(epub, tmp_path).read_text()


def test_finds_chapter_whose_name_contains_htm(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<p><a href="a.htm.xhtml#missing">Htm</a></p>',
            "a.htm.xhtml": "<p>Two</p>",
        }
    )
    assert "#link(<a.htm.xhtml>)[Htm]" in typeset(epub, tmp_path).read_text()


def test_unwraps_links_to_nothing_in_the_spine(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<p><a href="extra.xhtml#x">Extra</a> '
            '<a href="ch2.html#s">Html</a> '
            '<a href="../images/pic.png">Picture</a></p>'
        },
        files={"text/extra.xhtml": EXTRA},
        manifest='<item id="extra" href="text/extra.xhtml" '
        'media-type="application/xhtml+xml"/>',
    )
    source = typeset(epub, tmp_path).read_text()
    assert "Extra Html Picture" in source
    assert "#link(" not in source


def test_keeps_links_with_a_scheme(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<p><a href="https://example.com/a.html#b">Web</a> '
            '<a href="mailto:me@example.com">Mail</a></p>'
        }
    )
    source = typeset(epub, tmp_path).read_text()
    assert '#link("https://example.com/a.html#b")[Web]' in source
    assert '#link("mailto:me@example.com")[Mail]' in source


def test_anchors_linked_ids_that_typst_would_lose(make_epub, tmp_path, fonts):
    epub = make_epub(
        {
            "my ch.xhtml": '<p><img id="pic" src="../images/pic.png" alt=""/></p>'
            '<p>Text<a id="ref" href="ch2.xhtml#note" class="noteref">1</a></p>',
            "ch2.xhtml": '<p id="note"><a href="my%20ch.xhtml">Start</a> '
            '<a href="my%20ch.xhtml#pic">Picture</a> '
            '<a href="my%20ch.xhtml#ref">Back</a></p>',
        }
    )
    typst.compile(typeset(epub, tmp_path), root=tmp_path, font_paths=fonts)


def test_escapes_label_quotes():
    doc = {
        "blocks": [
            {"t": "Para", "c": [{"t": "Span", "c": [['a"b\\c', [], []], []]}]},
            {
                "t": "Para",
                "c": [{"t": "Link", "c": [["", [], []], [], ['#a"b\\c', ""]]}],
            },
        ]
    }
    links.fix(doc)
    assert doc["blocks"][0]["c"][0] == {
        "t": "RawInline",
        "c": ["typst", '#metadata(none)#label("a\\"b\\\\c");'],
    }


def test_hoists_anchors_out_of_headings(make_epub, tmp_path, fonts):
    epub = make_epub(
        {"ch1.xhtml": '<h2><span id="h">Title</span></h2><p><a href="#h">Up</a></p>'}
    )
    typst.compile(typeset(epub, tmp_path), root=tmp_path, font_paths=fonts)


def test_hoists_anchors_out_of_repeated_table_rows(make_epub, tmp_path, fonts):
    epub = make_epub(
        {
            "ch1.xhtml": '<p><a href="#th">Head</a> <a href="#tf">Foot</a></p>'
            '<table><thead><tr><th><span id="th">Name</span></th></tr></thead>'
            f"<tbody>{'<tr><td>row</td></tr>' * 120}</tbody>"
            '<tfoot><tr><td><span id="tf">Total</span></td></tr></tfoot></table>'
        }
    )
    typst.compile(typeset(epub, tmp_path), root=tmp_path, font_paths=fonts)


def test_keeps_line_breaks_inside_headings(make_epub, tmp_path, fonts):
    epub = make_epub({"ch1.xhtml": "<h1>Chapter 1<br/>(Start)</h1>"})
    bodies = typst.query(
        typeset(epub, tmp_path),
        "heading",
        field="body",
        root=tmp_path,
        font_paths=fonts,
    )
    assert "(Start)" in bodies


def test_ends_images_before_a_parenthesis(make_epub, tmp_path, fonts):
    epub = make_epub({"ch1.xhtml": '<p><img src="../images/pic.png" alt=""/>(1)</p>'})
    typst.compile(typeset(epub, tmp_path), root=tmp_path, font_paths=fonts)


def test_raises_note_references(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<p>Text<a href="ch2.xhtml#n1" class="noteref">1</a>'
            '<a href="ch2.xhtml#n2" role="doc-noteref">2</a></p>',
            "ch2.xhtml": '<section id="n1"><p>One</p></section>'
            '<section id="n2"><p>Two</p></section>',
        }
    )
    source = typeset(epub, tmp_path).read_text()
    assert "#link(<ch2.xhtml_n1>)[#super[1];]" in source
    assert "#link(<ch2.xhtml_n2>)[#super[2];]" in source


def test_drops_inserted_cover_when_book_shows_it(make_epub, tmp_path):
    epub = make_epub(
        {
            "cover.xhtml": '<p><img src="../images/pic.png" alt=""/></p>',
            "ch1.xhtml": "<p>One</p>",
        },
        metadata='<dc:title>Test</dc:title><meta name="cover" content="pic"/>',
    )
    assert typeset(epub, tmp_path).read_text().count('image("') == 1


def test_keeps_inserted_cover_when_book_lacks_it(make_epub, tmp_path):
    epub = make_epub(
        {"ch1.xhtml": "<p>One</p>"},
        metadata='<dc:title>Test</dc:title><meta name="cover" content="pic"/>',
    )
    assert typeset(epub, tmp_path).read_text().count('image("') == 1


HOOK = "\N{LEFTWARDS ARROW WITH HOOK}"
UP = "\N{UPWARDS ARROW}"


def test_replaces_backlink_arrows(make_epub, tmp_path):
    text = f"{HOOK}\N{VARIATION SELECTOR-15} {HOOK}\N{VARIATION SELECTOR-16} {HOOK}"
    epub = make_epub({"ch1.xhtml": f"<p>{text}</p>"})
    assert f"{UP} {UP} {UP}\n" in typeset(epub, tmp_path).read_text()


def test_repairs_metadata_too():
    title = {"t": "MetaInlines", "c": [{"t": "Str", "c": HOOK}]}
    doc = {"meta": {"title": title}, "blocks": []}
    links.fix(doc)
    assert title["c"] == [{"t": "Str", "c": UP}]


def test_fills_empty_square_roots(make_epub, tmp_path, fonts):
    epub = make_epub(
        {
            "ch1.xhtml": '<p><math xmlns="http://www.w3.org/1998/Math/MathML">'
            "<msqrt></msqrt></math></p>"
        }
    )
    typst.compile(typeset(epub, tmp_path), root=tmp_path, font_paths=fonts)
