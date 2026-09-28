# epub2pdf

Convert an EPUB to a PDF with pandoc and typst, themed with
[rose-pine](https://typst.app/universe/package/rose-pine).

## Requirements

- Python 3.12 or newer.
- [pandoc](https://pandoc.org) on the `PATH`.

On the first run, typst downloads the `@preview/rose-pine` package into
`~/.cache/typst`.

## Install

```sh
uv tool install git+https://github.com/ramirc0/epub2pdf
```

## Usage

```sh
epub2pdf BOOK.epub            # writes BOOK.pdf
epub2pdf BOOK.epub out.pdf
epub2pdf -v rose-pine-dawn -m "Libertinus Serif" BOOK.epub
```

`-v` picks the theme variant: `rose-pine` (default), `rose-pine-moon` or
`rose-pine-dawn`. `-m` sets the text font.

## Demo

```sh
epub2pdf demo/the-time-machine.epub
```

This writes `demo/the-time-machine.pdf`, which is also in the repository.
`demo/the-time-machine.epub` is H. G. Wells's *The Time Machine* from
[Standard Ebooks](https://standardebooks.org/ebooks/h-g-wells/the-time-machine).
The text is in the US public domain, and Standard Ebooks dedicates its ebook to
the public domain under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
