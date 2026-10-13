#!/usr/bin/env python3
"""Generic PDF -> Markdown body converter for Commonwealth-Caribbean style
revised laws (LawCodex).

Uses poppler's pdftotext (no OCR). The text layer is preserved faithfully;
only presentation is touched:
  * running page headers/footers (lines repeated on many pages) and bare
    page numbers are dropped;
  * PART / SCHEDULE / CHAPTER lines become level-2 headings;
  * numbered section openings ("12. ...") become level-3 headings when the
    numbering is plausible (monotonic), otherwise they are left as text;
  * characters that Markdown would interpret at line start are escaped.
"""
import collections
import re
import subprocess

PART_RE = re.compile(r"^(PART|Part|CHAPTER|Chapter)\s+([IVXLC]+|\d+[A-Z]?|[A-Z])\b(.{0,120})$")
SCHED_RE = re.compile(r"^((FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH)\s+)?SCHEDULE\b.{0,80}$")
SEC_RE = re.compile(r"^(\d{1,3}[A-Z]{0,2})\s?\.\s*(\S.*)?$")


def pdf_text(path, layout=False):
    args = ["pdftotext", "-enc", "UTF-8"]
    if layout:
        args.append("-layout")
    r = subprocess.run(args + [path, "-"], capture_output=True)
    return r.stdout.decode("utf-8", "replace")


def pages_of(path, layout=False):
    return pdf_text(path, layout).split("\f")


def is_scan(pages):
    """True when the PDF has (almost) no text layer."""
    txt = "".join(pages)
    n = max(1, len([p for p in pages if p.strip()]) or len(pages))
    return len(re.sub(r"\s", "", txt)) < 40 * max(1, len(pages)) * 0.5 or len(re.sub(r"\s", "", txt)) < 200


def _norm(l):
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", l.strip())).lower()


def sec_num_value(s):
    m = re.match(r"(\d+)([A-Z]*)", s)
    return int(m.group(1)) if m else -1


def escape_md(line):
    s = line
    if re.match(r"^\s*[#>*+\-=|`~]", s):
        s = "\\" + s.lstrip()
    s = re.sub(r"^(\d+)([.)])(\s|$)", r"\1\\\2\3", s)
    s = s.replace("<", "&lt;") if re.search(r"<[A-Za-z/!]", s) else s
    return s


def convert(pages, drop_lines=()):
    """Return Markdown body from a list of page texts."""
    # 1. detect running headers/footers
    cnt = collections.Counter()
    for p in pages:
        seen = set()
        lines = [l for l in p.split("\n") if l.strip()]
        for l in lines[:6] + lines[-4:]:
            k = _norm(l)
            if len(k) <= 90 and k not in seen:
                seen.add(k)
                cnt[k] += 1
    npages = len([p for p in pages if p.strip()])
    thr = max(3, int(npages * 0.3))
    running = {k for k, c in cnt.items() if c >= thr} if npages >= 4 else set()
    out = []
    last_sec = 0
    in_arrangement = False
    arr_last = 0
    for p in pages:
        lines = p.split("\n")
        nonblank = [i for i, l in enumerate(lines) if l.strip()]
        edge = set(nonblank[:6] + nonblank[-4:])
        for i, raw in enumerate(lines):
            l = raw.rstrip()
            st = l.strip()
            if not st:
                if out and out[-1] != "":
                    out.append("")
                continue
            if i in edge and _norm(st) in running:
                continue
            if re.fullmatch(r"[-–— ]*\d{1,4}[-–— ]*|[ivxlc]{1,6}", st) and i in edge:
                continue
            if any(re.search(d, st) for d in drop_lines):
                continue
            st = re.sub(r"\s+", " ", st) if not raw.startswith("   ") else st
            low = st.lower()
            if re.match(r"^arrangement of (sections|clauses|regulations|rules|articles|paragraphs|provisions|orders)", low):
                in_arrangement = True
                arr_last = 0
                out += ["", "## " + st, ""]
                continue
            m = PART_RE.match(st)
            if m and len(st) < 130:
                out += ["", "## " + st, ""]
                continue
            if SCHED_RE.match(st) and st.upper() == st:
                in_arrangement = False
                out += ["", "## " + st, ""]
                continue
            m = SEC_RE.match(st)
            if m and in_arrangement:
                v = sec_num_value(m.group(1))
                if arr_last >= 2 and v <= 1:
                    in_arrangement = False
                    out += ["", "---", ""]
                    last_sec = 0
                else:
                    arr_last = max(arr_last, v)
            if m and not in_arrangement:
                v = sec_num_value(m.group(1))
                if last_sec < v <= last_sec + 3 or (v == last_sec and m.group(1)[-1:].isalpha()):
                    last_sec = v
                    rest = m.group(2) or ""
                    out += ["", "### " + m.group(1) + ".", ""]
                    if rest:
                        out.append(escape_md(rest))
                    continue
            out.append(escape_md(st))
        if out and out[-1] != "":
            out.append("")
    # second pass: arrangement ends at first body text after it; reset handled loosely
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text
