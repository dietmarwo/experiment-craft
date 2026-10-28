# The mathematicians' guide: PDF and images

[`../mathematicians-guide.md`](../mathematicians-guide.md) is the guide;
[`mathematicians-guide.pdf`](mathematicians-guide.pdf) is a typeset copy built
from it. Edit the Markdown and rebuild the PDF in the same commit.

| Path | Content |
| --- | --- |
| `mathematicians-guide.pdf` | The PDF built from the guide |
| `images/` | The two screenshots of a real scalar audit, and the derivative-root campaign's figure |
| `focused_results.py` | Draws `images/focused-results.png` from the certified values that the guide reports; needs matplotlib |
| `pdf/defaults.yaml` | The pandoc options: input, output, contents, numbering, filter and header |
| `pdf/metadata.yaml` | Subtitle, date, paper, fonts and link colors |
| `pdf/header.tex` | Running header and footer, landscape support, the contents page |
| `pdf/guide.lua` | Drops the guide's note about this PDF, points relative links at the files on GitHub, keeps code blocks on one page and puts wide screenshots on landscape pages |

Build from the repository root:

```bash
pandoc --defaults docs/mathematicians/pdf/defaults.yaml
```

The build needs pandoc 3 and XeLaTeX with the Latin Modern OpenType fonts and
the `unicode-math`, `fancyhdr`, `pdflscape`, `etoolbox` and `xurl` packages.
The committed PDF was built with pandoc 3.1.3 and XeTeX from TeX Live 2023
(Debian). The build runs no shell escape and needs no network access. In the
PDF, links to other files of this repository point at `main` on GitHub.

`focused_results.py` draws the campaign's figure from the certified values in
the guide; rerun it with `python3 docs/mathematicians/focused_results.py` when
they change. The screenshots were taken from the dashboard reading the audit
of a real scalar campaign of the [certificate example](../../examples/campaigns/certificates/run.py),
with the address bar and its access token left out. The wide one is shown on a
landscape page because its file name ends in `-wide.png`.
