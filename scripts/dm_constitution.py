#!/usr/bin/env python3
"""Fetch the Constitution of the Commonwealth of Dominica.

The copy on dominica.gov.dm (laws/chapters/chap1-01-sch1.pdf) is a scan
without a text layer. WIPO Lex hosts the same official Revised Edition
print (Revised Laws of Dominica, L.R.O. 1/1991) with an OCR text layer:
https://www.wipo.int/wipolex/en/legislation/details/9009
This script downloads it (the PDF link is a signed, expiring URL found on the
details page) and writes constitution/constitution-of-the-commonwealth-of-dominica.md.
Usage: dm_constitution.py
"""
import datetime
import html
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dm_pdf2md  # noqa: E402
from dm_fetch import RAW, pdf_ok  # noqa: E402

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
PAGE = "https://www.wipo.int/wipolex/en/legislation/details/9009"
OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "constitution",
                                   "constitution-of-the-commonwealth-of-dominica.md"))


def main():
    p = os.path.join(RAW, "constitution-wipo.pdf")
    if not pdf_ok(p):
        s = requests.Session()
        s.headers["User-Agent"] = UA
        t = s.get(PAGE, timeout=120).text
        u = html.unescape(re.search(r'href="(https://wipolex-res\.wipo\.int/[^"]+\.pdf[^"]*)"', t).group(1))
        r = s.get(u, timeout=300)
        open(p, "wb").write(r.content)
        assert pdf_ok(p), "download failed"
    body = dm_pdf2md.convert(dm_pdf2md.pages_of(p))
    fm = ["---", 'title: "The Constitution of the Commonwealth of Dominica"',
          'identifier: "S.I. 1978 No. 1027 (U.K.), Schedule 1"', "type: constitution", "jurisdiction: dm",
          "language: en", "date: 1978-11-03", 'edition: "Revised Laws of Dominica 1990 (L.R.O. 1/1991)"',
          "status: in_force", 'source: "https://dominica.gov.dm/laws/chapters/chap1-01-sch1.pdf"',
          'text_from: "' + PAGE + '"',
          'note: "Text layer from the WIPO Lex copy of the official Revised Edition print (the dominica.gov.dm '
          'copy is an image-only scan). Amendments after 1984 (e.g. Act 4 of 2014) are not consolidated."',
          "retrieved: " + datetime.date.today().isoformat(), "---"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(fm) + "\n\n# The Constitution of the Commonwealth of Dominica\n\n" + body)
    print("ok", OUT)


if __name__ == "__main__":
    main()
