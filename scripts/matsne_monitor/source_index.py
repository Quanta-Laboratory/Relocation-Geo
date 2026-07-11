#!/usr/bin/env python3
"""Build a reverse index: matsne document id -> pages that cite it.

Pure local scan, no network. Walks the content collection and data/pages,
extracts every matsne document/view/<id> reference, and records which pages
depend on it together with each page's freshness dates (reviewed / checked).

Output: scripts/matsne_monitor/source_index.json

This file is the "impact map" for the redaction probe: when a law changes,
the probe looks it up here to know exactly which pages are affected.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (relocation-ge/)
SRC = ROOT / "src"
OUT = Path(__file__).resolve().parent / "source_index.json"

DOC_RE = re.compile(r"matsne\.gov\.ge/[a-z]{2}/document/view/(\d+)")
# Minimal front-matter field extraction (avoids a YAML dependency).
FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _field(fm: str, name: str) -> str | None:
    m = re.search(rf"^{name}:\s*(.+?)\s*$", fm, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def scan_file(path: Path) -> tuple[dict, set[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    ids = set(DOC_RE.findall(text))
    meta: dict = {"path": str(path.relative_to(SRC))}
    fm_match = FM_RE.match(text)
    if fm_match:
        fm = fm_match.group(1)
        meta["title"] = _field(fm, "title")
        meta["reviewed"] = _field(fm, "reviewed")
        meta["checked"] = _field(fm, "checked")
        meta["lang"] = _field(fm, "lang")
    return meta, ids


def main() -> None:
    index: dict[str, list[dict]] = {}
    pages_scanned = 0
    for base in ("content", "data", "pages"):
        root = SRC / base
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() not in (".md", ".mdx", ".ts", ".astro"):
                continue
            meta, ids = scan_file(path)
            if not ids:
                continue
            pages_scanned += 1
            for doc_id in ids:
                index.setdefault(doc_id, [])
                # de-dupe by path
                if not any(e["path"] == meta["path"] for e in index[doc_id]):
                    index[doc_id].append(meta)

    # Sort: docs by citing-count desc, then id; pages by path.
    ordered = {}
    for doc_id in sorted(index, key=lambda d: (-len(index[d]), d)):
        ordered[doc_id] = sorted(index[doc_id], key=lambda e: e["path"])

    payload = {
        "generated_from": "src/{content,data,pages}",
        "doc_count": len(ordered),
        "index": ordered,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scanned files with refs: {pages_scanned}")
    print(f"Tracked documents: {len(ordered)}")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
