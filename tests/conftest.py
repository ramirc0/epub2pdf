"""Fixtures that build minimal EPUBs."""

import base64
import urllib.parse
import zipfile

import pytest
import typst

# A 1x1 PNG, stored in every book as OEBPS/images/pic.png.
PIC = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

CONTAINER = """\
<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

OPF = """\
<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">urn:uuid:0b6c3a1e-5d2f-4c1a-9f5e-3f1d2c4b5a69</dc:identifier>
    <dc:language>en</dc:language>
    {metadata}
  </metadata>
  <manifest>
    <item id="nav" href="text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="pic" href="images/pic.png" media-type="image/png"/>
    {manifest}
  </manifest>
  <spine>
    {spine}
  </spine>
  {guide}
</package>
"""

XHTML = """\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en">
<head><title>{title}</title></head>
<body>
{body}
</body>
</html>
"""


@pytest.fixture
def make_epub(tmp_path):
    """Return a function that writes a minimal EPUB 3 to tmp_path/book.epub.

    The function takes a dict of chapter file names to body markup, stored in
    spine order under OEBPS/text, next to a nav document listing them. Keyword
    arguments add raw XML to the OPF's ``metadata`` (replacing the default
    title), ``manifest``, ``spine`` and ``guide``, add ``nav`` markup to the nav
    document, put the nav document first in the spine (``nav_in_spine``), and
    add ``files`` by path under OEBPS. Every book stores a 1x1 PNG at
    OEBPS/images/pic.png, with manifest id ``pic``.
    """

    def make(
        chapters,
        *,
        metadata="<dc:title>Test</dc:title>",
        manifest="",
        spine="",
        guide="",
        nav="",
        nav_in_spine=False,
        files=None,
    ):
        hrefs = [urllib.parse.quote(name) for name in chapters]
        toc = "".join(
            f'<li><a href="{href}">{name}</a></li>'
            for href, name in zip(hrefs, chapters)
        )
        items = "".join(
            f'<item id="c{i}" href="text/{href}" media-type="application/xhtml+xml"/>'
            for i, href in enumerate(hrefs)
        )
        itemrefs = "".join(f'<itemref idref="c{i}"/>' for i in range(len(chapters)))
        if nav_in_spine:
            itemrefs = '<itemref idref="nav"/>' + itemrefs
        opf = OPF.format(
            metadata=metadata,
            manifest=items + manifest,
            spine=itemrefs + spine,
            guide=guide,
        )
        toc_nav = f'<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>{toc}</ol></nav>'
        path = tmp_path / "book.epub"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("META-INF/container.xml", CONTAINER)
            z.writestr("OEBPS/content.opf", opf)
            z.writestr(
                "OEBPS/text/nav.xhtml",
                XHTML.format(title="Contents", body=toc_nav + nav),
            )
            z.writestr("OEBPS/images/pic.png", PIC)
            for name, body in chapters.items():
                z.writestr(f"OEBPS/text/{name}", XHTML.format(title=name, body=body))
            for name, data in (files or {}).items():
                z.writestr(f"OEBPS/{name}", data)
        return path

    return make


@pytest.fixture(scope="session")
def fonts():
    """Return typst's embedded fonts; a system font scan takes 0.6 s per compile."""
    return typst.Fonts(include_system_fonts=False)
