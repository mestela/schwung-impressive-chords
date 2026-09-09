#!/usr/bin/env python3
"""Import the 100 factory chord sets from Roland's J-6 online manual."""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


SOURCE_URL = "https://static.roland.com/manuals/J-6_manual_v102/eng/28645807.html"
NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
PITCH_CLASSES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            text = html.unescape(data).strip()
            if text:
                self._cell.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("th", "td") and self._cell is not None and self._row is not None:
            self._row.append("\n".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def note_to_midi(note: str) -> int:
    match = NOTE_RE.fullmatch(note.strip())
    if not match:
        raise ValueError(f"invalid note name: {note!r}")
    letter, accidental, octave_text = match.groups()
    pitch = PITCH_CLASSES[letter.upper()]
    if accidental == "#":
        pitch += 1
    elif accidental == "b":
        pitch -= 1
    midi = (int(octave_text) + 1) * 12 + pitch
    if not 0 <= midi <= 127:
        raise ValueError(f"note outside MIDI range: {note!r}")
    return midi


def parse_sets(document: str) -> list[tuple[int, str, list[list[int]]]]:
    parser = TableParser()
    parser.feed(document)
    rows = parser.rows
    sets: list[tuple[int, str, list[list[int]]]] = []

    for index, row in enumerate(rows):
        if len(row) != 14:
            continue
        number_text = row[0].replace("\n", "").strip()
        if not number_text.isdigit() or not 1 <= int(number_text) <= 100:
            continue
        if index + 1 >= len(rows) or len(rows[index + 1]) != 12:
            raise ValueError(f"missing note row for J-6 set {number_text}")

        voicings: list[list[int]] = []
        for cell in rows[index + 1]:
            note_names = [value.strip() for value in cell.splitlines() if value.strip()]
            voicings.append(sorted(note_to_midi(value) for value in note_names))
        sets.append((int(number_text), row[1].replace("\n", " ").strip(), voicings))

    numbers = [number for number, _, _ in sets]
    if numbers != list(range(1, 101)):
        raise ValueError(f"expected J-6 sets 1-100, found: {numbers}")
    return sets


def safe_genre(genre: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", genre.strip().lower()).strip("_")
    return cleaned or "other"


def write_presets(sets: list[tuple[int, str, list[list[int]]]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for number, genre, voicings in sets:
        filename = output_dir / f"j6_{number:03d}_{safe_genre(genre)}.chords"
        lines = [f"Name: J-6 {number:03d} {genre}"]
        lines.extend(f"{index}: {','.join(map(str, notes))}" for index, notes in enumerate(voicings))
        filename.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_source(source: str | None) -> str:
    if source:
        return Path(source).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        piped = sys.stdin.read()
        if piped:
            return piped
    with urllib.request.urlopen(SOURCE_URL) as response:
        return response.read().decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="read a previously downloaded Roland HTML page")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src" / "presets" / "chords",
    )
    args = parser.parse_args()

    sets = parse_sets(read_source(args.source))
    write_presets(sets, args.output_dir)
    chord_count = sum(len(voicings) for _, _, voicings in sets)
    print(f"Imported {len(sets)} J-6 presets containing {chord_count} chord voicings")


if __name__ == "__main__":
    main()
