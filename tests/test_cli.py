"""Tests for the command line and the typst header."""

import re
import subprocess

import pytest
import typst

from epub2pdf import cli

ROWS = "".join(f"<tr><td>row {i}</td></tr>" for i in range(1, 121))


def pdf_text(pdf, *options):
    """Return the text of a PDF, as pdftotext extracts it with options."""
    return subprocess.run(
        ["pdftotext", *options, pdf, "-"], capture_output=True, text=True, check=True
    ).stdout


def compile_pdf(epub, tmp_path, fonts):
    """Typeset and compile an EPUB, and return the PDF."""
    pdf = tmp_path / "book.pdf"
    typst.compile(
        cli.typeset(epub, tmp_path), output=pdf, root=tmp_path, font_paths=fonts
    )
    return pdf


def test_writes_pdf_next_to_input(make_epub, capsys):
    epub = make_epub({"ch1.xhtml": "<p>Hello world</p>"})
    cli.main([str(epub)])
    pdf = epub.with_suffix(".pdf")
    assert capsys.readouterr().out == f"Wrote {pdf}\n"
    assert "Hello world" in pdf_text(pdf)


def test_writes_named_output(make_epub, tmp_path):
    epub = make_epub({"ch1.xhtml": "<p>Hello world</p>"})
    cli.main([str(epub), str(tmp_path / "out.pdf")])
    assert "Hello world" in pdf_text(tmp_path / "out.pdf")


def test_rejects_missing_input(tmp_path):
    with pytest.raises(SystemExit, match="^epub2pdf: file not found: "):
        cli.main([str(tmp_path / "none.epub")])


def test_rejects_missing_output_directory(make_epub, tmp_path):
    epub = make_epub({"ch1.xhtml": "<p>Hello</p>"})
    with pytest.raises(SystemExit, match="^epub2pdf: directory not found: "):
        cli.main([str(epub), str(tmp_path / "none" / "out.pdf")])


def test_requires_pandoc(make_epub, monkeypatch):
    epub = make_epub({"ch1.xhtml": "<p>Hello</p>"})
    monkeypatch.setenv("PATH", "")
    with pytest.raises(
        SystemExit, match="^epub2pdf: required command not found: pandoc$"
    ):
        cli.main([str(epub)])


def test_rejects_unknown_variant(make_epub):
    epub = make_epub({"ch1.xhtml": "<p>Hello</p>"})
    with pytest.raises(SystemExit):
        cli.main(["-v", "rose-pine-noon", str(epub)])


def test_reports_unknown_font_only(make_epub, capsys):
    epub = make_epub({"ch1.xhtml": "<p>Hello</p>"})
    cli.main(["-m", "No Such Font", str(epub)])
    assert capsys.readouterr().err == "warning: unknown font family: no such font\n"


def test_exits_with_typst_diagnostic(make_epub, monkeypatch):
    epub = make_epub({"ch1.xhtml": "<p>Hello</p>"})

    def typeset(epub, workdir, variant, mainfont):
        (workdir / "book.typ").write_text("#nonexistent()")
        return workdir / "book.typ"

    monkeypatch.setattr(cli, "typeset", typeset)
    with pytest.raises(SystemExit, match="unknown variable: nonexistent"):
        cli.main([str(epub)])


def test_rejects_non_zip(tmp_path):
    epub = tmp_path / "book.epub"
    epub.write_text("<html></html>")
    with pytest.raises(SystemExit, match="^epub2pdf: not an EPUB: "):
        cli.main([str(epub)])


def test_breaks_tables_across_pages(make_epub, tmp_path, fonts):
    epub = make_epub({"ch1.xhtml": f"<p>Intro</p><table>{ROWS}</table>"})
    pdf = compile_pdf(epub, tmp_path, fonts)
    assert "row 1\n" in pdf_text(pdf, "-f", "1", "-l", "1")


def test_aligns_table_cells_to_start(make_epub, tmp_path, fonts):
    epub = make_epub(
        {
            "ch1.xhtml": "<table><tr><td>Short</td></tr>"
            "<tr><td>Much longer cell text</td></tr></table>"
        }
    )
    bbox = pdf_text(compile_pdf(epub, tmp_path, fonts), "-bbox")
    x_min = {w: x for x, w in re.findall(r'xMin="([\d.]+)"[^>]*>(Short|Much)<', bbox)}
    assert x_min["Short"] == x_min["Much"]


def test_sets_lines_two_alphabets_wide(make_epub, tmp_path, fonts):
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    prose = "the quick brown fox jumps over a lazy dog " * 30
    epub = make_epub({"ch1.xhtml": f"<p>{alphabet}</p><p>{prose}</p>"})
    bbox = pdf_text(compile_pdf(epub, tmp_path, fonts), "-bbox-layout")
    x_min, x_max = re.search(
        rf'<word xMin="([\d.]+)" [^>]*xMax="([\d.]+)"[^>]*>{alphabet}<', bbox
    ).groups()
    measure = 2 * (float(x_max) - float(x_min))
    lines = re.findall(r'<line xMin="([\d.]+)" [^>]*xMax="([\d.]+)"', bbox)
    widest = max(float(right) - float(left) for left, right in lines)
    assert widest == pytest.approx(measure, abs=1)


def test_keeps_captions_unnumbered(make_epub, tmp_path, fonts):
    epub = make_epub(
        {
            "ch1.xhtml": "<table><caption>Prices</caption><tr><td>1</td></tr></table>"
            '<figure><img src="../images/pic.png" alt=""/>'
            "<figcaption>Map</figcaption></figure>"
        }
    )
    text = pdf_text(compile_pdf(epub, tmp_path, fonts))
    assert "Prices" in text
    assert "Map" in text
    assert "Table 1" not in text
    assert "Figure 1" not in text


def test_breaks_long_figures_across_pages(make_epub, tmp_path, fonts):
    caption = "word " * 400 + "lastword"
    epub = make_epub(
        {
            "ch1.xhtml": '<figure><img src="../images/pic.png" alt="" height="400"/>'
            f"<figcaption>{caption}</figcaption></figure>"
        }
    )
    assert "lastword" in pdf_text(compile_pdf(epub, tmp_path, fonts))
