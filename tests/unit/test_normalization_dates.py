from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analisador.core.config import DEFAULT_TIMEZONE, PREVIEW_ROW_COUNT
from analisador.normalization.dates import parse_date_series, parse_date_value

_PT_MONTH_NAMES: tuple[str, ...] = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


@pytest.mark.parametrize(
    ("raw", "dayfirst", "expected_tuple"),
    [
        ("2026-10-15", True, (2026, 10, 15, 0, 0)),
        ("2026-10-15T14:30:00", True, (2026, 10, 15, 14, 30)),
        ("2026-10-15T17:30:00Z", True, (2026, 10, 15, 14, 30)),
        ("2026-10-15T19:30:00+02:00", True, (2026, 10, 15, 14, 30)),
        ("05/10/2026", True, (2026, 10, 5, 0, 0)),
        ("05/10/2026", False, (2026, 5, 10, 0, 0)),
        ("15-10-2026 14:20", True, (2026, 10, 15, 14, 20)),
        ("25 de novembro de 2024 11:43 hs.", True, (2024, 11, 25, 11, 43)),
        ("12 de fevereiro de 2025 21:45 hs.", True, (2025, 2, 12, 21, 45)),
        ("3 de março de 2025", True, (2025, 3, 3, 0, 0)),
        ("3 de marco de 2025", True, (2025, 3, 3, 0, 0)),
        ("25 de noviembre de 2024 11:43 hs.", True, (2024, 11, 25, 11, 43)),
    ],
)
def test_parse_date_value_valid_formats(
    raw: str,
    dayfirst: bool,
    expected_tuple: tuple[int, int, int, int, int],
) -> None:
    parsed = parse_date_value(raw, dayfirst=dayfirst)
    assert parsed is not None
    assert parsed.tzinfo is not None
    localized = parsed.astimezone(ZoneInfo(DEFAULT_TIMEZONE))
    actual = (
        localized.year,
        localized.month,
        localized.day,
        localized.hour,
        localized.minute,
    )
    assert actual == expected_tuple


def test_parse_date_handles_dst_and_invalid_dates() -> None:
    dst_gap = parse_date_value("2018-11-04 00:30:00")
    assert dst_gap is not None
    assert dst_gap.hour == 1

    series_dst = parse_date_series(pd.Series(["2018-11-04 00:30:00"]))
    assert series_dst.parsed_count == 1
    assert series_dst.series.iloc[0].hour == 1

    for invalid in (
        "",
        "  ",
        "31/02/2026",
        "31 de fevereiro de 2025",
        "15 de mes_invalido de 2025",
        "2025-13-45T10:00:00Z",
        "not-a-date",
    ):
        assert parse_date_value(invalid) is None


def test_parse_date_series_aware_iso_and_textual_without_time() -> None:
    aware_res = parse_date_series(
        pd.Series(["2026-10-15T17:30:00Z", "2026-10-16T12:00:00-03:00"])
    )
    assert aware_res.parsed_count == 2
    assert aware_res.invalid_count == 0
    assert aware_res.series.iloc[0].hour == 14

    textual_res = parse_date_series(pd.Series(["15 de outubro de 2025"]))
    assert textual_res.parsed_count == 1
    assert textual_res.series.iloc[0].month == 10
    assert textual_res.series.iloc[0].day == 15


def test_parse_date_series_tracks_empty_invalid_and_sample_limit() -> None:
    empty_res = parse_date_series(pd.Series([], dtype="object"))
    assert empty_res.total_count == 0
    assert empty_res.parsed_count == 0

    all_blank = parse_date_series(pd.Series(["", None, "  "]))
    assert all_blank.empty_count == 3
    assert all_blank.invalid_count == 0

    invalids = [f"bad-date-{idx}" for idx in range(PREVIEW_ROW_COUNT + 5)]
    raw = pd.Series(["2026-10-15", "", *invalids])
    res = parse_date_series(raw)

    assert res.total_count == len(raw)
    assert res.parsed_count == 1
    assert res.empty_count == 1
    assert res.invalid_count == PREVIEW_ROW_COUNT + 5
    assert len(res.sample_invalid_rows) == PREVIEW_ROW_COUNT
    assert res.sample_invalid_rows[0] == 2


@settings(max_examples=100, deadline=None)
@given(
    dt=st.datetimes(
        min_value=datetime(1970, 1, 1),
        max_value=datetime(2099, 12, 31, 23, 59),
    ),
)
def test_date_roundtrip_iso_br_and_pt_textual(dt: datetime) -> None:
    dt_min = dt.replace(second=0, microsecond=0)
    iso_text = dt_min.strftime("%Y-%m-%d %H:%M:%S")
    br_text = dt_min.strftime("%d/%m/%Y %H:%M")
    month_name = _PT_MONTH_NAMES[dt_min.month - 1]
    pt_text = (
        f"{dt_min.day} de {month_name} de {dt_min.year} "
        f"{dt_min.hour:02d}:{dt_min.minute:02d} hs."
    )

    series_res = parse_date_series(pd.Series([iso_text, br_text, pt_text]))
    assert series_res.parsed_count == 3
    assert series_res.invalid_count == 0
    for idx in range(3):
        ts = series_res.series.iloc[idx]
        assert ts.year == dt_min.year
        assert ts.month == dt_min.month
        assert ts.day == dt_min.day


@settings(max_examples=100, deadline=None)
@given(
    values=st.lists(
        st.one_of(
            st.dates(
                min_value=datetime(1990, 1, 1).date(),
                max_value=datetime(2050, 12, 31).date(),
            ).map(lambda d: d.strftime("%d/%m/%Y")),
            st.text(max_size=24),
            st.just(""),
        ),
        max_size=20,
    ),
)
def test_date_series_matches_scalar_parser_on_arbitrary_text(
    values: list[str],
) -> None:
    series_out = parse_date_series(pd.Series(values), dayfirst=True)
    for idx, text in enumerate(values):
        scalar_dt = parse_date_value(text, dayfirst=True)
        series_ts = series_out.series.iloc[idx]
        if scalar_dt is None:
            assert pd.isna(series_ts)
        else:
            assert not pd.isna(series_ts)
            assert series_ts.to_pydatetime() == scalar_dt
