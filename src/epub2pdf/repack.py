"""Repack an EPUB around defects that break pandoc."""

import re
import zipfile
from pathlib import Path

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
        zout.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        for entry in zin.infolist():
            if entry.filename == "mimetype":
                continue
            data = zin.read(entry)
            if entry.filename.endswith(".opf"):
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
