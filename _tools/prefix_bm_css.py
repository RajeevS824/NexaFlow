#!/usr/bin/env python3
"""Prefix every top-level selector in a CSS file with a wrapper class so the
Business Map styles stay scoped and cannot leak into / be overridden by the
rest of the NexaFlow workspace (which uses some of the same generic class
names). Usage: prefix_bm_css.py <in.css> <out.css> [prefix]
"""
import re
import sys

PREFIX = ".business-map-app "

# Strip C-style block comments up front so they can't be mistaken for, or
# split across, selectors when we scan braces. Replaced with a single space
# so token boundaries stay intact but line 1 stays clean.
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def prefix_selectors(head, prefix):
    parts = head.split(",")
    new_parts = []
    for p in parts:
        core = p.strip()
        lead = p[: len(p) - len(p.lstrip())]
        trail = p[len(p.rstrip()):]
        if core == ":root":
            new_parts.append(lead + prefix.strip() + trail)
        elif core and not core.startswith("@"):
            new_parts.append(lead + prefix + core + trail)
        else:
            new_parts.append(p)
    return ",".join(new_parts)


def prefix_css(text, prefix=PREFIX):
    out = []
    i = 0
    n = len(text)
    while i < n:
        j = text.find("{", i)
        if j == -1:
            out.append(text[i:])
            break
        head = text[i:j]
        depth = 1
        k = j + 1
        while k < n and depth > 0:
            ch = text[k]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            k += 1
        body = text[j + 1 : k - 1]
        head_stripped = head.strip()
        close = text[k - 1] if k - 1 < n else "}"
        if head_stripped.startswith("@media"):
            inner = prefix_css(body, prefix)
            out.append(head + "{" + inner + "}")
        elif head_stripped.startswith("@"):
            out.append(head + "{" + body + "}")
        else:
            new_head = prefix_selectors(head, prefix)
            out.append(new_head + "{" + body + "}")
        i = k
    return "".join(out)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 else PREFIX
    with open(src, "r", encoding="utf-8") as f:
        text = f.read()
    text = _COMMENT_RE.sub(" ", text)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(prefix_css(text, prefix))
    print(f"prefixed {src} -> {dst}")


if __name__ == "__main__":
    main()
