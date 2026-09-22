#!/usr/bin/env python3
"""Build a Waikiki ``.wiki`` file from the markdown pages in ``wiki/``.

A Waikiki wiki is a single self-contained SQLite database (Waikiki → the
**Wikis** page → *Open wiki file…*). This script materialises one from the
plain-markdown sources next to it, so the wiki stays diffable in git while
still being openable in Waikiki.

Page metadata comes from each file's frontmatter:

    ---
    title: Feature Inventory      # page title (defaults to the filename)
    parent: verinfast-v2          # slug of the parent page
    tags: v2, features            # comma-separated
    ---

The slug is the filename without ``.md``. ``[[Wikilinks]]`` resolve by title
or slug, exactly as they do inside Waikiki.

HTML is pre-rendered so pages read correctly the moment the wiki is opened. If
a Waikiki checkout is available (``--waikiki /path/to/waikiki``) its own
renderer is used for byte-identical output; otherwise a markdown-it-py
rendering with the same wikilink expansion is used, and Waikiki will re-render
on its next save.

Usage:
    python docs/v2/build_wiki.py                      # → docs/v2/VerinFast-v2.wiki
    python docs/v2/build_wiki.py -o /tmp/out.wiki --waikiki ~/src/waikiki
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIKI_SRC = HERE / "wiki"

#: Folder documentation, not wiki pages.
NOT_PAGES = {"README.md", "CLAUDE.md"}

# Waikiki's page schema (waikiki/db.py::SCHEMA). Only the tables a freshly
# imported, content-only wiki needs: the RAG/vector tables are built lazily by
# Waikiki itself on first embed.
SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    slug       TEXT UNIQUE NOT NULL,
    title      TEXT NOT NULL,
    markdown   TEXT NOT NULL DEFAULT '',
    html       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    starred    INTEGER NOT NULL DEFAULT 0,
    parent_id  INTEGER REFERENCES pages(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS page_ydoc (
    page_id      INTEGER PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    ydoc_state   BLOB NOT NULL,
    spec_version INTEGER NOT NULL DEFAULT 1,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS page_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id    INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    markdown   TEXT NOT NULL,
    author     TEXT NOT NULL DEFAULT 'human',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id    INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    author     TEXT NOT NULL DEFAULT 'human',
    body       TEXT NOT NULL,
    resolved   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suggestions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id    INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    author     TEXT NOT NULL DEFAULT 'ai',
    note       TEXT NOT NULL DEFAULT '',
    markdown   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS page_tags (
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    PRIMARY KEY (page_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_page_tags_tag ON page_tags(tag);

CREATE TABLE IF NOT EXISTS templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    markdown    TEXT NOT NULL DEFAULT '',
    meta_schema TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS activity (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL DEFAULT (datetime('now')),
    actor  TEXT NOT NULL,
    action TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity(ts);

CREATE TABLE IF NOT EXISTS custom_elements (
    slug   TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    fields TEXT NOT NULL DEFAULT '[]',
    html   TEXT NOT NULL DEFAULT '',
    css    TEXT NOT NULL DEFAULT '',
    js     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    filename   TEXT NOT NULL,
    mimetype   TEXT NOT NULL,
    data       BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    title, markdown,
    content='pages', content_rowid='id',
    tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, title, markdown) VALUES (new.id, new.title, new.markdown);
END;
CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, title, markdown) VALUES ('delete', old.id, old.title, old.markdown);
END;
CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, title, markdown) VALUES ('delete', old.id, old.title, old.markdown);
    INSERT INTO pages_fts(rowid, title, markdown) VALUES (new.id, new.title, new.markdown);
END;

CREATE TABLE IF NOT EXISTS chunks (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    ord     INTEGER NOT NULL,
    text    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_page ON chunks(page_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks', content_rowid='id',
    tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
"""

_FM = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def page_files(src: Path) -> list[Path]:
    """Every markdown file in *src* that is a wiki page."""
    return sorted(p for p in src.glob("*.md") if p.name not in NOT_PAGES)


