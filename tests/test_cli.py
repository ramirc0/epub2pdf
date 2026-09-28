"""Tests for the command line and the typst header."""

import subprocess

import pytest

from epub2pdf import cli


def pdf_text(pdf):
    """Return the text of a PDF."""
    return subprocess.run(
        ["pdftotext", pdf, "-"], capture_output=True, text=True, check=True
    ).stdout


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
