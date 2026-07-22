#!/usr/bin/env python3
"""
Vault merge + audit helpers for granola-to-obsidian-howard.

Why this is code and not prose: the merge rules have failed twice in practice
when re-derived by hand — a dropped alias silently broke three links, and a
stale `company: Unknown` survived a meeting that identified the person. Both are
invisible without a check. Encoding them here makes them enforced rather than
remembered.

Usage from a batch script:

    import sys; sys.path.insert(0, "/Users/howardgil/.claude/skills/granola-to-obsidian-howard/scripts")
    import vaultmerge as vm

    vm.person("Younes", "2026-07-01-...-summary", "2026-07-01",
              company="Mem0", role="Sales FTE", notes=["**Jul 1:** ran the CBRE demo."])
    vm.simple("Companies", "Wiser", mtg, mdate, kind="tool", desc="...")
    vm.report(vm.audit())

Field-merge rules (see SKILL.md "Merging into existing notes"):
  existing Unknown + new value  -> overwrite
  existing value   + new Unknown-> keep existing (never regress)
  both values, differ           -> keep existing, record a conflict for Phase 8
"""
import datetime
import os
import pathlib
import re

#: Vault location. Override per-machine with MEM0_VAULT; the default is where
#: Obsidian puts it on a stock install. A hardcoded path worked while one
#: machine was the only writer and breaks the moment a second person clones.
VAULT = pathlib.Path(
    os.environ.get("MEM0_VAULT", pathlib.Path.home() / "Documents" / "mem0 vault")
).expanduser()

#: Stamped into the `date:` frontmatter of every note this module creates.
#: Must be computed, not literal: under the 5-minute ingest loop a frozen
#: constant would date every future note to the day it was written.
TODAY = datetime.date.today().isoformat()

FOLDERS = ("Meetings", "People", "Concepts", "Projects", "Companies")
UNKNOWNS = ("", "unknown", "none", "n/a", "?")

#: populated by person()/simple(); surface these in Phase 8
CONFLICTS = []


# ---------------------------------------------------------------- internals

def _is_unknown(v):
    return v is None or str(v).strip().lower().split()[0].strip('"') in UNKNOWNS


def _ylist(items):
    return "".join(f'\n  - "{i}"' for i in items) if items else " []"


def _split(text):
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def _get(fm, key):
    m = re.search(rf"^{key}:\s*(.*)$", fm, re.M)
    return m.group(1).strip().strip('"') if m else None


def _set(fm, key, value):
    if re.search(rf"^{key}:", fm, re.M):
        return re.sub(rf"^{key}:.*$", f'{key}: "{value}"', fm, count=1, flags=re.M)
    return fm + f'\n{key}: "{value}"'


def _merge_field(fm, key, new, note_name):
    """Upgrade placeholder fields; never regress; record conflicts."""
    if new is None:
        return fm
    old = _get(fm, key)
    if _is_unknown(old) and not _is_unknown(new):
        return _set(fm, key, new)
    if _is_unknown(new):
        return fm                      # never regress a known value to Unknown
    if old and old.strip() != str(new).strip():
        CONFLICTS.append((note_name, key, old, new))
    return fm


def _add_related(fm, mtg):
    if f'"{mtg}"' in fm:
        return fm
    m = re.search(r"(related:)((?:\n  - .*)*)", fm)
    if not m:
        return fm + f'\nrelated:\n  - "{mtg}"'
    return fm[:m.end()] + f'\n  - "{mtg}"' + fm[m.end():]


def _add_aliases(fm, aliases):
    """Additive only — merging must never drop an existing alias."""
    for a in aliases or ():
        if f'"{a}"' in fm or re.search(rf"^\s+- {re.escape(a)}$", fm, re.M):
            continue
        m = re.search(r"(aliases:)( \[\]|(?:\n  - .*)*)", fm)
        if m and m.group(2).strip() == "[]":
            fm = fm[:m.start(2)] + f'\n  - "{a}"' + fm[m.end(2):]
        elif m:
            fm = fm[:m.end()] + f'\n  - "{a}"' + fm[m.end():]
        else:
            fm = fm + f'\naliases:\n  - "{a}"'
    return fm


def _append_notes(body, notes):
    if not notes:
        return body
    add = "\n".join(f"- {n}" for n in notes)
    existing = set(re.findall(r"^- (.*)$", body, re.M))
    add = "\n".join(l for l in add.split("\n") if l[2:] not in existing)
    if not add:
        return body
    if "## Notes" in body:
        return re.sub(r"(## Notes\n(?:- .*\n)*)", lambda m: m.group(1) + add + "\n",
                      body, count=1)
    return body.rstrip() + "\n\n## Notes\n" + add + "\n"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ------------------------------------------------------------------- public

