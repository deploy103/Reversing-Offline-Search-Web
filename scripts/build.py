#!/usr/bin/env python3
"""
Build script for Reversing-Offline-Search-Web.

Reads content/articles/**/*.md, converts them to static HTML pages under
dist/article/, generates dist/assets/search-index.js and dist/index.html,
and copies hand-written assets/css and assets/js into dist/assets/.

Stdlib only. Run from repo root:

    python3 scripts/build.py

Idempotent: dist/ is fully regenerated from content/ + assets/ each run.
"""
import glob
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import mdlib  # noqa: E402

ROOT = SCRIPT_DIR.parent
CONTENT_DIR = ROOT / "content" / "articles"
DIST_DIR = ROOT / "dist"
ASSETS_SRC = ROOT / "assets"

REQUIRED_FIELDS = [
    "id", "title", "slug", "category", "difficulty",
    "platform", "architecture", "format", "tools",
    "keywords", "aliases", "symptom_keywords", "source_ids", "last_verified",
]

# Required top-level navigation, mapped to query-string
# entry points into index.html. Categories that don't have any articles yet
# simply render an empty-state message -- this is expected at Phase 1.
NAV_ITEMS = [
    ("처음 시작", "index.html"),
    ("30초 트리아지", "index.html?cat=triage"),
    ("파일 종류별 접근", "index.html?q=%ED%99%95%EC%9E%A5%EC%9E%90"),
    ("증상으로 찾기", "index.html?stuck=1"),
    ("Assembly Dictionary", "index.html?cat=assembly"),
    ("Windows / PE", "index.html?q=PE"),
    ("Linux / ELF", "index.html?cat=linux-elf"),
    ("정적 분석", "index.html?cat=static-analysis"),
    ("동적 분석", "index.html?cat=dynamic-analysis"),
    ("패킹 / 안티디버깅", "index.html?cat=packing"),
    ("알고리즘 패턴", "index.html?cat=algorithms"),
    ("툴 사용법", "index.html?cat=tools"),
    ("단축키", "index.html?q=%EB%8B%A8%EC%B6%95%ED%82%A4"),
    ("자동화 / Solver", "index.html?cat=automation"),
    ("Write-up (드림핵)", "index.html?cat=writeup"),
    ("C 코드 분석", "index.html?cat=c-analysis"),
    ("타 아키텍처/언어", "index.html?cat=other-targets"),
]

DIFFICULTY_LABEL = {"beginner": "입문", "basic": "기초", "intermediate": "중급"}


def esc(s):
    return html.escape(str(s), quote=True)


# --------------------------------------------------------------------------
# Discovery / parsing
# --------------------------------------------------------------------------

def discover_articles():
    paths = sorted(glob.glob(str(CONTENT_DIR / "**" / "*.md"), recursive=True))
    articles = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8")
        try:
            fm, body_md = mdlib.split_frontmatter(text)
        except ValueError as e:
            raise SystemExit("frontmatter error in {}: {}".format(p, e))
        missing = [f for f in REQUIRED_FIELDS if f not in fm]
        if missing:
            raise SystemExit("{}: missing frontmatter fields: {}".format(p, missing))
        category_dir = Path(p).parent.name
        articles.append({
            "path": p,
            "frontmatter": fm,
            "body_md": body_md,
            "category_dir": category_dir,
        })
    return articles


def build_id_index(articles):
    id_to_article = {}
    slug_to_article = {}
    for a in articles:
        fm = a["frontmatter"]
        if fm["id"] in id_to_article:
            raise SystemExit("duplicate id: {}".format(fm["id"]))
        if fm["slug"] in slug_to_article:
            raise SystemExit("duplicate slug: {}".format(fm["slug"]))
        id_to_article[fm["id"]] = a
        slug_to_article[fm["slug"]] = a
    return id_to_article, slug_to_article


RELATED_HEADING = "관련 글"


def process_related_section(body_md, own_id, id_to_article):
    """Rewrite '- REV-XXXX — Title' bullets in the '관련 글' section into real
    markdown links when the target article exists in this build's corpus.
    Returns (new_body_md, related_ids) where related_ids only contains ids
    that were actually resolved (and thus linked) -- these are used for the
    search index's "related result links" feature.
    """
    lines = body_md.split("\n")
    out = []
    in_related = False
    related_ids = []
    bullet_re = re.compile(r'^-\s+(REV-\d{4})\s+—\s+(.*)$')
    for line in lines:
        heading_m = re.match(r'^(#{1,3})\s+(.*)$', line.strip())
        if heading_m:
            in_related = heading_m.group(2).strip() == RELATED_HEADING
            out.append(line)
            continue
        if in_related:
            m = bullet_re.match(line.strip())
            if m:
                rid, rest = m.group(1), m.group(2)
                if rid in id_to_article and rid != own_id:
                    target_slug = id_to_article[rid]["frontmatter"]["slug"]
                    out.append("- [{} — {}]({}.html)".format(rid, rest, target_slug))
                    related_ids.append(rid)
                    continue
        out.append(line)
    return "\n".join(out), related_ids


LOCAL_MD_LINK_RE = re.compile(r'\]\(([^)]+?\.md)\)')


