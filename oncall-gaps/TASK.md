# oncall-gaps — On-call coverage gaps

## The problem
A small SaaS company runs 24/7 support with engineers in several timezones. Each engineer enters their on-call shifts by hand into a shared CSV, in their own local time. Because it's hand-edited, the sheet is messy: odd spacing and capitalisation, broken rows, and sometimes overlapping entries for the same person.

The support lead needs two answers:
1. **Where are the holes?** Within a given time window, when was nobody on call?
2. **Who covered how much?** How many hours each engineer was actually on call.

## Input
A `str` with the whole CSV already read into memory (up to 10^6 rows). Example (the text starts with a BOM, shown here as `﻿`):

```
\ufeffengineer, tz ,date,start,end
Olena,Europe/Kyiv,2026-11-16,09:00,17:00
  marco ,Europe/Rome,2026-11-16,08:00,12:00
Aiko,Asia/Tokyo,2026-11-17,02:00,06:00
SAM,America/New_York,2026-11-16,10:00,14:00
olena,Europe/Kyiv,2026-11-16,16:00,20:00
Priya,,2026-11-16,10:00,12:00
Marco,Europe/Rome,2026-11-16,25:00,26:00
Diego,America/New_York,2026-11-16,22:00,02:00
```

Columns: `engineer` (name), `tz` (IANA timezone name), `date` (day the shift starts, local), `start` and `end` (local wall-clock times, `HH:MM`).

## What to build (`oncall.py`)

```python
@dataclass(frozen=True)
class Shift:
    engineer: str
    start: datetime   # timezone-aware, UTC
    end: datetime     # timezone-aware, UTC

def parse_shifts(text: str) -> tuple[list[Shift], list[int]]:
    """Return (valid shifts, line numbers of rejected rows). Header is line 1."""

def merge_coverage(shifts: Iterable[Shift]) -> list[tuple[datetime, datetime]]:
    """Sorted, non-overlapping intervals during which at least one person is on call."""

def find_gaps(shifts: Iterable[Shift], window_start: datetime,
              window_end: datetime) -> list[tuple[datetime, datetime]]:
    """Uncovered intervals inside [window_start, window_end), sorted."""

def hours_per_engineer(shifts: Iterable[Shift]) -> dict[str, float]:
    """Hours actually covered per engineer, rounded to 2 decimals."""
```

The public API is fixed. Private helpers, constants and stdlib imports are allowed. Stdlib only, plus pytest for tests.

## Requirements

### Parsing
1. The input may start with a BOM. Header names may have stray spaces and any letter case.
2. Columns are read **by name**, so their order doesn't matter and extra columns are ignored. If a required column is missing, `parse_shifts` raises `ValueError` naming the missing columns.
3. Engineer names are normalised to stripped lowercase (`"  marco "` → `"marco"`).
4. `date`, `start` and `end` are local wall-clock time in the row's `tz`. Everything is stored as UTC.
5. `date` is the day the shift **starts**. If `end` is earlier than `start`, the shift runs overnight and ends the next day. Shifts are always under 24 hours.
6. A broken row is rejected and its line number recorded (header = line 1). `parse_shifts` never raises because of one bad row. Broken means: too few fields, an empty or whitespace-only value, an empty engineer name, an unparseable date or time, an unknown timezone, or a local time that doesn't exist (see 7).
7. **Daylight saving time:** a local time that never happens (the hour skipped when clocks jump forward) makes the row invalid. A local time that happens twice (when clocks go back) resolves to the first occurrence.
8. If `start == end`, the shift is zero-length: it is accepted but covers no time.

### Coverage and gaps
9. `merge_coverage` merges overlapping intervals across all engineers. Intervals that touch (one ends exactly when the next starts) merge into one. Zero-length shifts add nothing to coverage.
10. `find_gaps` returns the uncovered stretches inside the window, in time order. Gaps never extend outside the window, including when a shift crosses a window edge. With no shifts, the whole window is one gap.

### Hours
11. `hours_per_engineer` counts each real hour once: when one person's own shifts overlap (e.g. an extension entered as a second row), the overlap is not double-counted. Example: Olena 09:00–17:00 and 16:00–20:00 Kyiv = 11 hours, not 12.

### Performance
12. Must handle 10^6 shifts. `merge_coverage`, `find_gaps` and `hours_per_engineer` are O(n log n) and must not depend on the length of the window.

## Expected results for the example
- Rejected lines: `[7, 8]` (empty timezone, invalid time). 6 valid shifts.
- Coverage (UTC): 16 Nov 07:00–21:00, and 17 Nov 03:00–07:00.
- Gaps for the window 16 Nov 00:00 → 17 Nov 12:00 UTC: 00:00–07:00, 21:00–03:00, 07:00–12:00.
- Hours: olena 11, marco 4, aiko 4, sam 4, diego 4.

## Tests
`test_oncall.py` covers the requirements above; run it with `pytest`.

## Stretch goal (optional)
`on_call_at(shifts, moments: list[datetime]) -> list[int]`: how many engineers are on call at each moment. Must handle 10^5 queries over 10^6 shifts quickly.