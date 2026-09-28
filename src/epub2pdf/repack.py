"""Repack an EPUB around defects that break pandoc."""

import posixpath
import re
import urllib.parse
import zipfile
from pathlib import Path

# Some src and href attributes pad the path with whitespace.
PADDED = re.compile(rb'\b(src|href)="\s*([^"]*?)\s*"')
# Some manifests list files missing from the archive, which aborts the reader.
ITEM = re.compile(rb"<item\b[^>]*/>")
# Some images are empty or not images at all, which aborts typst.
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"<?xml", b"<svg")
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
        broken = [
            posixpath.basename(n).encode()
            for n in names
            if n.lower().endswith(IMAGE_EXT)
            and not zin.read(n).lstrip().startswith(IMAGE_MAGIC)
        ]
        broken_img = re.compile(
            rb'<(?:img|image)\b[^>]*["/](?:'
            + b"|".join(map(re.escape, broken))
            + rb')"[^>]*>'
        )
        zout.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        for entry in zin.infolist():
            if entry.filename == "mimetype":
                continue
            data = zin.read(entry)
            if entry.filename.endswith((".html", ".xhtml", ".opf")):
                data = PADDED.sub(rb'\1="\2"', data)
            if entry.filename.endswith((".html", ".xhtml")):
                if broken:
                    data = broken_img.sub(b"", data)
            elif entry.filename.endswith(".opf"):
                data = _prune(data, posixpath.dirname(entry.filename), names)
                needs_toc |= not _has_toc(data)
            zout.writestr(entry, data)
    return needs_toc


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
