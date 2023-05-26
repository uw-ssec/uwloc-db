import pytest

from uwloc.data.wav import parse_date

dates = [
    ("10:32:00 17/05/2023 (UTC-4)", "2023-05-17T14:32:00+00:00"),
    ("10:32:00 17/05/2023 (UTC+4)", "2023-05-17T06:32:00+00:00"),
    ("10:32:00 17/05/2023 (UTC)", "2023-05-17T10:32:00+00:00"),
]


@pytest.mark.parametrize("date, expected_iso", dates)
def test_parse_date(date: str, expected_iso: str) -> None:
    d = parse_date(date)
    assert d.isoformat() == expected_iso
