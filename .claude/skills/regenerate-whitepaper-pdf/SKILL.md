---
name: regenerate-whitepaper-pdf
description: Regenerate the AFFI whitepaper's PDF and HTML renders from the current markdown source in docs/. Use whenever docs/AFFI_whitepaper_*.md changes and the PDF/HTML need to match, or whenever the user asks for a PDF of the whitepaper.
---

# Regenerate whitepaper PDF/HTML

The whitepaper's source of truth is `docs/AFFI_whitepaper_<date>.md`. The `.pdf`
and `.html` next to it are generated renders, not hand-edited — they go stale
the moment the `.md` changes unless this is re-run.

## Requirements (install once, no sudo needed)

```bash
brew install pandoc pango
pip3 install weasyprint
```

If `weasyprint` fails to import with a `libgobject`/`libpango` dlopen error,
`pango` isn't installed yet — `brew install pango` fixes it (pandoc alone is
not enough; weasyprint needs Pango/GLib to render text and layout).

Do NOT use `brew install basictex` for this — it requires an interactive sudo
password prompt and cannot run headlessly. `pandoc` + `weasyprint` is the
no-sudo path and is what this project uses.

## Steps

1. Find the current whitepaper markdown file: `ls docs/AFFI_whitepaper_*.md`
   (there should be exactly one — older dated versions get moved to
   `docs/stale_<date>/` when superseded, not left alongside the current one).
2. Convert markdown to styled standalone HTML with pandoc, using the print
   stylesheet below (a serif, letter-sized, table-friendly style — reuse it,
   don't reinvent one each time):

   ```bash
   pandoc docs/AFFI_whitepaper_<date>.md \
     -f gfm -t html5 --standalone \
     --metadata title="AFFI Whitepaper — <date>" \
     --css /tmp/whitepaper_print.css \
     -o docs/AFFI_whitepaper_<date>.html
   ```

   Print stylesheet (write to `/tmp/whitepaper_print.css` first if it doesn't
   exist):

   ```css
   @page { size: Letter; margin: 2.2cm 2cm; }
   body { font-family: Georgia, "Times New Roman", serif; font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; }
   h1 { font-size: 20pt; margin-bottom: 4pt; }
   h2 { font-size: 14pt; margin-top: 20pt; border-bottom: 1pt solid #999; padding-bottom: 3pt; }
   h3 { font-size: 11.5pt; margin-top: 14pt; }
   p { margin: 6pt 0; text-align: justify; }
   table { border-collapse: collapse; width: 100%; margin: 10pt 0; font-size: 9pt; }
   th, td { border: 0.5pt solid #999; padding: 4pt 6pt; text-align: left; }
   th { background: #eee; }
   blockquote { border-left: 3pt solid #888; margin: 8pt 0; padding: 4pt 10pt; background: #f5f5f5; font-style: italic; }
   code { font-family: "Courier New", monospace; font-size: 9pt; background: #eee; padding: 1pt 3pt; }
   hr { border: none; border-top: 1pt solid #ccc; margin: 14pt 0; }
   a { color: #1a4a7a; }
   ```

3. Render the HTML to PDF with weasyprint:

   ```bash
   python3 -c "
   from weasyprint import HTML
   HTML('docs/AFFI_whitepaper_<date>.html').write_pdf('docs/AFFI_whitepaper_<date>.pdf')
   "
   ```

4. Sanity-check the output: confirm the PDF page count is plausible
   (`python3 -c "import pypdf; print(len(pypdf.PdfReader('docs/AFFI_whitepaper_<date>.pdf').pages))"`)
   and that the file size is in the same ballpark as the last render, not
   truncated.

5. If an older dated `.md`/`.html`/`.pdf` set still sits in `docs/` alongside
   the new one, move it into `docs/stale_<old-date>/` so nobody grabs the
   wrong file — this project's convention, not optional cleanup.
