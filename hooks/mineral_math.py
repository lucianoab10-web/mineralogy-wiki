"""Make Obsidian's single-line $$ formulas render inside Markdown tables.

Arithmatex recognizes $$ as block math, but a table cell needs inline math.
This changes only the text passed to the web build; the Markdown files and
the Obsidian vault remain untouched.
"""

from __future__ import annotations

import re


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_CODE = re.compile(r"<(code|pre)\b[^>]*>.*?</\1\s*>|<!--.*?-->", re.IGNORECASE)


def _escaped(text: str, position: int) -> bool:
    preceding = position
    while preceding and text[preceding - 1] == "\\":
        preceding -= 1
    return (position - preceding) % 2 == 1


def _literal_ranges(text: str) -> list[tuple[int, int]]:
    """Locate matched code spans; unmatched backticks remain ordinary text."""
    ranges = [(match.start(), match.end()) for match in _HTML_CODE.finditer(text)]
    cursor = 0
    while cursor < len(text):
        match = re.search(r"`+", text[cursor:])
        if match is None:
            break
        start, end = cursor + match.start(), cursor + match.end()
        if _escaped(text, start) or any(a <= start < b for a, b in ranges):
            cursor = end
            continue
        closing = next((candidate for candidate in re.finditer(r"`+", text[end:])
                        if len(candidate.group()) == end - start), None)
        if closing is None:
            cursor = end
            continue
        stop = end + closing.end()
        ranges.append((start, stop))
        cursor = stop
    return sorted(ranges)


def _cells(line: str) -> list[tuple[int, int]]:
    literals = _literal_ranges(line)
    pipes = [index for index, character in enumerate(line)
             if character == "|" and not _escaped(line, index)
             and not any(start <= index < end for start, end in literals)]
    if not pipes:
        return []
    boundaries = [-1, *pipes, len(line)]
    cells = [(left + 1, right) for left, right in zip(boundaries, boundaries[1:])]
    if not line[:pipes[0]].strip():
        cells.pop(0)
    if cells and not line[pipes[-1] + 1:].strip():
        cells.pop()
    return cells


def _inline(body: str) -> str:
    body = body.strip()
    before, after = "", ""
    # Some Obsidian table formulas include a trailing HTML line break. Keep
    # that break in the cell, outside MathJax's expression.
    while (match := _BREAK.match(body)) is not None:
        before += match.group()
        body = body[match.end():].lstrip()
    while (match := re.search(r"<br\s*/?>$", body, re.IGNORECASE)) is not None:
        after = match.group() + after
        body = body[:match.start()].rstrip()
    return before + ("$" + body + "$" if body else "") + after


def _math_segment(text: str) -> str:
    tokens = [match for match in re.finditer(r"\$+", text)
              if len(match.group()) == 2 and not _escaped(text, match.start())]
    pieces = []
    cursor = 0
    for opening, closing in zip(tokens[::2], tokens[1::2]):
        body = text[opening.end():closing.start()]
        # Leave malformed/nested dollar syntax alone rather than turning a
        # literal example into a different expression.
        if any(not _escaped(body, match.start()) for match in re.finditer(r"\$", body)):
            continue
        pieces.extend((text[cursor:opening.start()], _inline(body)))
        cursor = closing.end()
    return "".join(pieces) + text[cursor:]


def _cell_math(cell: str) -> str:
    result = []
    cursor = 0
    for start, end in _literal_ranges(cell):
        if start < cursor:
            continue
        result.extend((_math_segment(cell[cursor:start]), cell[start:end]))
        cursor = end
    return "".join(result) + _math_segment(cell[cursor:])


def _row_math(line: str) -> str:
    for start, end in reversed(_cells(line)):
        line = line[:start] + _cell_math(line[start:end]) + line[end:]
    return line


def normalize_table_math(markdown: str) -> str:
    lines = markdown.splitlines(keepends=True)
    blocked = set()
    fence = None
    html_end = None
    frontmatter = bool(lines and lines[0].strip() == "---")
    for index, line in enumerate(lines):
        if frontmatter:
            blocked.add(index)
            if index and line.strip() in {"---", "..."}:
                frontmatter = False
            continue
        if fence is not None:
            blocked.add(index)
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = None
            continue
        marker = _FENCE.match(line)
        if marker is not None:
            fence = marker.group(1)
            blocked.add(index)
            continue
        if html_end is not None:
            blocked.add(index)
            if re.search(html_end, line, re.IGNORECASE):
                html_end = None
            continue
        html = re.match(r"\s*(<!--|<(pre|code)\b)", line, re.IGNORECASE)
        if html is not None:
            end = r"-->" if html.group(1) == "<!--" else r"</" + html.group(2) + r"\s*>"
            blocked.add(index)
            if not re.search(end, line, re.IGNORECASE):
                html_end = end
        elif line.startswith(("    ", "\t")):
            blocked.add(index)

    index = 0
    while index + 1 < len(lines):
        header = _cells(lines[index])
        separator = _cells(lines[index + 1])
        table = (index not in blocked and index + 1 not in blocked and header
                 and len(header) == len(separator)
                 and all(re.fullmatch(r"\s*:?-+:?\s*", lines[index + 1][start:end])
                         for start, end in separator))
        if not table:
            index += 1
            continue
        lines[index] = _row_math(lines[index])
        index += 2  # Leave the delimiter row exactly as it was.
        while index < len(lines) and index not in blocked and lines[index].strip() and _cells(lines[index]):
            lines[index] = _row_math(lines[index])
            index += 1
    return "".join(lines)


def on_page_markdown(markdown, **kwargs):
    return normalize_table_math(markdown)
