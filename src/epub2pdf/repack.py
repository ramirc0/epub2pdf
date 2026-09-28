"""Repack an EPUB around defects that break pandoc."""

import posixpath
import re
import urllib.parse
import zipfile
from pathlib import Path

# Pandoc's HTML reader discards <section epub:type="...titlepage...">, where
# many books keep illustrations. It also discards any epub:type="toc" element,
# a book's own contents page, yet shows the <nav hidden> lists that reading
# systems hide.
TITLEPAGE = re.compile(rb'(epub:type="[^"]*)titlepage')
EPUB_TYPE = re.compile(rb'epub:type="[^"]*"')
TOC_TYPE = re.compile(rb"(?<![\w-])toc(?![\w-])")
HIDDEN_NAV = re.compile(rb"<nav\b[^>]*\bhidden\b[^>]*>.*?</nav>", re.DOTALL)
# Some src and href attributes pad the path with whitespace.
PADDED = re.compile(rb'\b(src|href)="\s*([^"]*?)\s*"')
# Some manifests list files missing from the archive, which aborts the reader.
ITEM = re.compile(rb"<item\b[^>]*/>")
# Some images are empty or not images at all, which aborts typst, so their
# tags are dropped.
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"<?xml", b"<svg")
# Pandoc joins every dc:title without a separator and keeps full timestamps
# as dates.
DC_TITLE = re.compile(rb"<dc:title\b[^>]*>.*?</dc:title>\s*", re.DOTALL)
MAIN_TITLE = re.compile(
    rb'<meta\b(?=[^>]*\bproperty="title-type")(?=[^>]*\brefines="#([^"]+)")'
    rb"[^>]*>\s*main\s*<"
)
TIMESTAMP = re.compile(rb"(<dc:date\b[^>]*>\s*\d{4}-\d\d-\d\d)T[^<]*")
# The EPUB 3 nav document and the EPUB 2 guide's contents page.
NAV_ITEM = re.compile(rb'<item\b(?=[^>]*\bproperties="[^"]*\bnav\b)[^>]*\bid="([^"]+)"')
TOC_REF = re.compile(rb'<reference\b(?=[^>]*\btype="toc")[^>]*\bhref="([^"#]*)')


def repack(src: Path, dst: Path) -> bool:
    """Copy an EPUB, rewriting what pandoc and typst mishandle.

    Parameters
    ----------
    src : Path
        EPUB to read.
    dst : Path
        EPUB to write.

    Returns
    -------
    bool
        Whether the book's own table of contents is missing from its reading
        order, which is where pandoc looks for content.

    Raises
    ------
    zipfile.BadZipFile
        If src is not a zip archive.
    """
    needs_toc = False
    with (
        zipfile.ZipFile(src) as zin,
        zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout,
    ):
        names = set(zin.namelist())
        broken_img = _broken_images(zin)
        zout.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        for entry in zin.infolist():
            if entry.filename == "mimetype":
                continue
            data = zin.read(entry)
            if entry.filename.endswith((".html", ".xhtml", ".opf")):
                data = PADDED.sub(rb'\1="\2"', data)
            if entry.filename.endswith((".html", ".xhtml")):
                data = _fix_html(data, broken_img)
            elif entry.filename.endswith(".opf"):
                data = _prune(data, posixpath.dirname(entry.filename), names)
                data = TIMESTAMP.sub(rb"\1", _one_title(data))
                needs_toc |= not _has_toc(data)
            zout.writestr(entry, data)
    return needs_toc


def _broken_images(zin):
    """Return a regex for the tags of images in zin that are empty or not images."""
    broken = [
        posixpath.basename(n).encode()
        for n in zin.namelist()
        if n.lower().endswith(IMAGE_EXT)
        and not zin.read(n).lstrip().startswith(IMAGE_MAGIC)
    ]
    if not broken:
        return None
    names = b"|".join(map(re.escape, broken))
    return re.compile(rb'<(?:img|image)\b[^>]*["/](?:' + names + rb')"[^>]*>')


def _fix_html(data, broken_img):
    """Rewrite an XHTML document, dropping tags broken_img matches, if any."""
    data = TITLEPAGE.sub(rb"\1", data)
    if broken_img:
        data = broken_img.sub(b"", data)
    data = HIDDEN_NAV.sub(b"", data)
    return EPUB_TYPE.sub(lambda m: TOC_TYPE.sub(b"", m.group(0)), data)


def _has_toc(opf):
    """Return whether the EPUB 3 nav or EPUB 2 guide toc page is in the spine."""
    ids = NAV_ITEM.findall(opf)
    ref = TOC_REF.search(opf)
    if ref:
        href = re.escape(ref.group(1))
        ids += re.findall(
            rb'<item\b(?=[^>]*\bhref="' + href + rb'")[^>]*\bid="([^"]+)"', opf
        )
    return any(b'idref="%s"' % i in opf for i in ids)


def _prune(opf, base, names):
    """Drop manifest items whose file is not in names, and their itemrefs."""
    dropped = []

    def keep(match):
        href = re.search(rb'href="([^"]*)"', match.group(0))
        if href and _resolve(href.group(1), base) not in names:
            ident = re.search(rb'id="([^"]*)"', match.group(0))
            if ident:
                dropped.append(ident.group(1))
            return b""
        return match.group(0)

    opf = ITEM.sub(keep, opf)
    for ident in dropped:
        itemref = rb'<itemref\b[^>]*idref="' + re.escape(ident) + rb'"[^>]*/>'
        opf = re.sub(itemref, b"", opf)
    return opf


def _resolve(href, base):
    """Return the archive path of an href relative to base."""
    href = urllib.parse.unquote(href.decode("utf8", "replace")).split("#")[0]
    return posixpath.normpath(posixpath.join(base, href))


def _one_title(opf):
    """Keep the dc:title refined as main, else the first."""
    main = MAIN_TITLE.search(opf)
    want = b'id="%s"' % main.group(1) if main else b""
    kept = False

    def keep(match):
        nonlocal kept
        if kept or want not in match.group(0):
            return b""
        kept = True
        return match.group(0)

    return DC_TITLE.sub(keep, opf)
