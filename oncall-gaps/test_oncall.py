from datetime import UTC, datetime

import pytest

from oncall import Shift, find_gaps, hours_per_engineer, merge_coverage, parse_shifts

# ---------------------------------------------------------------- helpers


def U(day: int, hour: int) -> datetime:
    """16 Nov 2026 style UTC timestamp: U(16, 7) -> 2026-11-16 07:00 UTC."""
    return datetime(2026, 11, day, hour, tzinfo=UTC)


def S(name: str, start_h: int, end_h: int, day: int = 16) -> Shift:
    """Shift on one day, whole hours, UTC."""
    return Shift(name, U(day, start_h), U(day, end_h))


# ---------------------------------------------------------------- data

SAMPLE = (
    "\ufeffengineer, tz ,date,start,end\n"
    "Olena,Europe/Kyiv,2026-11-16,09:00,17:00\n"
    "  marco ,Europe/Rome,2026-11-16,08:00,12:00\n"
    "Aiko,Asia/Tokyo,2026-11-17,02:00,06:00\n"
    "SAM,America/New_York,2026-11-16,10:00,14:00\n"
    "olena,Europe/Kyiv,2026-11-16,16:00,20:00\n"
    "Priya,,2026-11-16,10:00,12:00\n"
    "Marco,Europe/Rome,2026-11-16,25:00,26:00\n"
    "Diego,America/New_York,2026-11-16,22:00,02:00\n"
)

REQ5 = (
    "engineer,tz,date,start,end\n"  # line 1
    "Olena,Europe/Kyiv,2026-11-16,09:00,17:00\n"  # 2  valid
    "Priya,,2026-11-16,10:00,12:00\n"  # 3  empty tz
    "Priya,   ,2026-11-16,10:00,12:00\n"  # 4  tz is only spaces
    "Marco,Mars/Base,2026-11-16,08:00,12:00\n"  # 5  unknown tz
    "Sam,America/New_York,2026-13-40,10:00,14:00\n"  # 6  impossible date
    "Sam,America/New_York,2026-11-16,9am,14:00\n"  # 7  unparseable time
    "Aiko,Asia/Tokyo\n"  # 8  short row
    ",Europe/Rome,2026-11-16,08:00,12:00\n"  # 9  empty engineer
    "Diego,America/New_York,2026-11-16,22:00,02:00\n"  # 10 valid
)

DST = (
    "engineer,tz,date,start,end\n"
    "Olena,Europe/Kyiv,2027-03-28,03:30,08:00\n"  # line 2: spring, 03:30 never happens
    "Marco,Europe/Kyiv,2026-10-25,03:30,08:00\n"  # line 3: autumn, 03:30 happens twice
)

EXTRA_COLUMN = (
    "engineer,tz,date,start,end,notes\n"
    "Olena,Europe/Kyiv,2026-11-16,09:00,17:00,covering for Marco\n"
)

MISSING_TZ = "engineer,date,start,end\nOlena,2026-11-16,09:00,17:00\n"

REORDERED = "end,start,date,tz,engineer\n17:00,09:00,2026-11-16,Europe/Kyiv,Olena\n"

EQUAL_TIMES = "engineer,tz,date,start,end\nOlena,Europe/Kyiv,2026-11-16,09:00,09:00\n"


# ---------------------------------------------------------------- parse_shifts


def test_rejected_lines() -> None:
    _, bad = parse_shifts(SAMPLE)
    assert bad == [7, 8]


def test_utc_conversion() -> None:
    shifts, _ = parse_shifts(SAMPLE)
    assert len(shifts) == 6
    aiko = next(s for s in shifts if s.engineer == "aiko")
    assert (aiko.start, aiko.end) == (U(16, 17), U(16, 21))


def test_overnight_shift() -> None:
    shifts, _ = parse_shifts(SAMPLE)
    diego = next(s for s in shifts if s.engineer == "diego")
    assert (diego.start, diego.end) == (U(17, 3), U(17, 7))


