"""DOC-READ CLI — ingest a PDF into chunks (A) and build its 「本の地図」(B).

Usage:
  doc-read ingest "H:\\path\\book.pdf"      # A: chunk + index
  doc-read map <doc_id>                       # B: summarize → map.md (needs LM Studio)
  doc-read show <doc_id>                      # print map.md / meta
  doc-read list                              # list ingested docs
"""

from __future__ import annotations

import argparse
import asyncio
import json

from presence_ui.services import doc_read


def cmd_ingest(*, path: str, as_json: bool) -> int:
    meta, chunks = doc_read.ingest_pdf(path)
    if as_json:
        print(json.dumps({"meta": meta.__dict__, "chunk_count": len(chunks)}, ensure_ascii=False))
        return 0
    print(f"doc_id={meta.doc_id}  {meta.page_count}p / {meta.total_chars}字 / {len(chunks)} chunk")
    for chunk in chunks:
        label = chunk.heading if chunk.part == 0 else f"{chunk.heading}（{chunk.part}）"
        print(f"  [{chunk.chunk_id:2}] p{chunk.page_start + 1}-{chunk.page_end + 1}  "
              f"{chunk.char_count:5}字  {label}")
    print(f"\nstore: {doc_read.doc_dir(meta.doc_id)}")
    print(f"next : doc-read map {meta.doc_id}")
    return 0


def cmd_map(*, doc_id: str) -> int:
    body = asyncio.run(doc_read.build_map(doc_id))
    print(body)
    print(f"\nsaved: {doc_read.map_path(doc_id)}")
    return 0


def cmd_show(*, doc_id: str) -> int:
    path = doc_read.map_path(doc_id)
    if path.is_file():
        print(path.read_text(encoding="utf-8"))
        return 0
    meta = doc_read.load_meta(doc_id)
    if meta is None:
        print(f"not found: {doc_id}")
        return 1
    print(json.dumps(meta.__dict__, ensure_ascii=False, indent=2))
    print("(map not built yet — run: doc-read map " + doc_id + ")")
    return 0


def cmd_list() -> int:
    root = doc_read.doc_store_dir()
    if not root.is_dir():
        print(f"(no docs) {root}")
        return 0
    active = doc_read.active_doc_id()
    titles = {e.doc_id: e for e in doc_read.list_registry()}
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        meta = doc_read.load_meta(child.name)
        if meta is None:
            continue
        built = "map✓" if doc_read.map_path(meta.doc_id).is_file() else "map–"
        entry = titles.get(meta.doc_id)
        title = entry.title if entry and entry.title else meta.title
        alias = f"  aliases={entry.aliases}" if entry and entry.aliases else ""
        star = "*" if meta.doc_id == active else " "
        print(f"{star}{meta.doc_id}  {built}  {title}  ({meta.page_count}p){alias}")
    return 0


def cmd_activate(*, doc_id: str) -> int:
    if doc_read.load_meta(doc_id) is None:
        print(f"not found: {doc_id}")
        return 1
    doc_read.set_active_doc(doc_id)
    print(f"active book = {doc_id}")
    return 0


def cmd_title(*, doc_id: str, title: str, aliases: list[str]) -> int:
    if doc_read.load_meta(doc_id) is None:
        print(f"not found: {doc_id}")
        return 1
    doc_read.set_doc_title(doc_id, title, aliases=aliases or None)
    print(f"{doc_id}: title={title!r} aliases={aliases}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DOC-READ — PDF ingest + book map")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command")

    ingest = sub.add_parser("ingest", help="A: chunk + index a PDF")
    ingest.add_argument("path", help="path to the PDF")

    mp = sub.add_parser("map", help="B: summarize chunks → map.md (needs LM Studio)")
    mp.add_argument("doc_id")

    show = sub.add_parser("show", help="print map.md / meta")
    show.add_argument("doc_id")

    sub.add_parser("list", help="list ingested docs")

    activate = sub.add_parser("activate", help="set the active book (fallback for cue)")
    activate.add_argument("doc_id")

    title = sub.add_parser("title", help="set a human title + aliases for '〇〇の本' resolution")
    title.add_argument("doc_id")
    title.add_argument("title")
    title.add_argument("--alias", action="append", default=[], help="repeatable alias")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ingest":
        return cmd_ingest(path=args.path, as_json=args.json)
    if args.command == "map":
        return cmd_map(doc_id=args.doc_id)
    if args.command == "show":
        return cmd_show(doc_id=args.doc_id)
    if args.command == "list":
        return cmd_list()
    if args.command == "activate":
        return cmd_activate(doc_id=args.doc_id)
    if args.command == "title":
        return cmd_title(doc_id=args.doc_id, title=args.title, aliases=args.alias)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
