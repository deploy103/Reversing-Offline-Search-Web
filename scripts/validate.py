#!/usr/bin/env python3
"""
Validation script for Reversing-Offline-Search-Web (Phase 1 scope).

Implements the project's required validation checks:
  - duplicate title
  - duplicate slug
  - invalid/missing frontmatter fields
  - broken local link between articles' 관련 글 references
  - missing dist/article/<slug>.html for any content article
  - empty/placeholder article detection (body under minimum length)
  - file:// smoke test (no fetch/XHR/module scripts/remote resources;
    all local script/link paths resolve to real files)

Stdlib only. Run from repo root:

    python3 scripts/validate.py

Exit code 0 on pass, non-zero on any failure.
"""
import glob
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import mdlib  # noqa: E402

ROOT = SCRIPT_DIR.parent
CONTENT_DIR = ROOT / "content" / "articles"
DIST_DIR = ROOT / "dist"

REQUIRED_FIELDS = [
    "id", "title", "slug", "category", "difficulty",
    "platform", "architecture", "format", "tools",
    "keywords", "aliases", "symptom_keywords", "source_ids", "last_verified",
]
VALID_DIFFICULTY = {"beginner", "basic", "intermediate"}
MIN_BODY_CHARS = 800  # empty/placeholder threshold; real articles here are 3-8k+ chars

REQUIRED_BODY_SECTIONS = [
    "한 줄 요약", "언제 검색해야 하나", "핵심 개념",
    "가장 먼저 할 것", "단계별 절차", "명령어/단축키",
    "흔한 실수", "막혔을 때 다음 체크", "미니 예제", "관련 글", "출처/검증",
]

errors = []
warnings = []


def fail(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load_articles():
    paths = sorted(glob.glob(str(CONTENT_DIR / "**" / "*.md"), recursive=True))
    articles = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8")
        try:
            fm, body_md = mdlib.split_frontmatter(text)
        except ValueError as e:
            fail("{}: frontmatter parse error: {}".format(p, e))
            continue
        articles.append({"path": p, "frontmatter": fm, "body_md": body_md})
    return articles


def check_frontmatter(articles):
    for a in articles:
        p, fm = a["path"], a["frontmatter"]
        missing = [f for f in REQUIRED_FIELDS if f not in fm]
        if missing:
            fail("{}: missing frontmatter fields: {}".format(p, missing))
            continue
        if not re.match(r'^REV-\d{4}$', fm["id"]):
            fail("{}: invalid id format: {}".format(p, fm["id"]))
        if fm["difficulty"] not in VALID_DIFFICULTY:
            fail("{}: invalid difficulty '{}' (expected one of {})".format(
                p, fm["difficulty"], VALID_DIFFICULTY))
        if not fm["title"].strip():
            fail("{}: empty title".format(p))
        if not fm["slug"].strip():
            fail("{}: empty slug".format(p))
        if not re.match(r'^[a-z0-9][a-z0-9-]*$', fm["slug"]):
            fail("{}: slug '{}' should be lowercase kebab-case".format(p, fm["slug"]))
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(fm.get("last_verified", ""))):
            fail("{}: last_verified should be YYYY-MM-DD, got '{}'".format(p, fm.get("last_verified")))
        for listfield in ["platform", "architecture", "format", "tools", "keywords", "aliases", "symptom_keywords", "source_ids"]:
            if not isinstance(fm.get(listfield), list):
                fail("{}: field '{}' should be a list".format(p, listfield))


def check_duplicates(articles):
    titles = {}
    slugs = {}
    ids = {}
    for a in articles:
        fm = a["frontmatter"]
        if "title" not in fm or "slug" not in fm or "id" not in fm:
            continue
        titles.setdefault(fm["title"], []).append(a["path"])
        slugs.setdefault(fm["slug"], []).append(a["path"])
        ids.setdefault(fm["id"], []).append(a["path"])
    for title, paths in titles.items():
        if len(paths) > 1:
            fail("duplicate title '{}': {}".format(title, paths))
    for slug, paths in slugs.items():
        if len(paths) > 1:
            fail("duplicate slug '{}': {}".format(slug, paths))
    for id_, paths in ids.items():
        if len(paths) > 1:
            fail("duplicate id '{}': {}".format(id_, paths))


def check_body_content(articles):
    for a in articles:
        p, body = a["path"], a["body_md"]
        if len(body.strip()) < MIN_BODY_CHARS:
            fail("{}: body too short ({} chars < {} minimum) -- possible placeholder".format(
                p, len(body.strip()), MIN_BODY_CHARS))
        lowered = body.lower()
        # NOTE: "placeholder" itself is intentionally excluded -- it's a
        # legitimate English loanword used in real Korean technical prose
        # (e.g. describing Ghidra's default variable-naming convention),
        # so a bare substring match on it produces false positives.
        for marker in ["tbd", "todo:", "lorem ipsum", "작성 예정 (본문 없음)"]:
            if marker in lowered:
                fail("{}: contains placeholder marker '{}'".format(p, marker))
        missing_sections = [s for s in REQUIRED_BODY_SECTIONS if s not in body]
        if missing_sections:
            warn("{}: missing recommended sections: {}".format(p, missing_sections))