def test_names_are_normalised() -> None:
    shifts, _ = parse_shifts(SAMPLE)
    assert [s.engineer for s in shifts] == [
        "olena",
        "marco",
        "aiko",
        "sam",
        "olena",
        "diego",
    ]


def test_stored_times_are_utc() -> None:
    shifts, _ = parse_shifts(SAMPLE)
    for s in shifts:
        assert (
            s.start.utcoffset() is not None and s.start.utcoffset().total_seconds() == 0
        )
        assert s.end.utcoffset() is not None and s.end.utcoffset().total_seconds() == 0


def test_requirement_5_bad_rows_are_rejected() -> None:
    shifts, bad = parse_shifts(REQ5)
    assert [s.engineer for s in shifts] == ["olena", "diego"]
    assert bad == [3, 4, 5, 6, 7, 8, 9]


def test_extra_column_is_ignored() -> None:
    shifts, bad = parse_shifts(EXTRA_COLUMN)
    assert bad == []
    assert [(s.start, s.end) for s in shifts] == [(U(16, 7), U(16, 15))]


def test_missing_column_raises() -> None:
    with pytest.raises(ValueError, match="tz"):
        parse_shifts(MISSING_TZ)


def test_reordered_columns() -> None:
    shifts, bad = parse_shifts(REORDERED)
    assert bad == []
    assert [(s.engineer, s.start, s.end) for s in shifts] == [
        ("olena", U(16, 7), U(16, 15))
    ]


def test_equal_start_and_end_is_zero_length() -> None:
    # Decision: start == end is a same-day, zero-length shift (requirement 4: overnight
    # only when end is *earlier* than start; shifts are always under 24h).
    shifts, bad = parse_shifts(EQUAL_TIMES)
    assert bad == []
    assert [(s.start, s.end) for s in shifts] == [(U(16, 7), U(16, 7))]


def test_dst_nonexistent_rejected_ambiguous_first_occurrence() -> None:
    # Decision: non-existent local times are rejected; ambiguous ones use the first occurrence.
    shifts, bad = parse_shifts(DST)
    assert bad == [2]
    assert len(shifts) == 1
    marco = shifts[0]
    assert marco.start == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert marco.end == datetime(2026, 10, 25, 6, 0, tzinfo=UTC)


# ---------------------------------------------------------------- merge_coverage


def test_merge_sample() -> None:
    shifts, _ = parse_shifts(SAMPLE)
    assert merge_coverage(shifts) == [(U(16, 7), U(16, 21)), (U(17, 3), U(17, 7))]


def test_merge_chain() -> None:
    shifts = [S("a", 7, 15), S("b", 14, 18), S("c", 17, 21)]
    assert merge_coverage(shifts) == [(U(16, 7), U(16, 21))]


def test_merge_contained() -> None:
    shifts = [S("a", 7, 21), S("b", 9, 10), S("c", 15, 16)]
    assert merge_coverage(shifts) == [(U(16, 7), U(16, 21))]


def test_merge_separate() -> None:
    shifts = [S("a", 7, 11), S("b", 13, 16)]
    assert merge_coverage(shifts) == [(U(16, 7), U(16, 11)), (U(16, 13), U(16, 16))]


def test_merge_unsorted_input() -> None:
    shifts = [S("c", 17, 21), S("a", 7, 15), S("b", 14, 18)]
    assert merge_coverage(shifts) == [(U(16, 7), U(16, 21))]


def test_merge_single_shift() -> None:
    assert merge_coverage([S("a", 7, 11)]) == [(U(16, 7), U(16, 11))]


def test_merge_empty() -> None:
    assert merge_coverage([]) == []


def test_merge_empty_generator() -> None:
    assert merge_coverage(s for s in []) == []


def test_merge_accepts_any_iterable() -> None:
    shifts = (s for s in [S("a", 7, 11), S("b", 9, 12)])
    assert merge_coverage(shifts) == [(U(16, 7), U(16, 12))]


# TODO (yours): zero-length shift between two others, e.g. S("z", 12, 12).
#               Decide the expected output and write the test.


# ---------------------------------------------------------------- find_gaps


