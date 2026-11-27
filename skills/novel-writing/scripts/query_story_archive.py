"""Find and read selected rows from a Markdown story archive without dumping it."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


KINDS = {
    "coverage": ("归档覆盖",),
    "rule": ("已确认设定",),
    "person": ("人物索引", "人物与信息"),
    "state": ("人物状态",),
    "event": ("关键事件", "时间线与状态"),
    "thread": ("伏笔",),
    "dependency": ("后文依赖",),
    "pending": ("待确认",),
}
EVENT_ID = re.compile(r"E-[0-9]+", re.IGNORECASE | re.ASCII)
POSITION = re.compile(r"([0-9]+)(?:\.([0-9]+))?", re.ASCII)
CHAPTER_LABEL = re.compile(r"第([0-9]+)章(?:\s*第([0-9]+)场)?")
DIGEST = re.compile(r"[0-9a-f]{64}", re.IGNORECASE | re.ASCII)
SEPARATOR = re.compile(r":?-{3,}:?")


@dataclass(frozen=True)
class Row:
    line: int
    kind: str
    cells: tuple[str, ...]

    @property
    def event_id(self):
        first = self.cells[0].strip("`")
        return first.upper() if self.kind == "event" and EVENT_ID.fullmatch(first) else None


def table_cells(line):
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return ()
    return tuple(cell.strip() for cell in re.split(r"(?<!\\)\|", line[1:-1]))


def rows_from(lines):
    kind = None
    width = 0
    fence = None
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        marker = re.match(r"`{3,}|~{3,}", stripped)
        if fence:
            if marker and marker[0].startswith(fence) and not stripped[marker.end():].strip():
                fence = None
            continue
        if marker:
            fence = marker[0]
            width = 0
            continue
        if heading := re.match(r"#{1,6}\s+(.+)", stripped):
            kind = next(
                (name for name, prefixes in KINDS.items() if heading[1].startswith(prefixes)),
                None,
            )
            width = 0
            continue
        if kind is None:
            continue
        cells = table_cells(line)
        if not cells:
            width = 0
            continue
        if all(SEPARATOR.fullmatch(cell) for cell in cells):
            header = table_cells(lines[index - 1]) if index else ()
            width = len(cells) if len(header) == len(cells) else 0
            continue
        if width and len(cells) == width:
            following = table_cells(lines[index + 1]) if index + 1 < len(lines) else ()
            if len(following) == len(cells) and all(SEPARATOR.fullmatch(cell) for cell in following):
                continue
            yield Row(index + 1, kind, cells)


def clip(text, start=0, width=96):
    stop = start + width
    return ("\u2026" if start else "") + text[start:stop] + ("\u2026" if stop < len(text) else "")


def find(rows, terms, kinds, limit):
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        hits = []
        for row in rows:
            if row.kind not in kinds:
                continue
            text = " | ".join(row.cells)
            match = pattern.search(text)
            if match:
                hits.append((row, text, match.start()))
        hits.sort(key=lambda hit: (
            not bool(pattern.search(hit[0].cells[0])),
            hit[0].kind != "event",
            hit[0].line,
        ))
        print(f"{term}: {len(hits)} match(es); showing {min(limit, len(hits))}")
        for row, text, start in hits[:limit]:
            print(f"L{row.line} [{row.event_id or row.kind}] {clip(text, max(0, start - 24))}")


def overview(lines, rows):
    # Metadata is kept separate from the fingerprint table and plot summaries.
    for line in lines[:10]:
        if line.startswith("## "):
            break
        if line.startswith("# ") or any(label in line for label in ("分支", "维护方式")):
            print(clip(line, width=120))
    sources = [row for row in rows if row.kind == "coverage"]
    print(f"coverage rows: {len(sources)} (not a guarantee of completeness)")
    if sources:
        print(f"first/last labels: {clip(sources[0].cells[0], width=48)} / "
              f"{clip(sources[-1].cells[0], width=48)}")


def read(rows, events, line_numbers, paths):
    hit = False
    missing = False
    for eid in dict.fromkeys(event.upper() for event in events):
        matches = [row for row in rows if row.event_id == eid]
        if len(matches) != 1:
            print(f"{eid}: {'ambiguous' if matches else 'not found'}")
            missing = True
        else:
            row = matches[0]
            print(f"L{row.line} [{row.event_id}] {' | '.join(row.cells[1:])}")
            hit = True
    for number in dict.fromkeys(line_numbers):
        row = next((item for item in rows if item.line == number and item.kind != "coverage"), None)
        if row is None:
            print(f"L{number}: not a selectable record")
            missing = True
        else:
            print(f"L{row.line} [{row.kind}] {' | '.join(row.cells)}")
            hit = True
    for path in dict.fromkeys(source.replace("\\", "/") for source in paths):
        matches = [
            row for row in rows
            if row.kind == "coverage" and len(row.cells) >= 3
            and row.cells[1].strip("`").replace("\\", "/") == path
        ]
        if len(matches) != 1:
            print(f"{path}: {'ambiguous' if matches else 'not found'}")
            missing = True
            continue
        row = matches[0]
        digest = row.cells[2].strip("`")
        if not DIGEST.fullmatch(digest):
            print(f"{path}: no recorded SHA-256")
            missing = True
        else:
            note = f" | {row.cells[3]}" if len(row.cells) > 3 and row.cells[3] else ""
            print(f"{path} {digest.lower()}{note}")
            hit = True
    return int(missing or not hit)


def position(text):
    label = text.strip("`")
    match = POSITION.fullmatch(label) or CHAPTER_LABEL.fullmatch(label)
    if not match:
        return None
    chapter, scene = match.groups()
    if len(chapter) > 9 or (scene is not None and len(scene) > 9):
        return None
    chapter, scene = int(chapter), None if scene is None else int(scene)
    return (chapter, scene) if chapter > 0 and scene != 0 else None


def state(rows, person, item, before):
    chapter, scene = before
    eligible = []
    unresolved = []
    for row in rows:
        if row.kind != "state" or len(row.cells) < 3:
            continue
        name, when, field = (cell.strip("`") for cell in row.cells[:3])
        if (name, field) != (person, item):
            continue
        point = position(when)
        if point is None:
            unresolved.append(row.line)
            continue
        change_chapter, change_scene = point
        if change_chapter == chapter and scene is not None and change_scene is None:
            unresolved.append(row.line)
        elif change_chapter < chapter or (
            change_chapter == chapter and scene is not None and change_scene < scene
        ):
            if len(row.cells) != 5 or not all(row.cells[3:]):
                unresolved.append(row.line)
            else:
                eligible.append((point, row))
    if unresolved:
        lines = ", ".join(f"L{line}" for line in unresolved[:8])
        print(f"Cannot resolve state from archive: {len(unresolved)} incomplete or unordered "
              f"row(s), {lines}; verify the source.")
        return 1
    if not eligible:
        print("No recorded state strictly before the requested position.")
        return 1
    last_chapter = max(point[0] for point, _ in eligible)
    latest = [(point[1], row) for point, row in eligible if point[0] == last_chapter]
    # An unspecified scene may come before or after any numbered scene in that chapter.
    if all(scene is not None for scene, _ in latest):
        last_scene = max(scene for scene, _ in latest)
        latest = [(scene, row) for scene, row in latest if scene == last_scene]
    if len(latest) != 1:
        print("Ambiguous latest state; verify the source instead of choosing by archive order.")
        return 1
    _, row = latest[0]
    print(f"L{row.line} [state] {' | '.join(row.cells)}")
    return 0


def impact(rows, event, limit, offset):
    matches = []
    for row in rows:
        if row.kind != "dependency" or row.cells[0].strip("`").upper() != event:
            continue
        point = position(row.cells[1]) if len(row.cells) == 4 else None
        if point is None or not all(row.cells[2:]):
            print(f"{event}: incomplete or unordered dependency at L{row.line}; verify the archive.")
            return 1
        chapter, scene = point
        matches.append((chapter, scene or 0, row.line, row))
    matches.sort()
    print(f"{event}: {len(matches)} recorded direct dependency row(s); coverage may be incomplete.")
    page = matches[offset:offset + limit]
    for _, _, _, row in page:
        print(f"L{row.line} [dependency] {' | '.join(row.cells[1:])}")
    if offset + len(page) < len(matches):
        print(f"More recorded rows: repeat with --offset {offset + len(page)}.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("story-bible.md"))
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("overview")
    find_parser = modes.add_parser("find")
    find_parser.add_argument("--term", action="append", required=True)
    find_parser.add_argument("--kind", action="append", choices=tuple(KINDS)[1:])
    find_parser.add_argument("--limit", type=int, choices=range(1, 5), default=2)
    read_parser = modes.add_parser("read")
    read_parser.add_argument("--event", action="append", default=[])
    read_parser.add_argument("--line", action="append", type=int, default=[])
    read_parser.add_argument("--source", action="append", default=[])
    state_parser = modes.add_parser("state")
    state_parser.add_argument("--person", required=True)
    state_parser.add_argument("--item", required=True)
    state_parser.add_argument("--before", required=True, metavar="CHAPTER[.SCENE]")
    impact_parser = modes.add_parser("impact")
    impact_parser.add_argument("--event", required=True)
    impact_parser.add_argument("--limit", type=int, choices=range(1, 13), default=8)
    impact_parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    if args.mode == "find" and (
        len(args.term) > 4 or any(not term.strip() or len(term) > 48 for term in args.term)
    ):
        parser.error("provide one to four nonempty search terms, up to 48 chars each")
    if args.mode == "read" and not 1 <= len(args.event) + len(args.line) + len(args.source) <= 12:
        parser.error("select one to twelve --event, --line or --source values")
    if args.mode == "state":
        before = position(args.before)
        if before is None or not args.person.strip() or not args.item.strip():
            parser.error("provide an exact person, item and positive --before CHAPTER[.SCENE]")
    if args.mode == "impact" and (not EVENT_ID.fullmatch(args.event) or args.offset < 0):
        parser.error("provide a valid --event E-NUMBER and a nonnegative --offset")
    try:
        lines = args.archive.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as error:
        parser.exit(1, f"Cannot read the UTF-8 story archive: {error}\n")
    sys.stdout.reconfigure(encoding="utf-8")
    rows = list(rows_from(lines))
    if not rows:
        parser.exit(1, "No supported story archive table rows found; use a targeted text search.\n")
    if args.mode == "overview":
        overview(lines, rows)
    elif args.mode == "find":
        find(rows, [term.strip() for term in args.term], args.kind or ["event"], args.limit)
    elif args.mode == "read":
        return read(rows, args.event, args.line, args.source)
    elif args.mode == "state":
        return state(rows, args.person.strip(), args.item.strip(), before)
    else:
        return impact(rows, args.event.upper(), args.limit, args.offset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
