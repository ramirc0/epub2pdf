"""Repair the pandoc AST of an EPUB for the typst writer.

EPUB chapters link to each other by filename, and their fragments often name
an anchor the target never defines. Typst treats a dead link as an error, so
point each link at an id that exists, or unwrap it.
"""

import re

# The kind of each pandoc element, for filters that handle a whole kind.
KIND = dict.fromkeys(
    (
        "Str", "Emph", "Underline", "Strong", "Strikeout", "Superscript",
        "Subscript", "SmallCaps", "Quoted", "Cite", "Code", "Space", "SoftBreak",
        "LineBreak", "Math", "RawInline", "Link", "Image", "Note", "Span",
    ),
    "Inline",
) | dict.fromkeys(
    (
        "Plain", "Para", "LineBlock", "CodeBlock", "RawBlock", "BlockQuote",
        "OrderedList", "BulletList", "DefinitionList", "Header",
        "HorizontalRule", "Table", "Figure", "Div",
    ),
    "Block",
)  # fmt: skip
# Where each element with attributes keeps them in its content.
ATTR = {
    "Code": 0, "Link": 0, "Image": 0, "Span": 0, "CodeBlock": 0, "Header": 1,
    "Table": 0, "Figure": 0, "Div": 0,
}  # fmt: skip


def fix(doc: dict) -> dict:
    """Repair the links in a pandoc AST of an EPUB.

    Parameters
    ----------
    doc : dict
        Pandoc JSON AST, read from an EPUB. It is modified in place.

    Returns
    -------
    dict
        The repaired AST.
    """
    ids = _ids(doc)
    _walk(doc, {"Link": lambda link: _repair(link, ids)})
    return doc


def _walk(node, filter):
    """Apply a filter bottom-up to the elements under node, as pandoc's Lua does.

    The filter maps an element tag, or "Inline" or "Block" for any other inline
    or block element, to a function. The function returns None to keep the
    element, or a list of elements to splice in its place, unwalked.
    """
    if isinstance(node, dict):
        for value in node.values():
            _walk(value, filter)
    elif isinstance(node, list):
        out = []
        for item in node:
            _walk(item, filter)
            tag = item.get("t") if isinstance(item, dict) else None
            function = filter.get(tag) or filter.get(KIND.get(tag))
            result = function(item) if function else None
            out.extend([item] if result is None else result)
        node[:] = out


def _attr(el):
    """Return the attributes of el, or None if it has none."""
    index = ATTR.get(el["t"])
    return None if index is None else el["c"][index]


def _ids(doc):
    """Return the ids of the elements in doc."""
    ids = set()

    def collect(el):
        attr = _attr(el)
        if attr and attr[0]:
            ids.add(attr[0])

    _walk(doc, {"Inline": collect, "Block": collect})
    return ids


def _chapter_of(target, ids):
    """Return the chapter id at the start of target, or None.

    Pandoc names each chapter's id after its file. Files may be .htm, .html
    or .xhtml, and names may contain ".htm".
    """
    for match in re.finditer(r"\.x?html?", target):
        if target[: match.end()] in ids:
            return target[: match.end()]
    return None


def _repair(link, ids):
    """Point link at an id that exists, or return its content to unwrap it."""
    target = link["c"][2][0]
    if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target):
        return None
    path, _, frag = target.partition("#")
    if not path:
        found = frag if frag in ids else _chapter_of(frag, ids)
    else:
        found = _chapter_of(path.rpartition("/")[2], ids)
        if found and frag and f"{found}_{frag}" in ids:
            found = f"{found}_{frag}"
    if found in ids:
        link["c"][2][0] = "#" + found
        return None
    return link["c"][1]
