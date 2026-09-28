"""Tests for the pandoc AST repairs in epub2pdf.links."""

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