def rewrite_local_md_links(body_md, slug_to_article):
    """Rewrite any markdown link pointing at a local '*.md' article (written
    directly by content authors as e.g. '[LEA](./rev-0042-lea.md)' or
    '[...](../binary-basics/rev-0024-twos-complement.md)') into the flat
    '<slug>.html' path that actually exists under dist/article/.

    Only rewrites when the referenced slug exists in this build's corpus;
    otherwise the link is left untouched so scripts/validate.py's broken-link
    check can still catch genuinely dead references.
    """
    def repl(m):
        href = m.group(1)
        if href.startswith("http://") or href.startswith("https://"):
            return m.group(0)
        basename = href.rsplit("/", 1)[-1]
        slug = basename[:-3] if basename.endswith(".md") else basename
        if slug in slug_to_article:
            return "]({}.html)".format(slug)
        return m.group(0)
    return LOCAL_MD_LINK_RE.sub(repl, body_md)


LOCAL_IMAGE_RE = re.compile(r'(!\[[^\]]*\]\()(/assets/images/[^)]+)(\))')


def rewrite_local_image_paths(body_md):
    """Rewrite author-written site-root-relative image paths
    ('![alt](/assets/images/diagrams/foo.svg)') into the '../assets/images/...'
    path that actually resolves from dist/article/<slug>.html (which always
    lives exactly one directory below dist/).
    """
    def repl(m):
        return m.group(1) + ".." + m.group(2) + m.group(3)
    return LOCAL_IMAGE_RE.sub(repl, body_md)


# --------------------------------------------------------------------------
# HTML templating
# --------------------------------------------------------------------------

def nav_html(prefix):
    items = []
    for label, target in NAV_ITEMS:
        items.append('<li><a href="{}{}">{}</a></li>'.format(prefix, target, esc(label)))
    return "<ul>" + "".join(items) + "</ul>"


def header_html(prefix):
    return """<header class="site-header">
  <div class="header-top">
    <a class="site-title" href="{p}index.html">Reversing 오프라인 위키</a>
    <form class="header-search" action="{p}index.html" method="get">
      <input type="search" name="q" placeholder="검색: call, positive sp value, 16777619...">
      <button type="submit">검색</button>
    </form>
    <button id="theme-toggle" type="button">다크 모드</button>
  </div>
  <nav class="site-nav">
    {nav}
  </nav>
</header>""".format(p=prefix, nav=nav_html(prefix))


def footer_html():
    return """<footer class="site-footer">
  <p>Reversing-Offline-Search-Web &mdash; 완전 오프라인 한국어 리버싱 지식베이스. 인터넷 연결 없이 <code>dist/index.html</code>을 더블클릭해서 사용하세요.</p>
</footer>"""


ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Reversing 오프라인 위키</title>
<link rel="stylesheet" href="../assets/css/style.css">
</head>
<body>
{header}
<main>
<div class="breadcrumb"><a href="../index.html">홈</a> / {category}</div>
<article class="article-body">
<h1>{title}</h1>
<div class="article-meta">{tags}</div>
{body}
</article>
</main>
{footer}
<script src="../assets/search-index.js"></script>
<script src="../assets/js/theme.js"></script>
<script src="../assets/js/search.js"></script>
</body>
</html>
"""


def tag_list_for(fm):
    tags = [fm.get("category", ""), DIFFICULTY_LABEL.get(fm.get("difficulty", ""), fm.get("difficulty", ""))]
    tags += fm.get("platform", []) or []
    tags += fm.get("format", []) or []
    tags += fm.get("tools", []) or []
    return [t for t in tags if t]


def render_article_html(article, id_to_article, slug_to_article):
    fm = article["frontmatter"]
    body_md, related_ids = process_related_section(article["body_md"], fm["id"], id_to_article)
    body_md = rewrite_local_md_links(body_md, slug_to_article)
    body_md = rewrite_local_image_paths(body_md)
    body_html = mdlib.markdown_to_html(body_md)
    tags_html = "".join('<span class="tag">{}</span>'.format(esc(t)) for t in tag_list_for(fm))
    page = ARTICLE_TEMPLATE.format(
        title=esc(fm["title"]),
        header=header_html("../"),
        category=esc(fm["category"]),
        tags=tags_html,
        body=body_html,
        footer=footer_html(),
    )
    return page, related_ids


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reversing 오프라인 위키 &mdash; 오프라인 리버싱 지식베이스</title>
<link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
{header}
<main>
<section class="hero">
  <h1>오프라인 리버싱 지식베이스</h1>
  <p>인터넷 없이 CTF / 워게임 리버싱 문제를 풀 때 바로 찾아보는 한국어 검색 위키입니다.</p>
  <form class="big-search" id="search-form">
    <input type="search" id="search-input" placeholder="예: call, positive sp value, 16777619, main 어디, rsp 뭐임" autofocus>
    <button type="submit">검색</button>
  </form>
  <div class="stuck-toggle">
    <label><input type="checkbox" id="stuck-mode"> 막혔을 때 모드 (증상 · 에러 글 우선)</label>
  </div>
</section>

<div id="search-results"></div>

<section class="entry-callouts">
  <div class="callout">
    <h2>파일 받았을 때 30초 트리아지</h2>
    <p>처음 보는 문제 파일을 받았을 때 무엇부터 확인해야 하는지 순서대로 정리했습니다.</p>
    <a href="article/rev-0001-first-30-seconds.html">30초 트리아지 읽기 →</a>
  </div>
  <div class="callout">
    <h2>처음이라 아무것도 모르겠음</h2>
    <p>리버싱이 처음이라면 여기서부터 시작하세요. 파일 형식 확인부터 main 찾기까지 이어집니다.</p>
    <a href="article/rev-0001-first-30-seconds.html">시작하기 →</a>
  </div>
</section>

<section class="home-section">
  <h2>빠른 카테고리</h2>
  <div class="quick-links">
    <a href="index.html?q=PE">PE / EXE</a>
    <a href="index.html?cat=linux-elf">ELF</a>
    <a href="index.html?cat=assembly">Assembly Dictionary</a>
    <a href="index.html?q=IDA">IDA</a>
    <a href="index.html?q=Ghidra">Ghidra</a>
    <a href="index.html?q=x64dbg">x64dbg</a>
    <a href="index.html?q=GDB">GDB / Pwndbg</a>
    <a href="index.html?q=UPX">패킹</a>
    <a href="index.html?cat=algorithms">알고리즘 패턴</a>
    <a href="index.html?stuck=1">막힌 상황 모음 (stuck mode)</a>
  </div>
</section>
</main>
{footer}
<script src="assets/search-index.js"></script>
<script src="assets/js/theme.js"></script>
<script src="assets/js/search.js"></script>
</body>
</html>
"""


