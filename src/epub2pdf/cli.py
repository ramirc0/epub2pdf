"""Convert an EPUB to a rose-pine themed PDF with pandoc and typst."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import typst

from epub2pdf import links

VARIANTS = ("rose-pine", "rose-pine-moon", "rose-pine-dawn")
MAINFONT = "Libertinus Serif"
HEADER = """\
#import "@preview/rose-pine:0.2.1": apply
#show: apply(variant: "{variant}")
"""


def typeset(
    epub: Path, workdir: Path, variant: str = VARIANTS[0], mainfont: str = MAINFONT
) -> Path:
    """Write the typst source of an EPUB, and its media, into a directory.

    Parameters
    ----------
    epub : Path
        EPUB to read.
    workdir : Path
        Directory to write ``book.typ`` and the ``media`` it uses into.
    variant : str, optional
        Theme variant, one of `VARIANTS`.
    mainfont : str, optional
        Font family of the text.

    Returns
    -------
    Path
        The typst source.

    Raises
    ------
    subprocess.CalledProcessError
        If pandoc fails.
    """
    doc = _pandoc(
        workdir, "-f", "epub", "-t", "json", "--extract-media=media", epub.resolve()
    )
    _pandoc(
        workdir,
        "-f", "json",
        "-t", "typst",
        "-s",
        "-V", "header-includes=" + HEADER.format(variant=variant),
        "-V", f"mainfont={mainfont}",
        "-o", "book.typ",
        stdin=json.dumps(links.fix(json.loads(doc))),
    )  # fmt: skip
    return workdir / "book.typ"


def _pandoc(workdir, *args, stdin=None):
    """Run pandoc in workdir and return its output."""
    return subprocess.run(
        ["pandoc", *args],
        cwd=workdir,
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def convert(
    epub: Path, pdf: Path, variant: str = VARIANTS[0], mainfont: str = MAINFONT
) -> list[typst.TypstWarning]:
    """Convert an EPUB to a PDF.

    Parameters
    ----------
    epub : Path
        EPUB to read.
    pdf : Path
        PDF to write.
    variant : str, optional
        Theme variant, one of `VARIANTS`.
    mainfont : str, optional
        Font family of the text.

    Returns
    -------
    list of typst.TypstWarning
        Warnings from typst.

    Raises
    ------
    subprocess.CalledProcessError
        If pandoc fails.
    typst.TypstError
        If typst fails.
    """
    with tempfile.TemporaryDirectory() as tmp:
        book = typeset(epub, Path(tmp), variant, mainfont)
        _, warnings = typst.compile_with_warnings(book, output=pdf, root=tmp)
    return warnings


def main(argv: list[str] | None = None) -> None:
    """Run the command line.

    Parameters
    ----------
    argv : list of str, optional
        Arguments after the program name. Defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(
        prog="epub2pdf",
        description=__doc__,
        epilog="Requires pandoc on the PATH. On first run, typst downloads the "
        "rose-pine package into its cache (~/.cache/typst).",
    )
    parser.add_argument(
        "-v",
        "--variant",
        choices=VARIANTS,
        default=VARIANTS[0],
        help="theme variant (default: %(default)s)",
    )
    parser.add_argument(
        "-m",
        "--mainfont",
        default=MAINFONT,
        help="main text font (default: %(default)s, embedded in typst)",
    )
    parser.add_argument("input", type=Path, help="EPUB to convert")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="PDF to write (default: the input with a .pdf suffix)",
    )
    args = parser.parse_args(argv)
    output = (args.output or args.input.with_suffix(".pdf")).resolve()

    if not args.input.is_file():
        sys.exit(f"epub2pdf: file not found: {args.input}")
    if not output.parent.is_dir():
        sys.exit(f"epub2pdf: directory not found: {output.parent}")
    if not shutil.which("pandoc"):
        sys.exit("epub2pdf: required command not found: pandoc")

    try:
        warnings = convert(args.input, output, args.variant, args.mainfont)
    except subprocess.CalledProcessError as err:
        sys.exit(err.stderr.rstrip())
    except typst.TypstError as err:
        sys.exit(err.diagnostic.rstrip())
    for warning in warnings:
        if warning.message.startswith("unknown font family"):
            print(f"warning: {warning.message}", file=sys.stderr)
    print(f"Wrote {output}")
