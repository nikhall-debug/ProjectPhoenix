from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd


CANONICAL_TIMESTAMP_DTYPE = "datetime64[ns, UTC]"


def _timestamp_series_ns_utc(values: pd.Series) -> pd.Series:
    """Return one consistent Phoenix timestamp dtype: datetime64[ns, UTC]."""
    converted = pd.to_datetime(values, utc=True, errors="coerce")

    # Pandas may choose seconds, microseconds or nanoseconds depending on the
    # input and platform. merge_asof requires the join-key dtypes to match
    # exactly, so force nanosecond precision at the integration boundary.
    try:
        return converted.astype(CANONICAL_TIMESTAMP_DTYPE)
    except (TypeError, ValueError):
        index = pd.DatetimeIndex(converted)
        if hasattr(index, "as_unit"):
            index = index.as_unit("ns")
        return pd.Series(index, index=values.index, name=values.name)


def normalize_timeline(
    frame: Optional[pd.DataFrame],
    *,
    keep_columns: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """
    Normalize a source timeline before it enters Phoenix's merge layer.

    This guarantees:
      * a timestamp column exists;
      * UTC timezone;
      * nanosecond datetime precision;
      * chronological, unique records;
      * numeric metric columns where conversion is possible.
    """
    if frame is None or frame.empty or "timestamp" not in frame.columns:
        columns = ["timestamp"]
        if keep_columns is not None:
            columns.extend(c for c in keep_columns if c != "timestamp")
        empty = pd.DataFrame(columns=list(dict.fromkeys(columns)))
        empty["timestamp"] = pd.Series(dtype=CANONICAL_TIMESTAMP_DTYPE)
        return empty

    normalized = frame.copy()
    normalized["timestamp"] = _timestamp_series_ns_utc(normalized["timestamp"])

    if keep_columns is not None:
        selected = ["timestamp"] + [
            column
            for column in keep_columns
            if column != "timestamp" and column in normalized.columns
        ]
        normalized = normalized[selected]

    for column in normalized.columns:
        if column != "timestamp":
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    return (
        normalized
        .dropna(subset=["timestamp"])
        .sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .reset_index(drop=True)
    )