def test_gaps_sample() -> None:
    shifts, _ = parse_shifts(SAMPLE)
    assert find_gaps(shifts, U(16, 0), U(17, 12)) == [
        (U(16, 0), U(16, 7)),
        (U(16, 21), U(17, 3)),
        (U(17, 7), U(17, 12)),
    ]


def test_no_shifts_means_whole_window_is_a_gap() -> None:
    assert find_gaps([], U(16, 0), U(16, 1)) == [(U(16, 0), U(16, 1))]


def test_gaps_all_shifts_before_window() -> None:
    assert find_gaps([S("a", 1, 3)], U(16, 8), U(16, 20)) == [(U(16, 8), U(16, 20))]


def test_gaps_all_shifts_after_window() -> None:
    assert find_gaps([S("a", 21, 23)], U(16, 8), U(16, 20)) == [(U(16, 8), U(16, 20))]


def test_gaps_between_shifts() -> None:
    shifts = [S("a", 9, 12), S("b", 14, 16)]
    assert find_gaps(shifts, U(16, 8), U(16, 20)) == [
        (U(16, 8), U(16, 9)),
        (U(16, 12), U(16, 14)),
        (U(16, 16), U(16, 20)),
    ]


def test_gaps_ignores_interval_before_window() -> None:
    shifts = [S("a", 1, 2), S("b", 9, 12)]
    assert find_gaps(shifts, U(16, 8), U(16, 20)) == [
        (U(16, 8), U(16, 9)),
        (U(16, 12), U(16, 20)),
    ]


def test_gaps_shift_after_window_is_ignored() -> None:
    shifts = [S("a", 9, 12), S("b", 22, 23)]
    assert find_gaps(shifts, U(16, 8), U(16, 20)) == [
        (U(16, 8), U(16, 9)),
        (U(16, 12), U(16, 20)),
    ]


def test_gaps_cursor_moves_without_gap() -> None:
    shifts = [S("a", 8, 12), S("b", 14, 16)]
    assert find_gaps(shifts, U(16, 8), U(16, 20)) == [
        (U(16, 12), U(16, 14)),
        (U(16, 16), U(16, 20)),
    ]


def test_gaps_shift_starts_exactly_at_window_start() -> None:
    assert find_gaps([S("a", 8, 12)], U(16, 8), U(16, 20)) == [(U(16, 12), U(16, 20))]


def test_gaps_shift_ends_exactly_at_window_end() -> None:
    assert find_gaps([S("a", 15, 20)], U(16, 8), U(16, 20)) == [(U(16, 8), U(16, 15))]


def test_gaps_window_exactly_covered() -> None:
    assert find_gaps([S("a", 8, 20)], U(16, 8), U(16, 20)) == []


# TODO (yours): the hidden find_gaps case — a shift position relative to the
#               window that none of the tests above use.


# ---------------------------------------------------------------- hours_per_engineer


def test_hours_sample() -> None:
    shifts, _ = parse_shifts(SAMPLE)
    assert hours_per_engineer(shifts) == {
        "olena": 11.0,
        "marco": 4.0,
        "aiko": 4.0,
        "sam": 4.0,
        "diego": 4.0,
    }


def test_hours_mixed() -> None:
    shifts = [
        S("olena", 7, 15),
        S("marco", 7, 11),
        S("olena", 14, 18),
        S("sam", 9, 10),
        S("aiko", 8, 20),
        S("sam", 12, 14),
        S("aiko", 10, 12),
    ]
    assert hours_per_engineer(shifts) == {
        "olena": 11.0,
        "marco": 4.0,
        "sam": 3.0,
        "aiko": 12.0,
    }


def test_hours_empty() -> None:
    assert hours_per_engineer([]) == {}


def test_hours_accepts_generator() -> None:
    shifts = (s for s in [S("a", 7, 9), S("a", 8, 10)])
    assert hours_per_engineer(shifts) == {"a": 3.0}


def test_hours_rounding() -> None:
    start = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    end = datetime(2026, 11, 16, 9, 20, tzinfo=UTC)  # 20 minutes
    assert hours_per_engineer([Shift("a", start, end)]) == {"a": 0.33}
