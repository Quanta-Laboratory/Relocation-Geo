#!/usr/bin/env python3
"""
Build the activity dataset for the Small Business Status checker.

INPUT   the official Geostat classifier SEC 006-2016 (NACE Rev. 2), PDF:
        https://www.geostat.ge/media/70150/NACE-Rev_2_GE_2023.pdf
OUTPUT  src/data/activity-classifier.json

WHY THIS SCRIPT EXISTS
----------------------
The classifier holds 613 classes and 697 Georgian sub-classes — 1310 addressable
codes. Hand-curating that is neither possible nor honest. This script parses the
official PDF, applies a RULE LAYER derived from Annex 4 to Government Ordinance
No 415, and marks everything it has not positively assessed as "unreviewed".

THE POINT OF "unreviewed"
-------------------------
Law does not classify by code. Annex 4 lists seven categories in words. Mapping
codes onto them is interpretation. So the dataset has FOUR verdicts, and the
default is not "clear":

  prohibited  a rule maps this code onto an Annex 4 category with little room
  grey        the code's own name contains "consulting" (the Annex 4 trap), or a
              rule flags it as licence-dependent
  clear       a human actually looked at this code (the curated set)
  unreviewed  we have not assessed it — the tool says so, and sends the user to
              the seven categories and the Revenue Service

Marking 1250 unreviewed codes "clear" by default would produce a tool that is
confidently wrong most of the time. That is the failure this file prevents.

USAGE
  python scripts/build_activity_dataset.py --pdf "/path/to/NACE-Rev_2_GE_2023.pdf"
  python scripts/build_activity_dataset.py --pdf ... --translate   # fills English names
                                                                   # (needs ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "data" / "activity-classifier.json"
CURATED = ROOT / "src" / "data" / "small-business-activity-data.ts"

# --------------------------------------------------------------------------- #
# The rule layer. Every entry traces back to a numbered category of Annex 4.
# Keep this table small, explicit and auditable — it is the legal heart of the
# tool and someone should be able to check it against the ordinance line by line.
# --------------------------------------------------------------------------- #

# Whole divisions (2-digit) that fall inside a prohibited category.
PROHIBITED_DIVISIONS: dict[str, tuple[int, str]] = {
    "11": (7, "Manufacture of beverages — excisable goods."),
    "12": (7, "Manufacture of tobacco products — excisable goods."),
    "64": (1, "Financial service activities — licensed, and engage currency operations."),
    "65": (1, "Insurance and pension funding — licensed activity."),
    "66": (3, "Activities auxiliary to financial services — currency operations and licensed."),
    "78": (6, "Employment activities — this is 'provision of personnel'."),
    "86": (4, "Human health activities — medical activity is named in Annex 4, and is licensed."),
    "92": (5, "Gambling and betting activities — named in Annex 4."),
}

# Individual classes that fall inside a prohibited category.
PROHIBITED_CLASSES: dict[str, tuple[int, str]] = {
    "19.20": (7, "Manufacture of refined petroleum products — excisable goods."),
    "69.10": (4, "Legal activities — advocacy and notarial work are named in Annex 4."),
    "69.20": (4, "Accounting, bookkeeping, auditing and tax consultancy — auditing and tax consulting are both named in Annex 4."),
    "70.22": (4, "Management consultancy — consulting is named in Annex 4."),
    "71.11": (4, "Architectural activities — named in Annex 4."),
}

# Classes/divisions we flag as grey because they sit on a boundary.
GREY_DIVISIONS: dict[str, str] = {
    "75": "Veterinary activities are licensed, and sit close to the 'medical' category. Confirm.",
}
GREY_CLASSES: dict[str, str] = {
    "70.10": "Head office activities shade into management consultancy (70.22), which is prohibited. Confirm which you actually do.",
    "71.12": "Engineering activities are bundled with technical consultancy in this code. Execution and advice may be treated differently.",
    "49.32": "Taxi operation needs a permit, which normally triggers Annex 4 item 1 — but the M1 taxi permit for the capital is carved out. Depends on your permit and city.",
}

# Georgian stems that mean "consulting". Annex 4 prohibits consulting, so any code
# whose own official name contains one of these is, at minimum, a question.
CONSULTING_STEMS = ["საკონსულტაციო", "კონსულტირება", "კონსულტაცი"]

CATEGORY_LABELS = {
    1: "Requires a licence or permit",
    2: "Requires significant investment (excisable goods)",
    3: "Foreign-currency operations",
    4: "Medical, architectural, legal/notarial, auditing or consulting",
    5: "Gambling business",
    6: "Provision of personnel (staffing)",
    7: "Manufacture of excisable goods",
}


def extract_text(pdf_path: Path) -> str:
    try:
        import pypdf
    except ImportError:
        sys.exit("pip install pypdf")
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


CLASS_RE = re.compile(r"^\s*(\d{2}\.\d{2})\s+(\S.*)$")
SUB_RE = re.compile(r"^\s*(\d{2}\.\d{2}\.\d)\s+(\S.*)$")


def clean_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s*\.{3,}.*$", "", s)          # table-of-contents dot leaders
    s = re.sub(r"^[–-]\s*კლასი\s*„?", "", s)     # "– კლასი „..."
    s = s.strip(' „”"')
    return re.sub(r"\s+", " ", s).strip()


def parse(text: str) -> dict[str, dict]:
    """Return {code: {code, level, name_ka}} for classes and sub-classes."""
    found: dict[str, dict] = {}
    for line in text.split("\n"):
        m = SUB_RE.match(line)
        if m:
            code, name = m.group(1), clean_name(m.group(2))
            if len(name) < 3:
                continue
            # first sighting wins: the body text precedes the cross-references
            found.setdefault(code, {"code": code, "level": "subclass", "name_ka": name})
            continue
        m = CLASS_RE.match(line)
        if m:
            code, name = m.group(1), clean_name(m.group(2))
            if len(name) < 3:
                continue
            found.setdefault(code, {"code": code, "level": "class", "name_ka": name})
    return found


def classify(code: str, name_ka: str) -> dict:
    """Apply the rule layer. Default is 'unreviewed' — never 'clear'."""
    division = code.split(".")[0]
    cls = ".".join(code.split(".")[:2])

    if division in PROHIBITED_DIVISIONS:
        cat, why = PROHIBITED_DIVISIONS[division]
        return {"verdict": "prohibited", "category": cat, "rule": why}
    if cls in PROHIBITED_CLASSES:
        cat, why = PROHIBITED_CLASSES[cls]
        return {"verdict": "prohibited", "category": cat, "rule": why}

    low = name_ka.lower()
    if any(stem in low for stem in CONSULTING_STEMS):
        return {
            "verdict": "grey",
            "category": 4,
            "rule": "The official name of this code contains 'consulting'. Annex 4 prohibits consulting, so this needs confirming before you rely on the regime.",
        }

    if division in GREY_DIVISIONS:
        return {"verdict": "grey", "category": 1, "rule": GREY_DIVISIONS[division]}
    if cls in GREY_CLASSES:
        return {"verdict": "grey", "category": 1, "rule": GREY_CLASSES[cls]}

    return {"verdict": "unreviewed", "rule": None}


def curated_entries() -> dict[str, dict]:
    """The hand-assessed set. A human looked at these, so their verdict WINS over
    the rule layer — including the only way a code can ever become 'clear'."""
    if not CURATED.exists():
        return {}
    src = CURATED.read_text(encoding="utf-8")
    # Each entry looks like: { code: "62.01", name: "...", verdict: "clear", ... }
    blocks = re.findall(r"\{\s*code:\s*\"([\d.]+)\",(.*?)\},", src, re.DOTALL)
    out: dict[str, dict] = {}
    for code, body in blocks:
        def field(nm: str) -> str | None:
            m = re.search(rf'{nm}:\s*"((?:[^"\\]|\\.)*)"', body, re.DOTALL)
            return m.group(1).replace('\\"', '"').replace("\n", " ") if m else None

        verdict = field("verdict")
        if verdict not in ("prohibited", "grey", "clear"):
            continue
        cat = re.search(r"category:\s*(\d+)", body)
        entry = {
            "verdict": verdict,
            "note": re.sub(r"\s+", " ", (field("note") or "")).strip(),
            "name_en_curated": field("name"),
        }
        if cat:
            entry["category"] = int(cat.group(1))
        iw = field("incomeWarning")
        if iw:
            entry["income_warning"] = re.sub(r"\s+", " ", iw).strip()
        out[code] = entry
    return out


def translate(entries: list[dict]) -> None:
    """Fill name_en via the Claude API, in batches. Idempotent: skips what exists."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        sys.exit("--translate needs ANTHROPIC_API_KEY in the environment")
    import urllib.request

    todo = [e for e in entries if not e.get("name_en")]
    print(f"translating {len(todo)} names…")
    BATCH = 40
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        listing = "\n".join(f"{e['code']}\t{e['name_ka']}" for e in chunk)
        prompt = (
            "These are official Georgian statistical classifier names for economic "
            "activities (SEC 006-2016, which mirrors NACE Rev. 2). Translate each into "
            "its standard ENGLISH NACE Rev. 2 wording where one exists, otherwise a "
            "faithful plain-English translation.\n\n"
            "Return STRICT JSON only: {\"CODE\": \"English name\", ...}\n\n" + listing
        )
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(
                {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ).encode(),
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
            mapping = json.loads(text)
            by_code = {e["code"]: e for e in chunk}
            for code, en in mapping.items():
                if code in by_code and isinstance(en, str):
                    by_code[code]["name_en"] = en.strip()
            print(f"  {i + len(chunk)}/{len(todo)}", flush=True)
        except Exception as exc:  # keep going; untranslated names stay Georgian
            print(f"  WARN batch {i}: {exc}", file=sys.stderr)
        time.sleep(0.5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--translate", action="store_true")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    if not pdf.exists():
        sys.exit(f"not found: {pdf}")

    print("extracting text…")
    text = extract_text(pdf)
    parsed = parse(text)
    print(f"parsed {len(parsed)} codes")

    keep = curated_entries()
    existing = {}
    if OUT.exists():
        existing = {e["code"]: e for e in json.loads(OUT.read_text(encoding="utf-8"))["activities"]}

    entries: list[dict] = []
    for code in sorted(parsed):
        e = dict(parsed[code])
        ruled = classify(code, e["name_ka"])
        e.update(ruled)

        cur = keep.get(code)
        if cur:
            # A human assessed this code. Their verdict overrides the rule layer —
            # but we KEEP what the rule thought, so any disagreement stays visible
            # instead of being silently swallowed.
            if cur["verdict"] != ruled["verdict"]:
                e["rule_said"] = ruled["verdict"]
            e["verdict"] = cur["verdict"]
            e["curated"] = True
            if cur.get("note"):
                e["note"] = cur["note"]
            if cur.get("category"):
                e["category"] = cur["category"]
            if cur.get("income_warning"):
                e["income_warning"] = cur["income_warning"]
            if cur.get("name_en_curated"):
                e["name_en"] = cur["name_en_curated"]

        prev = existing.get(code, {})
        if prev.get("name_en") and not e.get("name_en"):
            e["name_en"] = prev["name_en"]
        entries.append(e)

    missing = sorted(set(keep) - set(parsed))
    if missing:
        print(f"  NOTE: curated codes not present in the classifier: {missing}")

    if args.translate:
        translate(entries)

    counts: dict[str, int] = {}
    for e in entries:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1

    payload = {
        "source": "Geostat SEC 006-2016 (NACE Rev. 2), official PDF",
        "source_url": "https://www.geostat.ge/media/70150/NACE-Rev_2_GE_2023.pdf",
        "rule_basis": "Annex 4 to Government Ordinance No 415 of 29 December 2010",
        "categories": CATEGORY_LABELS,
        "counts": counts,
        "activities": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"wrote {OUT.relative_to(ROOT)}")
    for v in ("prohibited", "grey", "clear", "unreviewed"):
        print(f"  {v:11} {counts.get(v, 0)}")
    print(f"  curated (human-assessed): {sum(1 for e in entries if e.get('curated'))}")
    translated = sum(1 for e in entries if e.get("name_en"))
    print(f"  with English names: {translated}/{len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
