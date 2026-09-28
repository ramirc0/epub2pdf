"""Tests for the EPUB repairs in epub2pdf.repack."""

import zipfile

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