def person(name, mtg, mdate, *, aliases=(), status=None, company=None, role=None,
           notes=(), callout=None):
    """Create or update a People/ note. Returns 'created' or 'updated'."""
    p = VAULT / "People" / f"{name}.md"
    if p.exists():
        fm, body = _split(p.read_text(encoding="utf-8"))
        fm = _add_related(fm, mtg)
        fm = _add_aliases(fm, aliases)
        fm = _merge_field(fm, "company", company, name)
        fm = _merge_field(fm, "role", role, name)
        if status == "confirmed":                       # never confirmed -> unconfirmed
            fm = re.sub(r"^status:.*$", "status: confirmed", fm, count=1, flags=re.M)
        last = _get(fm, "last-contact")
        if last and mdate > last:                       # forward only
            fm = re.sub(r"^last-contact:.*$", f"last-contact: {mdate}", fm,
                        count=1, flags=re.M)
        if f"[[{mtg}]]" not in body:
            body = body.replace("- **Mentioned in:**", f"- **Mentioned in:** [[{mtg}]],", 1)
        # keep the Context block in step with any upgraded frontmatter
        for label, key in (("Company/Org", "company"), ("Role", "role")):
            val = _get(fm, key)
            if val:
                body = re.sub(rf"^- \*\*{label}:\*\* .*$", f"- **{label}:** {val}",
                              body, count=1, flags=re.M)
        _write(p, f"---\n{fm}\n---\n{_append_notes(body, notes)}")
        return "updated"

    b = ["---", f'title: "{name}"', f"date: {TODAY}", "tags: [people]",
         f"aliases:{_ylist(aliases)}", "type: person",
         f'company: "{company or "Unknown"}"', f'role: "{role or "Unknown"}"',
         f"last-contact: {mdate}", f"status: {status or 'unconfirmed'}",
         f"related:{_ylist([mtg])}", "---", "", f"# {name}", "", "## Context",
         f"- **Company/Org:** {company or 'Unknown'}", f"- **Role:** {role or 'Unknown'}",
         f"- **Mentioned in:** [[{mtg}]]", ""]
    if (status or "unconfirmed") == "unconfirmed" and not callout:
        b += ["> [!warning] Unconfirmed identity",
              "> Referenced by first name only and never explicitly identified.",
              "> Role and company are inferred from context.", ""]
    if callout:
        head, *rest = callout.split("\n")
        b += [f"> [!note] {head}"] + ["> " + l.lstrip("> ") for l in rest] + [""]
    b += ["## Notes"] + [f"- {n}" for n in notes] + ["", "## Key Quotes", "",
                                                      "## Action Items", ""]
    _write(p, "\n".join(b))
    return "created"


def simple(folder, name, mtg, mdate, *, aliases=(), kind=None, desc=None,
           what=None, why=None, by=None):
    """Create or update a Concepts/ Projects/ Companies/ note."""
    p = VAULT / folder / f"{name}.md"
    if p.exists():
        fm, body = _split(p.read_text(encoding="utf-8"))
        fm = _add_related(fm, mtg)
        fm = _add_aliases(fm, aliases)
        if desc and desc not in body:
            body = body.rstrip() + f"\n\n### From [[{mtg}]]\n{desc}\n"
        if f"- [[{mtg}]]" not in body:
            body = body.rstrip() + f"\n- [[{mtg}]]\n"
        _write(p, f"---\n{fm}\n---\n{body}")
        return "updated"

    if folder == "Concepts":
        b = ["---", f'title: "{name}"', f"date: {TODAY}", "tags: [concept]",
             "type: concept", "status: active", f"related:{_ylist([mtg])}", "---", "",
             f"# {name}", "", "## What is it?", what or "", "", "## Why it matters",
             why or "", "", "## Connections", f"- [[{mtg}]]",
             f"- Articulated by: {by}" if by else "", "", "## Sources / References",
             f"- [[{mtg}]] — extracted from meeting on {mdate}", ""]
    elif folder == "Projects":
        b = ["---", f'title: "{name}"', f"date: {TODAY}", "tags: [project]",
             "type: project", "status: active", f"started: {mdate}",
             f"related:{_ylist([mtg])}", "---", "", f"# {name}", "", desc or "", "",
             "## Sources", f"- [[{mtg}]] — {mdate}", ""]
    else:
        b = ["---", f'title: "{name}"', f"date: {TODAY}", f"tags: [{kind or 'company'}]",
             f"aliases:{_ylist(aliases)}", f"type: {kind or 'company'}", "status: active",
             f"related:{_ylist([mtg])}", "---", "", f"# {name}", "", desc or "", "",
             "## Sources", f"- [[{mtg}]]", ""]
    _write(p, "\n".join(b))
    return "created"


# ---------------------------------------------------------- resolution queue

def _notes_bullets(body):
    """The bullets under '## Notes' — the evidence a human needs to resolve."""
    m = re.search(r"^## Notes\n((?:- .*\n)*)", body, re.M)
    return re.findall(r"^- (.*)$", m.group(1), re.M) if m else []