def render_index_html():
    return INDEX_TEMPLATE.format(header=header_html(""), footer=footer_html())


# --------------------------------------------------------------------------
# Search index
# --------------------------------------------------------------------------

def build_search_index_entries(articles, related_ids_by_id):
    entries = []
    for a in articles:
        fm = a["frontmatter"]
        headings = mdlib.extract_headings(a["body_md"])
        body_text = mdlib.markdown_to_plain_text(a["body_md"])
        entries.append({
            "id": fm["id"],
            "title": fm["title"],
            "slug": fm["slug"],
            "url": "article/{}.html".format(fm["slug"]),
            "category": fm["category"],
            "difficulty": fm["difficulty"],
            "platform": fm.get("platform", []),
            "architecture": fm.get("architecture", []),
            "format": fm.get("format", []),
            "tools": fm.get("tools", []),
            "keywords": fm.get("keywords", []),
            "aliases": fm.get("aliases", []),
            "symptom_keywords": fm.get("symptom_keywords", []),
            "headings": headings,
            "body_text": body_text,
            "related_ids": related_ids_by_id.get(fm["id"], []),
        })
    return entries


def write_search_index_js(entries, out_path):
    payload = json.dumps(entries, ensure_ascii=False, indent=0)
    content = "window.SEARCH_INDEX = " + payload + ";\n"
    out_path.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------
# Main build
# --------------------------------------------------------------------------

def main():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    (DIST_DIR / "article").mkdir(parents=True)
    (DIST_DIR / "assets" / "css").mkdir(parents=True)
    (DIST_DIR / "assets" / "js").mkdir(parents=True)
    (DIST_DIR / "assets" / "images").mkdir(parents=True)

    articles = discover_articles()
    if not articles:
        raise SystemExit("no articles found under {}".format(CONTENT_DIR))

    id_to_article, slug_to_article = build_id_index(articles)

    related_ids_by_id = {}
    rendered_pages = {}
    for a in articles:
        page_html, related_ids = render_article_html(a, id_to_article, slug_to_article)
        slug = a["frontmatter"]["slug"]
        rendered_pages[slug] = page_html
        related_ids_by_id[a["frontmatter"]["id"]] = related_ids

    for slug, page_html in rendered_pages.items():
        out_file = DIST_DIR / "article" / "{}.html".format(slug)
        out_file.write_text(page_html, encoding="utf-8")

    entries = build_search_index_entries(articles, related_ids_by_id)
    write_search_index_js(entries, DIST_DIR / "assets" / "search-index.js")

    (DIST_DIR / "index.html").write_text(render_index_html(), encoding="utf-8")

    for css_file in sorted(glob.glob(str(ASSETS_SRC / "css" / "*.css"))):
        shutil.copy2(css_file, DIST_DIR / "assets" / "css" / Path(css_file).name)
    for js_file in sorted(glob.glob(str(ASSETS_SRC / "js" / "*.js"))):
        shutil.copy2(js_file, DIST_DIR / "assets" / "js" / Path(js_file).name)

    images_src = ASSETS_SRC / "images"
    if images_src.exists():
        shutil.copytree(images_src, DIST_DIR / "assets" / "images", dirs_exist_ok=True)

    print("Built {} articles into {}".format(len(articles), DIST_DIR))
    for a in articles:
        print("  - {} ({})".format(a["frontmatter"]["id"], a["frontmatter"]["slug"]))


if __name__ == "__main__":
    main()
