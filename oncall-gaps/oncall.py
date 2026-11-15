import csv
import io
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from operator import attrgetter
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Shift:
    engineer: str
    start: datetime  # timezone-aware, UTC
    end: datetime  # timezone-aware, UTC

def _to_utc(day: date, clock: time, zone: ZoneInfo) -> datetime:
    """Label a local wall-clock time with its zone and convert it to UTC.

    Raises ValueError if the local time doesn't exist (DST spring-forward gap).
    Ambiguous times (DST fall-back) resolve to the first occurrence (fold=0).
    """
    local = datetime.combine(day, clock, tzinfo=zone)
    utc = local.astimezone(UTC)
    if utc.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError(f"{local:%Y-%m-%d %H:%M} does not exist in {zone.key}")
    return utc


def parse_shifts(text: str) -> tuple[list[Shift], list[int]]:
    """Return (valid shifts, line numbers of rejected rows). Header is line 1."""
    if text.lower().startswith("\ufeff"):
        text = text[len("\ufeff") :]
    reader = csv.reader(io.StringIO(text))
    header = [el.strip().lower() for el in next(reader)]
    missing = {"engineer", "tz", "date", "start", "end"} - set(header)
    if missing:
        raise ValueError(f"Missing required columns: {", ".join(sorted(missing))}")

    shifts, rejected_idxs = [], []
    engineer_idx, tz_idx, date_idx, start_idx, end_idx = (
        header.index("engineer"),
        header.index("tz"),
        header.index("date"),
        header.index("start"),
        header.index("end"),
    )
    for idx, line in enumerate(reader):
        try:
            engineer = line[engineer_idx].strip().lower()
            if not engineer:
                raise ValueError(f"Line {idx + 2}: missing engineer name")
            tz = ZoneInfo(line[tz_idx].strip())
            date_value = date.fromisoformat(line[date_idx].strip())
            start = time.fromisoformat(line[start_idx].strip())
            end = time.fromisoformat(line[end_idx].strip())

            end_day = date_value if start <= end else date_value + timedelta(days=1)
            shift = Shift(
                engineer=engineer,
                start=_to_utc(date_value, start, tz),
                end=_to_utc(end_day, end, tz),
            )
            shifts.append(shift)
        except (ValueError, ZoneInfoNotFoundError, IndexError):
            rejected_idxs.append(idx + 2)

    return shifts, rejected_idxs


def merge_coverage(shifts: Iterable[Shift]) -> list[tuple[datetime, datetime]]:
    """Sorted, non-overlapping intervals during which at least one person is on call."""
    shifts_sorted: list[Shift] = sorted(shifts, key=attrgetter("start"))
    if not shifts_sorted:
        return []
    current_end: datetime = shifts_sorted[0].end
    current_start: datetime = shifts_sorted[0].start
    merged: list[tuple[datetime, datetime]] = []

    for elem in shifts_sorted[1:]:
        if elem.start <= current_end:
            current_end = max(current_end, elem.end)
        else:
            merged.append((current_start, current_end))
            current_start = elem.start
            current_end = elem.end
    merged.append((current_start, current_end))
    return merged


def find_gaps(
    shifts: Iterable[Shift], window_start: datetime, window_end: datetime
) -> list[tuple[datetime, datetime]]:
    """Uncovered intervals inside [window_start, window_end), sorted."""
    coverage = merge_coverage(shifts)
    if not coverage:
        return [(window_start, window_end)]
    if coverage[-1][1] <= window_start:
        return [(window_start, window_end)]
    if coverage[0][0] >= window_end:
        return [(window_start, window_end)]

    cursor = window_start
    gaps = []
    for start, end in coverage:
        if end <= window_start:
            continue
        if start >= window_end:
            break

        if start > cursor:
            gaps.append((cursor, start))

        cursor = end

    if cursor < window_end:
        gaps.append((cursor, window_end))
    return gaps

def hours_per_engineer(shifts: Iterable[Shift]) -> dict[str, float]:
    """Hours actually covered per engineer, rounded to 2 decimals."""
    engineer_shifts = defaultdict(list)

    for shift in shifts:
        engineer_shifts[shift.engineer].append(shift)

    result: dict[str, float] = {}

    for engineer, shifts in engineer_shifts.items():
        result[engineer] = round(sum((end - start).total_seconds() / 3600
                               for start, end in merge_coverage(shifts)), 2)

    return result