def queue():
    """Every People/Companies note needing human resolution, as gap dicts.

    Deliberately broader than audit()'s stale-stub check: a single-meeting
    stub is invisible to audit() but still a gap a human must clear. One
    entry per note; 'kind' lists every reason it is queued.
    """
    gaps = []
    for folder in ("People", "Companies"):
        d = VAULT / folder
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            fm, body = _split(p.read_text(encoding="utf-8"))
            kind, fields = [], []
            if _get(fm, "status") == "unconfirmed":
                kind.append("unconfirmed-status")
            for key in ("company", "role"):
                v = _get(fm, key)
                if v is not None and (not v.strip() or _is_unknown(v)):
                    fields.append(key)
            if fields:
                kind.append("unknown-field")
            if kind:
                gaps.append({"path": str(p), "name": p.stem, "kind": kind,
                             "fields": fields, "evidence": _notes_bullets(body)})
    return gaps


def report_queue(gaps):
    """Print a queue human-readably. Returns True if the queue is empty."""
    if not gaps:
        print("QUEUE EMPTY")
        return True
    print(f"QUEUE: {len(gaps)} note(s) need human resolution")
    for g in gaps:
        line = f"  {g['name']} [{', '.join(g['kind'])}]"
        if g["fields"]:
            line += f" — unknown: {', '.join(g['fields'])}"
        print(line)
        print(f"    path: {g['path']}")
        for e in g["evidence"]:
            print(f"    | {e}")
    return False


# -------------------------------------------------------------------- audit

def _known_names():
    """Every note stem plus every declared alias, lowercased."""
    names = set()
    for p in VAULT.rglob("*.md"):
        names.add(p.stem.lower())
        fm, _ = _split(p.read_text(encoding="utf-8"))
        block = re.search(r"aliases:((?:\n\s+- .*)*)", fm)
        if block:
            for a in re.findall(r"-\s*\"?([^\"\n]+?)\"?\s*$", block.group(1), re.M):
                names.add(a.strip().lower())
    return names


def audit():
    """Run every consistency check. Returns a dict; feed to report()."""
    known = _known_names()

    links = {}
    for p in VAULT.rglob("*.md"):
        for raw in re.findall(r"\[\[([^\]|#]+)", p.read_text(encoding="utf-8")):
            links.setdefault(raw.strip(), []).append(p.name)
    broken = {k: v for k, v in links.items() if k.lower() not in known}

    stale = []
    for p in (VAULT / "People").glob("*.md"):
        fm, _ = _split(p.read_text(encoding="utf-8"))
        n_meetings = len(re.findall(r"^  - .*summary", fm, re.M))
        if n_meetings > 1 and (_is_unknown(_get(fm, "company")) or
                               _is_unknown(_get(fm, "role"))):
            stale.append((p.stem, n_meetings))

    raw_speakers = {}
    tdir = VAULT / "Meetings" / "transcripts"
    if tdir.exists():
        for p in tdir.glob("*.md"):
            n = len(re.findall(r"^Speaker [A-Z]:", p.read_text(encoding="utf-8"), re.M))
            if n:
                raw_speakers[p.name] = n

    mismatched = []
    for p in VAULT.rglob("*.md"):
        fm, _ = _split(p.read_text(encoding="utf-8"))
        title = _get(fm, "title")
        if title and title != p.stem and not title.startswith("Summary:"):
            mismatched.append((p.stem, title))

    return {"total_links": len(links), "broken": broken, "stale_stubs": stale,
            "raw_speakers": raw_speakers, "title_mismatch": mismatched,
            "conflicts": list(CONFLICTS),
            "counts": {f: len(list((VAULT / f).glob("*.md")))
                       for f in FOLDERS if (VAULT / f).exists()}}


def report(a):
    """Print an audit. Returns True if the vault is clean."""
    ok = True
    print("counts:", " ".join(f"{k}={v}" for k, v in a["counts"].items()))
    print(f"links: {a['total_links']} distinct | "
          f"resolve {a['total_links'] - len(a['broken'])} | broken {len(a['broken'])}")
    for k, files in a["broken"].items():
        ok = False
        print(f"  BROKEN [[{k}]] <- {', '.join(sorted(set(files))[:3])}")
    for name, n in a["stale_stubs"]:
        ok = False
        print(f"  STALE STUB {name}: in {n} meetings but company/role still Unknown")
    for f, n in a["raw_speakers"].items():
        ok = False
        print(f"  UNRESOLVED {n} raw 'Speaker X:' labels in {f}")
    for stem, title in a["title_mismatch"]:
        ok = False
        print(f"  TITLE MISMATCH file '{stem}' vs title '{title}'")
    for note, key, old, new in a["conflicts"]:
        ok = False
        print(f"  CONFLICT {note}.{key}: kept '{old}', new meeting said '{new}' "
              f"-> raise in Phase 8")
    print("CLEAN" if ok else "ISSUES ABOVE")
    return ok


if __name__ == "__main__":
    import sys
    if "--queue" in sys.argv[1:]:
        # exit 3, not 1, so callers can tell "gaps to resolve" from a failed audit
        raise SystemExit(0 if report_queue(queue()) else 3)
    raise SystemExit(0 if report(audit()) else 1)
