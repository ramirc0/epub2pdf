"""Tests for the EPUB repairs in epub2pdf.repack."""

from epub2pdf import repack
from epub2pdf.cli import typeset

OUTLINE = "#outline(\n  title: auto,\n  depth: 2\n);"


def test_generates_contents_when_nav_is_outside_spine(make_epub, tmp_path):
    epub = make_epub({"ch1.xhtml": "<h1>One</h1>"})
    assert OUTLINE in typeset(epub, tmp_path).read_text()


def test_keeps_nav_in_spine_as_contents(make_epub, tmp_path):
    epub = make_epub({"ch1.xhtml": "<h1>One</h1>"}, nav_in_spine=True)
    assert "#outline(" not in typeset(epub, tmp_path).read_text()


def test_keeps_guide_contents_page_in_spine(make_epub, tmp_path):
    epub = make_epub(
        {
            "toc.xhtml": '<p><a href="ch1.xhtml">One</a></p>',
            "ch1.xhtml": "<h1>One</h1>",
        },
        guide='<guide><reference type="toc" title="Contents" href="text/toc.xhtml"/>'
        "</guide>",
    )
    assert "#outline(" not in typeset(epub, tmp_path).read_text()


def test_generates_contents_when_any_package_lacks_them(make_epub, tmp_path):
    epub = make_epub(
        {"ch1.xhtml": "<h1>One</h1>"},
        nav_in_spine=True,
        files={"other.opf": "<package><manifest/><spine/></package>"},
    )
    assert repack.repack(epub, tmp_path / "fixed.epub")
