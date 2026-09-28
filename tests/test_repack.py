"""Tests for the EPUB repairs in epub2pdf.repack."""

import zipfile

import pytest
import typst

from epub2pdf import repack
from epub2pdf.cli import typeset

OUTLINE = "#outline(\n  title: auto,\n  depth: 2\n);"
CH2 = (
    '<html xmlns="http://www.w3.org/1999/xhtml">'
    '<body><section id="s"><p>Two</p></section></body></html>'
)


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


def test_drops_manifest_items_missing_from_archive(make_epub, tmp_path):
    epub = make_epub(
        {"ch1.xhtml": "<p>One</p>"},
        manifest='<item id="gone" href="text/gone.xhtml" '
        'media-type="application/xhtml+xml"/>',
        spine='<itemref idref="gone"/>',
    )
    assert "One" in typeset(epub, tmp_path).read_text()


def test_trims_padded_paths(make_epub, tmp_path, fonts):
    epub = make_epub(
        {
            "ch1.xhtml": '<p><img src=" ../images/pic.png " alt=""/> '
            '<a href=" ch2.xhtml#s ">Two</a></p>'
        },
        files={"text/ch2.xhtml": CH2},
        manifest='<item id="ch2" href=" text/ch2.xhtml " '
        'media-type="application/xhtml+xml"/>',
        spine='<itemref idref="ch2"/>',
    )
    book = typeset(epub, tmp_path)
    assert "#link(<ch2.xhtml_s>)[Two]" in book.read_text()
    typst.compile(book, root=tmp_path, font_paths=fonts)


def test_drops_images_that_are_empty_or_not_images(make_epub, tmp_path, fonts):
    epub = make_epub(
        {
            "ch1.xhtml": '<p><img src="../images/bad.png" alt=""/>'
            '<img src="../images/bad.jpg" alt=""/>'
            '<img src="../images/pic.png" alt=""/></p>'
        },
        files={"images/bad.png": b"", "images/bad.jpg": b"<html></html>"},
        manifest='<item id="b1" href="images/bad.png" media-type="image/png"/>'
        '<item id="b2" href="images/bad.jpg" media-type="image/jpeg"/>',
    )
    book = typeset(epub, tmp_path)
    source = book.read_text()
    assert "pic.png" in source
    assert "bad." not in source
    typst.compile(book, root=tmp_path, font_paths=fonts)


def test_drops_broken_svg_images(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<image xlink:href="../images/bad.png"/></svg>'
        },
        files={"images/bad.png": b""},
    )
    repack.repack(epub, tmp_path / "fixed.epub")
    with zipfile.ZipFile(tmp_path / "fixed.epub") as z:
        assert b"<image" not in z.read("OEBPS/text/ch1.xhtml")


def test_keeps_title_refined_as_main(make_epub, tmp_path):
    epub = make_epub(
        {"ch1.xhtml": "<p>One</p>"},
        metadata='<dc:title id="t1">Series</dc:title><dc:title id="t2">Main</dc:title>'
        '<meta refines="#t1" property="title-type">collection</meta>'
        '<meta refines="#t2" property="title-type">main</meta>',
    )
    assert "title: [Main]," in typeset(epub, tmp_path).read_text()


def test_keeps_first_of_unrefined_titles(make_epub, tmp_path):
    epub = make_epub(
        {"ch1.xhtml": "<p>One</p>"},
        metadata="<dc:title>First</dc:title><dc:title>Second</dc:title>",
    )
    assert "title: [First]," in typeset(epub, tmp_path).read_text()


def test_drops_time_from_date(make_epub, tmp_path):
    epub = make_epub(
        {"ch1.xhtml": "<p>One</p>"},
        metadata="<dc:title>Test</dc:title><dc:date>2020-01-02T03:04:05Z</dc:date>",
    )
    assert "date: [2020-01-02]," in typeset(epub, tmp_path).read_text()


def test_keeps_title_page(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<section epub:type="frontmatter titlepage">'
            "<p>Title page</p></section>"
        }
    )
    assert "Title page" in typeset(epub, tmp_path).read_text()


def test_keeps_own_contents(make_epub, tmp_path):
    epub = make_epub(
        {"ch1.xhtml": '<section epub:type="toc"><p>Contents page</p></section>'},
        nav_in_spine=True,
    )
    source = typeset(epub, tmp_path).read_text()
    assert "Contents page" in source
    assert "[ch1.xhtml]" in source


def test_drops_hidden_nav(make_epub, tmp_path):
    epub = make_epub(
        {"ch1.xhtml": "<p>One</p>"},
        nav='<nav epub:type="landmarks" hidden=""><ol>'
        '<li><a href="ch1.xhtml">Begin reading</a></li></ol></nav>',
        nav_in_spine=True,
    )
    assert "Begin reading" not in typeset(epub, tmp_path).read_text()


@pytest.mark.parametrize("tag", ["article", "nav", "footer", "details"])
def test_keeps_ids_of_containers(make_epub, tmp_path, fonts, tag):
    epub = make_epub(
        {
            "ch1.xhtml": f'<{tag} id="b"><p>Inside</p></{tag}>',
            "ch2.xhtml": '<p><a href="ch1.xhtml#b">Back</a></p>',
        }
    )
    book = typeset(epub, tmp_path)
    assert "#link(<ch1.xhtml_b>)[Back]" in book.read_text()
    typst.compile(book, root=tmp_path, font_paths=fonts)


def test_joins_hgroup_into_one_heading(make_epub, tmp_path):
    epub = make_epub({"ch1.xhtml": "<hgroup><h2>Chapter 1</h2><p>Start</p></hgroup>"})
    assert "== Chapter 1: Start\n" in typeset(epub, tmp_path).read_text()


def test_keeps_notes_referenced_from_other_files(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<p>Text<a href="notes.xhtml#n1" epub:type="noteref">1</a>'
            '<a href="notes.xhtml#n2" epub:type="noteref">2</a></p>',
            "notes.xhtml": '<section epub:type="endnotes" role="doc-endnotes"><ol>'
            '<li id="n1" epub:type="endnote"><p>End text.</p></li></ol></section>'
            '<aside id="n2" epub:type="rearnote"><p>Rear text.</p></aside>',
        }
    )
    source = typeset(epub, tmp_path).read_text()
    assert "End text." in source
    assert "Rear text." in source


def test_keeps_footnotes_referenced_from_same_file(make_epub, tmp_path):
    epub = make_epub(
        {
            "ch1.xhtml": '<p>Text<a href="#f1" epub:type="noteref">1</a></p>'
            '<aside id="f1" epub:type="footnote"><p>Foot text.</p></aside>'
        }
    )
    assert "#footnote[Foot text." in typeset(epub, tmp_path).read_text()
