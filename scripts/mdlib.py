"""
Dependency-free frontmatter + Markdown helpers for the Reversing-Offline-Search-Web
build pipeline. Stdlib only.

This module intentionally implements a SMALL, PREDICTABLE subset of YAML and
Markdown -- just enough for the article format described in AGENTS.md. It is
NOT a general-purpose YAML or CommonMark parser.
"""
import html
import re


# --------------------------------------------------------------------------
# Frontmatter parsing
# --------------------------------------------------------------------------

def split_frontmatter(text):
    """Split a markdown file's text into (frontmatter_dict, body_markdown).

    Frontmatter is delimited by '---' lines at the very top of the file.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing frontmatter start '---'")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("missing frontmatter end '---'")

    fm_lines = lines[1:end_idx]
    body_lines = lines[end_idx + 1:]
    frontmatter = parse_flat_yaml(fm_lines)
    body = "\n".join(body_lines).strip("\n")
    return frontmatter, body


def _parse_scalar(raw):
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    return raw


def _parse_inline_list(raw):
    """Parse a YAML flow-style list like [windows, linux] or [] or ["a", "b"]."""
    raw = raw.strip()
    assert raw.startswith("[") and raw.endswith("]")
    inner = raw[1:-1].strip()
    if inner == "":
        return []
    items = []
    current = ""
    in_quote = None
    for ch in inner:
        if in_quote:
            if ch == in_quote:
                in_quote = None
            current += ch
        elif ch in ('"', "'"):
            in_quote = ch
            current += ch
        elif ch == ",":
            items.append(_parse_scalar(current.strip()))
            current = ""
        else:
            current += ch
    if current.strip() != "":
        items.append(_parse_scalar(current.strip()))
    return items


def parse_flat_yaml(lines):
    """Parse a simple flat YAML mapping: key: value / key: [list] / key: "str".

    Also supports block-style lists:
        keywords:
          - a
          - b
    """
    result = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        m = re.match(r'^([A-Za-z0-9_]+):\s*(.*)$', line)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2)
        rest = rest.strip()
        if rest == "":
            # Possibly a block list on following lines
            items = []
            j = i + 1
            while j < n and re.match(r'^\s*-\s*(.*)$', lines[j]):
                item_m = re.match(r'^\s*-\s*(.*)$', lines[j])
                items.append(_parse_scalar(item_m.group(1)))
                j += 1
            result[key] = items
            i = j
            continue
        elif rest.startswith("["):
            result[key] = _parse_inline_list(rest)
            i += 1
        else:
            result[key] = _parse_scalar(rest)
            i += 1
    return result


# --------------------------------------------------------------------------
# Markdown -> HTML conversion (small, dependency-free subset)
# --------------------------------------------------------------------------

def _inline_to_html(text):
    """Convert inline markdown (bold, code, links) to HTML. Escapes raw text first.

    Inline code spans are pulled out into placeholders BEFORE bold/link
    processing runs, so literal '**' or '[...]'-looking text inside code
    (e.g. `char**argv`, `2**bits`) can never be misinterpreted as markdown
    markup by the later passes.
    """
    # Escape HTML special chars first, then re-introduce markup.
    text = html.escape(text, quote=False)

    # Inline code `...` -- extract to placeholders first so its raw content
    # is immune to the bold/link regexes below.
    code_spans = []

    def code_stash(m):
        code_spans.append(m.group(1))
        return "\x00CODE{}\x00".format(len(code_spans) - 1)

    text = re.sub(r'`([^`]+)`', code_stash, text)

    # Links [text](url)
    def link_sub(m):
        label, url = m.group(1), m.group(2)
        return '<a href="{}">{}</a>'.format(url, label)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link_sub, text)

    # Bold **text**
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)

    # Restore code spans
    def code_restore(m):
        idx = int(m.group(1))
        return '<code>' + code_spans[idx] + '</code>'

    text = re.sub(r'\x00CODE(\d+)\x00', code_restore, text)

    return text


def markdown_to_html(md_text):
    """Convert a small subset of Markdown to HTML.

    Supported: #/##/### headers, paragraphs, **bold**, `code`, fenced ``` blocks,
    unordered '-' lists, ordered '1.' lists, blockquotes '>', links, horizontal rules '---'.
    """
    lines = md_text.split("\n")
    html_out = []
    i = 0
    n = len(lines)

    def flush_paragraph(buf):
        if buf:
            joined = " ".join(l.strip() for l in buf if l.strip())
            if joined:
                html_out.append("<p>" + _inline_to_html(joined) + "</p>")
            buf.clear()

    para_buf = []

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith("```"):
            flush_paragraph(para_buf)
            lang = stripped[3:].strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            code_content = html.escape("\n".join(code_lines), quote=False)
            cls = ' class="language-{}"'.format(lang) if lang else ""
            html_out.append("<pre><code{}>{}</code></pre>".format(cls, code_content))
            continue

        # Horizontal rule
        if re.match(r'^-{3,}$', stripped):
            flush_paragraph(para_buf)
            html_out.append("<hr>")
            i += 1
            continue

        # Headers
        header_m = re.match(r'^(#{1,3})\s+(.*)$', stripped)
        if header_m:
            flush_paragraph(para_buf)
            level = len(header_m.group(1))
            content = header_m.group(2).strip()
            html_out.append("<h{0}>{1}</h{0}>".format(level, _inline_to_html(content)))
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            flush_paragraph(para_buf)
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            joined = " ".join(l.strip() for l in quote_lines if l.strip())
            html_out.append("<blockquote><p>" + _inline_to_html(joined) + "</p></blockquote>")
            continue

        # Unordered list
        if re.match(r'^-\s+', stripped):
            flush_paragraph(para_buf)
            items = []
            while i < n and re.match(r'^-\s+', lines[i].strip()):
                item_text = re.match(r'^-\s+(.*)$', lines[i].strip()).group(1)
                items.append(item_text)
                i += 1
            html_out.append("<ul>" + "".join(
                "<li>" + _inline_to_html(it) + "</li>" for it in items
            ) + "</ul>")
            continue

        # Ordered list
        if re.match(r'^\d+\.\s+', stripped):
            flush_paragraph(para_buf)
            items = []
            while i < n and re.match(r'^\d+\.\s+', lines[i].strip()):
                item_text = re.match(r'^\d+\.\s+(.*)$', lines[i].strip()).group(1)
                items.append(item_text)
                i += 1
            html_out.append("<ol>" + "".join(
                "<li>" + _inline_to_html(it) + "</li>" for it in items
            ) + "</ol>")
            continue

        # Table row (very small GFM-table subset: header | header \n --- | ---)
        if stripped.startswith("|") and i + 1 < n and re.match(r'^\|?[\s:|-]+\|?$', lines[i + 1].strip()) and "-" in lines[i + 1]:
            flush_paragraph(para_buf)
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            body_rows = []
            while i < n and lines[i].strip().startswith("|"):
                row_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                body_rows.append(row_cells)
                i += 1
            table_html = ["<table>", "<thead><tr>"]
            for c in header_cells:
                table_html.append("<th>" + _inline_to_html(c) + "</th>")
            table_html.append("</tr></thead><tbody>")
            for row in body_rows:
                table_html.append("<tr>")
                for c in row:
                    table_html.append("<td>" + _inline_to_html(c) + "</td>")
                table_html.append("</tr>")
            table_html.append("</tbody></table>")
            html_out.append("".join(table_html))
            continue

        # Blank line -> flush paragraph
        if stripped == "":
            flush_paragraph(para_buf)
            i += 1
            continue

        # Otherwise, accumulate into paragraph
        para_buf.append(line)
        i += 1

    flush_paragraph(para_buf)
    return "\n".join(html_out)


def extract_headings(md_text):
    """Return list of heading strings (text only, no #) for #, ##, ### lines."""
    headings = []
    for line in md_text.split("\n"):
        m = re.match(r'^(#{1,3})\s+(.*)$', line.strip())
        if m:
            headings.append(m.group(2).strip())
    return headings


def markdown_to_plain_text(md_text):
    """Strip markdown syntax down to plain text, for full-text search indexing."""
    text = md_text
    # Remove fenced code blocks entirely is too aggressive for search; keep content but drop fences.
    text = re.sub(r'```[a-zA-Z0-9_+-]*\n', '', text)
    text = text.replace("```", "")
    lines = []
    for line in text.split("\n"):
        s = line.strip()
        s = re.sub(r'^#{1,6}\s+', '', s)          # headers
        s = re.sub(r'^-\s+', '', s)                # unordered list marker
        s = re.sub(r'^\d+\.\s+', '', s)             # ordered list marker
        s = re.sub(r'^>\s?', '', s)                 # blockquote marker
        s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)    # bold
        s = re.sub(r'`([^`]+)`', r'\1', s)           # inline code
        s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)  # links -> text only
        s = re.sub(r'\|', ' ', s)                    # table pipes
        if s.strip('-') == '' and s != '':
            continue  # skip separator rows like --- or ---|---
        lines.append(s)
    joined = " ".join(l for l in lines if l.strip())
    joined = re.sub(r'\s+', ' ', joined).strip()
    return joined
