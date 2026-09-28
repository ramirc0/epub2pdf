"""Compare the words of an EPUB's spine with the text of its PDF.

Prints one tab-separated row: stem, then the counts of distinct words, glued
words, unknown words, missing words and missing CJK characters. Known noise:
hyphenated compounds split at line ends, math symbols, URLs, hidden text.
"""

import argparse
import collections
import html.parser
import posixpath
import re
import subprocess
import urllib.parse
import zipfile
from pathlib import Path

BLOCK = {
    "p", "div", "br", "hr", "li", "tr", "td", "th", "dt", "dd", "blockquote",
    "section", "article", "aside", "header", "footer", "nav", "figure",
    "figcaption", "pre", "table", "h1", "h2", "h3", "h4", "h5", "h6", "hgroup",
    "body", "ol", "ul", "img", "svg",
}  # fmt: skip
SKIP = {"head", "script", "style", "rt", "rp"}
WORD = re.compile(r"[^\W\d_]+")
# A hyphen or dash, as between the halves of a compound split at a line end.
DASH = r"[-\u2010\u2011\u2013\u2014]\s*"
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")


class _Text(html.parser.HTMLParser):
    """Collect text outside SKIP elements, with newlines around blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in SKIP
        if tag in BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        self.skip -= tag in SKIP
        if tag in BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def epub_text(path):
    """Return the text of an EPUB's spine documents.

    Parameters
    ----------
    path : Path
        EPUB file.

    Returns
    -------
    str
        Text of each spine document, in reading order.
    """
    with zipfile.ZipFile(path) as z:
        container = z.read("META-INF/container.xml").decode()
        opf_name = re.search(r'full-path="([^"]+)"', container).group(1)
        opf = z.read(opf_name).decode("utf8", "replace")
        base = posixpath.dirname(opf_name)
        items = {}
        for tag in re.findall(r"<item\b[^>]*>", opf):
            ident = re.search(r'\bid="([^"]*)"', tag)
            href = re.search(r'\bhref="([^"]*)"', tag)
            if ident and href:
                name = urllib.parse.unquote(href.group(1).strip())
                items[ident.group(1)] = posixpath.normpath(posixpath.join(base, name))
        parts = []
        for idref in re.findall(r'<itemref\b[^>]*\bidref="([^"]*)"', opf):
            name = items.get(idref)
            if name in z.namelist():
                parser = _Text()
                parser.feed(z.read(name).decode("utf8", "replace"))
                parts.append("".join(parser.out))
    return "\n".join(parts)


def pdf_text(path):
    """Return the text of a PDF as pdftotext extracts it.

    Parameters
    ----------
    path : Path
        PDF file.

    Returns
    -------
    str
        Text with soft hyphens, and the line breaks after them, removed.
    """
    out = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", path, "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return re.sub(r"\xad\s*", "", out)


def normalize(text):
    """Drop invisible characters and straighten single quotes.

    Parameters
    ----------
    text : str
        Text to normalize.

    Returns
    -------
    str
        Text without soft hyphens or word joiners, with ' for curly quotes.
    """
    text = text.replace("\xad", "").replace("\u2060", "")
    return re.sub(r"[\u2018\u2019]", "'", text)


def context(text, word, width, bound=""):
    """Return the first occurrence of word in text, with its surroundings.

    Parameters
    ----------
    text : str
        Text to search.
    word : str
        Word to find.
    width : int
        Characters to keep on each side.
    bound : str, optional
        Regex to require on both sides of the word, such as ``\\b``.

    Returns
    -------
    str
        The match on one line, or an empty string.
    """
    side = f".{{0,{width}}}"
    match = re.search(side + bound + re.escape(word) + bound + side, text)
    return match.group(0).replace("\n", "\u23ce") if match else ""


def main():
    """Print the text check row for an EPUB and its PDF."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("epub", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show the most frequent glued and missing words",
    )
    args = parser.parse_args()

    src = normalize(epub_text(args.epub))
    out = normalize(pdf_text(args.pdf))
    vocab = collections.Counter(WORD.findall(src))
    seen = collections.Counter(WORD.findall(out))
    glued, unknown = collections.Counter(), collections.Counter()
    for word, n in seen.items():
        if word in vocab or CJK.search(word):
            continue
        splits = [
            i for i in range(1, len(word)) if word[:i] in vocab and word[i:] in vocab
        ]
        if not splits:
            unknown[word] += n
        elif not any(
            re.search(re.escape(word[:i]) + DASH + re.escape(word[i:]), src)
            for i in splits
        ):
            glued[word] += n
    missing = [word for word in vocab if word not in seen and not CJK.search(word)]
    cjk_missing = set(CJK.findall(src)) - set(CJK.findall(out))

    counts = (len(vocab), len(glued), len(unknown), len(missing), len(cjk_missing))
    print(args.epub.stem, *counts, sep="\t")
    if args.verbose:
        for word, _ in glued.most_common(8):
            print(f"  GLUED   {word!r:30} {context(out, word, 40)}")
        for word in sorted(missing, key=lambda w: -vocab[w])[:8]:
            print(
                f"  MISSING {word!r:14} x{vocab[word]}  src: {context(src, word, 50, r'\b')}"
            )
        if cjk_missing:
            print(f"  CJK MISSING {''.join(sorted(cjk_missing))[:60]}")


if __name__ == "__main__":
    main()