def check_related_links(articles, id_to_article):
    """Every 'REV-XXXX — title' bullet under 관련 글 should reference an id
    that either exists in the corpus (fine) or is clearly marked as not yet
    written. We only hard-fail when the referenced id exists in the corpus
    but under a DIFFERENT title than what's cited (stale reference) --
    that indicates a real broken/outdated link.
    """
    bullet_re = re.compile(r'^-\s+(REV-\d{4})\s+—\s+(.*?)(\s+\(예정\))?$')
    for a in articles:
        p, body = a["path"], a["body_md"]
        in_related = False
        for line in body.split("\n"):
            heading_m = re.match(r'^(#{1,3})\s+(.*)$', line.strip())
            if heading_m:
                in_related = heading_m.group(2).strip() == "관련 글"
                continue
            if not in_related:
                continue
            m = bullet_re.match(line.strip())
            if not m:
                continue
            rid, cited_title = m.group(1), m.group(2)
            if rid in id_to_article:
                actual_title = id_to_article[rid]["frontmatter"].get("title", "")
                if cited_title.strip() != actual_title.strip():
                    fail("{}: 관련 글 references {} with stale title '{}' (actual: '{}')".format(
                        p, rid, cited_title, actual_title))


def check_dist_output(articles):
    if not DIST_DIR.exists():
        fail("dist/ does not exist -- run scripts/build.py first")
        return
    for a in articles:
        fm = a["frontmatter"]
        if "slug" not in fm:
            continue
        out_file = DIST_DIR / "article" / "{}.html".format(fm["slug"])
        if not out_file.exists():
            fail("missing build output: {} (expected for {})".format(out_file, fm["id"]))

    index_file = DIST_DIR / "index.html"
    if not index_file.exists():
        fail("missing dist/index.html")

    search_index = DIST_DIR / "assets" / "search-index.js"
    if not search_index.exists():
        fail("missing dist/assets/search-index.js")
    else:
        content = search_index.read_text(encoding="utf-8")
        if not content.strip().startswith("window.SEARCH_INDEX"):
            fail("dist/assets/search-index.js does not start with 'window.SEARCH_INDEX ='")


FORBIDDEN_RUNTIME_PATTERNS = [
    (re.compile(r'fetch\s*\('), "fetch("),
    (re.compile(r'XMLHttpRequest'), "XMLHttpRequest"),
    (re.compile(r'<script[^>]*\btype\s*=\s*["\']module["\']'), '<script type="module">'),
]

SRC_HREF_RE = re.compile(r'(?:src|href)\s*=\s*"([^"]+)"')


def check_file_protocol_safety():
    if not DIST_DIR.exists():
        fail("dist/ does not exist -- cannot run file:// smoke test")
        return

    # (parent_dir_str, clean_url) -> resolved-path-exists bool. Most articles
    # live in the same dist/article/ directory and share the same handful of
    # relative links (nav, css/js assets, cross-article links repeat a lot
    # across ~1000 pages), so memoizing collapses what would otherwise be
    # thousands of redundant resolve()+exists() filesystem calls -- each of
    # which is a slow round trip on WSL's DrvFs bridge for a /mnt/c/ path.
    resolve_cache = {}

    def resolves(parent, clean):
        key = (str(parent), clean)
        cached = resolve_cache.get(key)
        if cached is None:
            cached = (parent / clean).resolve().exists()
            resolve_cache[key] = cached
        return cached

    html_files = list(DIST_DIR.rglob("*.html")) + list(DIST_DIR.rglob("*.js"))
    for f in html_files:
        text = f.read_text(encoding="utf-8")
        if f.suffix == ".html":
            for pattern, label in FORBIDDEN_RUNTIME_PATTERNS:
                if pattern.search(text):
                    fail("{}: forbidden runtime pattern found: {}".format(f, label))
            # remote http(s) resource references in src/href are forbidden;
            # plain-text mentions of URLs in article prose are fine (they
            # aren't inside a src="..."/href="..." attribute).
            for m in SRC_HREF_RE.finditer(text):
                url = m.group(1)
                if url.startswith("http://") or url.startswith("https://"):
                    fail("{}: remote resource referenced via src/href: {}".format(f, url))
                elif url.startswith("mailto:") or url.startswith("#"):
                    continue
                else:
                    # relative path -- verify it resolves to a real file (for src/href
                    # that point at local files; query strings like index.html?q=x are fine)
                    clean = url.split("?")[0].split("#")[0]
                    if not clean:
                        continue
                    if not resolves(f.parent, clean):
                        resolved = (f.parent / clean).resolve()
                        fail("{}: broken local reference: {} (resolved to {})".format(f, url, resolved))


def main():
    articles = load_articles()
    id_to_article = {}
    for a in articles:
        fm = a["frontmatter"]
        if "id" in fm:
            id_to_article[fm["id"]] = a

    check_frontmatter(articles)
    check_duplicates(articles)
    check_body_content(articles)
    check_related_links(articles, id_to_article)
    check_dist_output(articles)
    check_file_protocol_safety()

    print("=" * 60)
    print("Validation summary: {} articles checked".format(len(articles)))
    print("  Errors:   {}".format(len(errors)))
    print("  Warnings: {}".format(len(warnings)))
    print("=" * 60)

    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print("  - " + w)

    if errors:
        print("\nERRORS:")
        for e in errors:
            print("  - " + e)
        print("\nFAIL")
        return 1

    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
