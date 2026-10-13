#!/usr/bin/env python3
"""Convert the PDFs fetched by dm_fetch.py into Markdown.

  constitution/   Commonwealth of Dominica Constitution Order (Chap. 1:01) and
                  the Constitution (Schedule 1)
  chapters/chap-NN-NN-<slug>.md   Revised Laws of Dominica 1990 chapters
  acts/<year>/act-NN-<slug>.md    annual Acts 1991-
Scanned PDFs (no text layer) are not OCR'd; they are listed in
_raw/dm/gaps.json.
Usage: dm_convert.py
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dm_pdf2md  # noqa: E402
from dm_fetch import RAW, classify, fname  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TODAY = datetime.date.today().isoformat()


def slug(s, n=80):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower().replace("&", " and ")).strip("-")
    return s[:n].rstrip("-")


def yq(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    idx = json.load(open(os.path.join(RAW, "index.json")))
    gaps, counts, used = [], {}, set()
    for it in idx:
        kind = classify(it["url"], it["title"])
        if kind not in ("chapter", "act"):
            continue
        title_full = re.sub(r"\s+", " ", it["title"]).strip()
        pdf = os.path.join(RAW, "pdf", fname(it["url"]))
        if not os.path.exists(pdf):
            gaps.append({"title": title_full, "url": it["url"], "kind": kind, "reason": "not downloaded"})
            continue
        pages = dm_pdf2md.pages_of(pdf)
        if dm_pdf2md.is_scan(pages):
            gaps.append({"title": title_full, "url": it["url"], "kind": kind, "reason": "scanned PDF without text layer"})
            continue
        body = dm_pdf2md.convert(pages)
        if kind == "chapter":
            m = re.search(r"^(.*?),?\s*Chap(?:ter)?\.?\s*(\d+)\s*[:.]\s*(\d+)(.*)$", title_full, re.I)
            if m:
                title, a, b, rest = m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4).strip()
                ident = "Chap. %d:%02d%s" % (a, b, (" " + rest) if rest else "")
                fnb = "chap-%02d-%02d%s-%s" % (a, b, ("-" + slug(rest, 20)) if rest else "", slug(title, 70))
            else:
                title, ident, fnb = title_full, "", slug(title_full)
            if a == 1 and b == 1:
                d, typ = "constitution", "constitution"
            else:
                d, typ = "chapters", "act"
            path = os.path.join(OUT, d, fnb + ".md")
            year = ""
        else:
            m = re.search(r"^(.*?),?\s*(?:Act\s+)?(?:No\.?\s*)?(\d+)\s+of\s+(\d{4})\b.*$", title_full, re.I)
            if m:
                title, no, year = m.group(1).strip().rstrip(","), int(m.group(2)), m.group(3)
                ident = "Act No. %d of %s" % (no, year)
                path = os.path.join(OUT, "acts", year, "act-%02d-%s.md" % (no, slug(title, 70)))
            else:
                ym = re.search(r"/(\d{4})/", it["url"])
                year = ym.group(1) if ym else "undated"
                title, ident = title_full, ""
                path = os.path.join(OUT, "acts", year, slug(title_full) + ".md")
            typ = "act"
            if "constitution" in title.lower():
                typ = "act"
        base, k = path, 2
        while path in used:
            path = base[:-3] + "-%d.md" % k
            k += 1
        used.add(path)
        fm = ["---", "title: " + yq(title)]
        if ident:
            fm.append("identifier: " + yq(ident))
        fm += ["type: " + typ, "jurisdiction: dm", "language: en"]
        if year:
            fm.append("year: " + yq(year))
        if kind == "chapter":
            fm.append('edition: "Revised Laws of Dominica 1990"')
        fm += ["status: in_force", "source: " + yq(it["url"]), "retrieved: " + TODAY, "---"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(fm) + "\n\n# " + title + "\n\n" + body)
        counts[typ if kind == "chapter" else "annual act"] = counts.get(typ if kind == "chapter" else "annual act", 0) + 1
    json.dump(gaps, open(os.path.join(RAW, "gaps.json"), "w"), indent=1)
    print(counts, "gaps:", len(gaps), {r: sum(1 for g in gaps if g["reason"] == r) for r in {g["reason"] for g in gaps}})


if __name__ == "__main__":
    main()
