#!/usr/bin/env python3
"""Fetch the Laws of Dominica from the Government of Dominica web portal
(https://dominica.gov.dm/laws-of-dominica).

The portal exposes a title search (GET ?page=N&term=X&sort=title, 30 results
per page). We index the searches "chapter" (Revised Laws of Dominica 1990
chapters) and "act" (annual Acts 1991-), keep chapters and Acts (Statutory
Rules and Orders are skipped), and download the PDFs to _raw/dm/pdf/.
robots.txt sets Crawl-delay: 30, which is obeyed for every request.
Usage: dm_fetch.py
"""
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

import requests

BASE = "https://dominica.gov.dm/laws-of-dominica"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
RAW = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_raw", "dm"))
DELAY = 30.0  # robots.txt Crawl-delay
s = requests.Session()
s.headers["User-Agent"] = UA
_last = [0.0]


def get(url):
    for i in range(5):
        wait = DELAY - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = s.get(url, timeout=300)
            if r.status_code in (200, 404, 403, 410):
                return r
        except requests.RequestException as e:
            print("  retry", url, e, file=sys.stderr, flush=True)
        time.sleep(10 * (i + 1))
    raise RuntimeError("failed " + url)


class _Failed:
    status_code = 0
    content = b""
    headers = {}


FAILED = _Failed()


def pdf_ok(path):
    if not os.path.exists(path) or os.path.getsize(path) < 100:
        return False
    with open(path, "rb") as f:
        head = f.read(5)
        f.seek(max(0, os.path.getsize(path) - 2048))
        tail = f.read()
    if head != b"%PDF-" or b"%%EOF" not in tail:
        return False
    return subprocess.run(["pdfinfo", path], capture_output=True).returncode == 0


ITEM = re.compile(r"<li><a href='([^']+\.pdf)' target='_blank'>([^<]+)</a></li>", re.I)


def search(term):
    items, page, total = [], 1, None
    while True:
        url = "%s?page=%d&term=%s&sort=title" % (BASE, page, urllib.parse.quote(term))
        t = get(url).text
        m = re.search(r"found (\d+) results", t)
        total = int(m.group(1)) if m else 0
        got = [(u, html.unescape(x).strip()) for u, x in ITEM.findall(t)]
        items += got
        print("search", term, page, len(items), "/", total, flush=True)
        if not got or len(items) >= total:
            break
        page += 1
    return items


def classify(u, t):
    if "/chapters/" in u:
        return "chapter"
    if re.search(r"\bS\.?R\.?O\.?\b", t) or re.search(r"/sro", u, re.I):
        return "other"
    if re.search(r"/act[^/]*\.pdf$", u, re.I) or re.search(r"\b(?:Act\s+)?(?:No\.?\s*)?\d+\s+of\s+\d{4}", t, re.I):
        return "act"
    return "other"


def build_index():
    ip = os.path.join(RAW, "index.json")
    if os.path.exists(ip):
        return json.load(open(ip))
    seen, idx = set(), []
    for term in ("chapter", "act", "constitution"):
        for u, t in search(term):
            if u in seen:
                continue
            seen.add(u)
            kind = classify(u, t)
            idx.append({"url": u, "title": t, "kind": kind})
    json.dump(idx, open(ip, "w"), indent=1)
    return idx


def fname(url):
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    parts = path.split("/")
    return re.sub(r"[^A-Za-z0-9._-]", "_", "-".join(parts[-2:]))


def main():
    os.makedirs(os.path.join(RAW, "pdf"), exist_ok=True)
    idx = build_index()
    for r in idx:
        r["kind"] = classify(r["url"], r["title"])
    todo = [r for r in idx if r["kind"] in ("chapter", "act")]
    print(len(idx), "indexed,", len(todo), "chapters+acts", flush=True)
    bad = []
    for n, r in enumerate(todo):
        p = os.path.join(RAW, "pdf", fname(r["url"]))
        if pdf_ok(p):
            continue
        url = urllib.parse.quote(r["url"], safe=":/")
        try:
            resp = get(url)
        except RuntimeError as e:
            print('  giving up', e, flush=True)
            resp = FAILED
        ok = False
        if resp.status_code == 200 and resp.content[:5] == b"%PDF-":
            cl = resp.headers.get("content-length")
            if not cl or resp.headers.get("content-encoding") or int(cl) == len(resp.content):
                open(p, "wb").write(resp.content)
                ok = pdf_ok(p)
        if not ok:
            bad.append({"url": r["url"], "status": resp.status_code})
        print(n, fname(r["url"]), ok, resp.status_code, flush=True)
    json.dump(bad, open(os.path.join(RAW, "failed.json"), "w"), indent=1)
    print("failed:", len(bad))


if __name__ == "__main__":
    main()