def slugify(text: str) -> str:
    """Waikiki's slug rule: lowercase, non-alphanumerics to hyphens."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "page"


def parse_frontmatter(markdown: str) -> tuple[dict, list[str], str]:
    """(properties, tags, body) — a port of waikiki/structure.py."""
    text = (markdown or "").replace("\r\n", "\n").replace("\r", "\n")
    m = _FM.match(text)
    if not m:
        return {}, [], text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            if k.strip():
                meta[k.strip()] = v.strip()
    tags: list[str] = []
    for key in list(meta):
        if key.lower() == "tags":
            tags = [
                t.strip().lower() for t in re.split(r"[,;]", meta.pop(key)) if t.strip()
            ]
    return meta, tags, text[m.end() :]


def load_renderer(waikiki_path: str | None):
    """Waikiki's own renderer when we can reach it, else markdown-it-py."""
    if waikiki_path:
        sys.path.insert(0, str(Path(waikiki_path).resolve()))
        try:
            from waikiki import render as wk_render  # type: ignore

            return lambda md, resolve: wk_render.render_markdown(
                md, resolve, allow_html=False
            )
        except Exception as exc:  # pragma: no cover - optional path
            print(
                f"  ! waikiki renderer unavailable ({exc}); falling back",
                file=sys.stderr,
            )

    from markdown_it import MarkdownIt

    md = MarkdownIt("gfm-like", {"html": False, "linkify": True, "typographer": False})

    def render(markdown: str, resolve) -> str:
        def sub(m: re.Match) -> str:
            target, label = m.group(1).strip(), (m.group(2) or "").strip()
            slug = resolve(slugify(target)) or slugify(target)
            return f"[{label or target}](/{slug})"

        return md.render(_WIKILINK.sub(sub, markdown or ""))

    return render


def build(src: Path, out: Path, waikiki_path: str | None = None) -> int:
    pages = []
    for path in page_files(src):
        meta, tags, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        pages.append(
            {
                "slug": path.stem,
                "title": meta.get("title") or path.stem.replace("-", " ").title(),
                "parent": meta.get("parent"),
                "tags": tags,
                "markdown": path.read_text(encoding="utf-8"),
                "body": body,
            }
        )
    if not pages:
        raise SystemExit(f"no markdown pages found in {src}")

    index = {}
    for p in pages:
        index[p["slug"]] = p["slug"]
        index[slugify(p["title"])] = p["slug"]
    render = load_renderer(waikiki_path)

    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(out)
    conn.executescript(SCHEMA)

    for key, value in (
        ("title", "VerinFast v2"),
        (
            "description",
            "Features, goals and requirements for the VerinFast v2 rewrite",
        ),
        ("allow_html", "0"),
        ("home_slug", "verinfast-v2"),
    ):
        conn.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (key, value)
        )

    ids = {}
    for p in pages:
        # Waikiki renders the frontmatter as an infobox, so the body alone is
        # what becomes HTML — the markdown column keeps the frontmatter.
        html = render(p["body"], index.get)
        cur = conn.execute(
            "INSERT INTO pages(slug, title, markdown, html) VALUES (?,?,?,?)",
            (p["slug"], p["title"], p["markdown"], html),
        )
        ids[p["slug"]] = cur.lastrowid

    for p in pages:
        if p["parent"]:
            parent_id = ids.get(p["parent"])
            if parent_id is None:
                print(
                    f"  ! {p['slug']}: unknown parent {p['parent']!r}", file=sys.stderr
                )
                continue
            conn.execute(
                "UPDATE pages SET parent_id=? WHERE id=?", (parent_id, ids[p["slug"]])
            )
        for tag in p["tags"]:
            conn.execute(
                "INSERT OR IGNORE INTO page_tags(page_id, tag) VALUES (?,?)",
                (ids[p["slug"]], tag),
            )

    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    return len(pages)


def check_links(src: Path) -> list[str]:
    """Every [[Wikilink]] must resolve to a page in this wiki."""
    titles, slugs = {}, set()
    for path in page_files(src):
        meta, _tags, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
        slugs.add(path.stem)
        titles[slugify(meta.get("title") or path.stem)] = path.stem
    broken = []
    for path in page_files(src):
        for m in _WIKILINK.finditer(path.read_text(encoding="utf-8")):
            target = slugify(m.group(1).strip())
            if target not in titles and target not in slugs:
                broken.append(f"{path.name}: [[{m.group(1).strip()}]]")
    return broken


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-s", "--src", default=str(WIKI_SRC), help="directory of markdown pages"
    )
    ap.add_argument("-o", "--out", default=str(HERE / "VerinFast-v2.wiki"))
    ap.add_argument("--waikiki", help="path to a waikiki checkout, for its renderer")
    ap.add_argument("--check-only", action="store_true", help="only validate wikilinks")
    args = ap.parse_args()

    src = Path(args.src)
    broken = check_links(src)
    for b in broken:
        print(f"  ! broken wikilink → {b}", file=sys.stderr)
    if args.check_only:
        raise SystemExit(1 if broken else 0)

    out = Path(args.out)
    count = build(src, out, args.waikiki)
    print(
        f"wrote {out} — {count} pages, {out.stat().st_size // 1024} KiB"
        f"{f', {len(broken)} broken link(s)' if broken else ''}"
    )


if __name__ == "__main__":
    main()
