"""Write the typst source epub2pdf generates for an EPUB.

Usage: python scripts/typeset.py BOOK.epub OUT.typ
"""

import shutil
import sys
import tempfile
from pathlib import Path

from epub2pdf.cli import typeset

with tempfile.TemporaryDirectory() as tmp:
    shutil.copy(typeset(Path(sys.argv[1]), Path(tmp)), sys.argv[2])
