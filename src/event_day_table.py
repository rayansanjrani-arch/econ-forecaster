"""Build the Layer 2 source-linked event-day table from project event ledgers."""

from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pandas as pd

from config import (
    EVENT_DAY_TABLE_FILE,
    FIRST_RELEASE_OUTCOMES_FILE,
    NEWS_EVENTS_FILE,
    RELEASE_CALENDAR_FILE,
)
from outcome_log import OUTCOME_COLUMNS
from release_calendar import load_calendar


NEWS_EVENT_COLUMNS = [
    "event_id", "public_timestamp", "event_name", "headline", "reference_period",
    "category", "severity", "story_id", "publisher", "source_url", "evidence_note",
]
EVENT_DAY_COLUMNS = [
    "event_id", "event_origin", "event_type", "indicator", "event_name", "headline",
    "reference_period", "public_timestamp_utc", "event_date_et", "category", "severity",
    "story_id", "first_release_value", "first_release_value_secondary",
    "saved_forecast_value", "consensus_value", "consensus_value_secondary",
    "consensus_surprise", "consensus_surprise_secondary", "first_release_outcome",
    "source_name", "source_url", "outcome_source_url", "source_record_type",
    "source_record_id", "evidence_note", "same_day_event_count", "events_within_60m",
    "overlap_flag", "overlap_group_id", "overlap_policy",
]
NEWS_CATEGORIES = {
    "geopolitical_escalation",
    "sanctions",
    "tariffs_trade",
    "government_political_statement",
    "central_bank_surprise",
    "corporate_technology_shock",
    "energy_supply_disruption",
}
EASTERN = ZoneInfo("America/New_York")
OVERLAP_WINDOW_MINUTES = 60
SCHEDULED_SOURCE_NAMES = {
    "core_cpi_mom": "U.S. Bureau of Labor Statistics",
    "ppi": "U.S. Bureau of Labor Statistics",
    "initial_claims": "U.S. Department of Labor",
    "employment_situation": "U.S. Bureau of Labor Statistics",
    "fomc_decision": "Federal Reserve",
    "real_gdp_advance": "U.S. Bureau of Economic Analysis",
    "real_gdp_second": "U.S. Bureau of Economic Analysis",
    "real_gdp_third": "U.S. Bureau of Economic Analysis",
    "retail_sales_advance": "U.S. Census Bureau",
}


def _valid_http_url(value, label):
    parsed = urlsplit(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label} must be an absolute HTTP(S) URL")


def _utc_timestamp(value, label, require_timezone=True):
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a valid ISO timestamp") from exc
    if pd.isna(parsed):
        raise ValueError(f"{label} must be a valid ISO timestamp")
    if require_timezone and parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone offset")
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize(EASTERN)
    return parsed.tz_convert("UTC")


def load_news_events(path=NEWS_EVENTS_FILE):
    """Load and validate manually curated unscheduled headline source records."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=NEWS_EVENT_COLUMNS)
    frame = pd.read_csv(path, keep_default_na=False)
    missing = [column for column in NEWS_EVENT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"News event ledger is missing columns: {', '.join(missing)}")
    frame = frame[NEWS_EVENT_COLUMNS].copy()
    required = ["event_id", "public_timestamp", "event_name", "headline", "category",
                "severity", "publisher", "source_url", "evidence_note"]
    for column in required:
        if frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Every news event needs {column}")
    if frame["event_id"].duplicated().any():
        raise ValueError("News event ledger contains duplicate event_id values")
    unsupported = sorted(set(frame["category"]) - NEWS_CATEGORIES)
    if unsupported:
        raise ValueError(f"Unsupported news event category: {', '.join(unsupported)}")
    try:
        severity = pd.to_numeric(frame["severity"], errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError("News event severity must be an integer from 1 to 5") from exc
    if ((severity % 1) != 0).any() or (~severity.between(1, 5)).any():
        raise ValueError("News event severity must be an integer from 1 to 5")
    frame["severity"] = severity.astype(int)
    timestamps = []
    for value in frame["public_timestamp"]:
        timestamps.append(_utc_timestamp(value, "News public_timestamp"))
    frame["public_timestamp_utc"] = [value.isoformat(timespec="seconds") for value in timestamps]
    for url in frame["source_url"]:
        _valid_http_url(url, "News source_url")
    return frame


def _load_outcomes(path):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=OUTCOME_COLUMNS)
    frame = pd.read_csv(path, keep_default_na=False)
    missing = [column for column in OUTCOME_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"First-release outcome log is missing columns: {', '.join(missing)}")
    frame = frame[OUTCOME_COLUMNS].copy()
    if frame.duplicated(["release", "indicator"]).any():
        raise ValueError("First-release outcome log contains duplicate release/indicator keys")
    return frame


def _number_or_blank(value):
    if value is None or str(value).strip() == "":
        return ""
    number = pd.to_numeric(value, errors="coerce")
    return "" if pd.isna(number) else float(number)


def _scheduled_rows(calendar, outcomes):
    outcome_map = {
        (str(row.release), str(row.indicator)): row
        for row in outcomes.itertuples(index=False)
    }
    rows = []
    for event in calendar.itertuples(index=False):
        key = (str(event.release_date), str(event.indicator))
        outcome = outcome_map.get(key)
        first = _number_or_blank(outcome.actual) if outcome else ""
        first_secondary = _number_or_blank(outcome.actual_secondary) if outcome else ""
        saved_forecast = _number_or_blank(outcome.forecast) if outcome else ""
        consensus = ""
        consensus_secondary = ""
        surprise = ""
        surprise_secondary = ""
        # CPI outcome capture explicitly stores consensus. For other indicators,
        # the saved forecast is not assumed to be external consensus.
        if outcome and event.indicator == "core_cpi_mom":
            consensus = _number_or_blank(outcome.forecast)
            consensus_secondary = _number_or_blank(outcome.forecast_secondary)
            if first != "" and consensus != "":
                surprise = float(first) - float(consensus)
            if first_secondary != "" and consensus_secondary != "":
                surprise_secondary = float(first_secondary) - float(consensus_secondary)
        timestamp = _utc_timestamp(event.release_time_utc, "Calendar release_time_utc")
        rows.append({
            "event_id": f"scheduled:{event.release_date}:{event.indicator}",
            "event_origin": "scheduled",
            "event_type": event.indicator,
            "indicator": event.indicator,
            "event_name": event.event,
            "headline": "",
            "reference_period": event.reference_period,
            "public_timestamp_utc": timestamp.isoformat(timespec="seconds"),
            "event_date_et": timestamp.tz_convert(EASTERN).strftime("%Y-%m-%d"),
            "category": "",
            "severity": "",
            "story_id": "",
            "first_release_value": first,
            "first_release_value_secondary": first_secondary,
            "saved_forecast_value": saved_forecast,
            "consensus_value": consensus,
            "consensus_value_secondary": consensus_secondary,
            "consensus_surprise": surprise,
            "consensus_surprise_secondary": surprise_secondary,
            "first_release_outcome": str(outcome.outcome) if outcome else "",
            "source_name": SCHEDULED_SOURCE_NAMES.get(event.indicator, event.event),
            "source_url": outcome.source_url if outcome and str(outcome.source_url).strip() else event.source_url,
            "outcome_source_url": outcome.source_url if outcome else "",
            "source_record_type": "release_calendar",
            "source_record_id": f"release_calendar:{event.release_date}:{event.indicator}",
            "evidence_note": "",
            "public_timestamp": timestamp,
        })
    return rows


def _news_rows(news):
    rows = []
    for event in news.itertuples(index=False):
        timestamp = pd.Timestamp(event.public_timestamp_utc)
        rows.append({
            "event_id": str(event.event_id),
            "event_origin": "unscheduled",
            "event_type": str(event.category),
            "indicator": "",
            "event_name": str(event.event_name),
            "headline": str(event.headline),
            "reference_period": str(event.reference_period),
            "public_timestamp_utc": timestamp.isoformat(timespec="seconds"),
            "event_date_et": timestamp.tz_convert(EASTERN).strftime("%Y-%m-%d"),
            "category": str(event.category),
            "severity": int(event.severity),
            "story_id": str(event.story_id),
            "first_release_value": "",
            "first_release_value_secondary": "",
            "saved_forecast_value": "",
            "consensus_value": "",
            "consensus_value_secondary": "",
            "consensus_surprise": "",
            "consensus_surprise_secondary": "",
            "first_release_outcome": "",
            "source_name": str(event.publisher),
            "source_url": str(event.source_url),
            "outcome_source_url": "",
            "source_record_type": "news_events",
            "source_record_id": f"news_events:{event.event_id}",
            "evidence_note": str(event.evidence_note),
            "public_timestamp": timestamp,
        })
    return rows


def _add_overlap_flags(rows, overlap_window_minutes=OVERLAP_WINDOW_MINUTES):
    if not rows:
        return rows
    parent = list(range(len(rows)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    day_counts = {}
    for row in rows:
        day_counts[row["event_date_et"]] = day_counts.get(row["event_date_et"], 0) + 1
    times = [row["public_timestamp"] for row in rows]
    nearby_counts = [0] * len(rows)
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            seconds = abs((times[left] - times[right]).total_seconds())
            same_day = rows[left]["event_date_et"] == rows[right]["event_date_et"]
            near = seconds <= overlap_window_minutes * 60
            if same_day or near:
                union(left, right)
            if near:
                nearby_counts[left] += 1
                nearby_counts[right] += 1

    components = {}
    for index in range(len(rows)):
        components.setdefault(find(index), []).append(index)
    for indices in components.values():
        overlapping = len(indices) > 1
        group_id = ""
        if overlapping:
            member_ids = "|".join(sorted(rows[index]["event_id"] for index in indices))
            group_id = "overlap:" + sha256(member_ids.encode("utf-8")).hexdigest()[:12]
        for index in indices:
            row = rows[index]
            row["same_day_event_count"] = day_counts[row["event_date_et"]]
            row["events_within_60m"] = nearby_counts[index]
            row["overlap_flag"] = overlapping
            row["overlap_group_id"] = group_id
            row["overlap_policy"] = (
                "exclude_from_single_event_analysis" if overlapping
                else "eligible_for_single_event_analysis"
            )
    return rows


def build_event_day_table(calendar_path=RELEASE_CALENDAR_FILE,
                          outcome_path=FIRST_RELEASE_OUTCOMES_FILE,
                          news_path=NEWS_EVENTS_FILE):
    """Combine scheduled calendar entries and curated headlines with provenance."""
    calendar = load_calendar(calendar_path)
    outcomes = _load_outcomes(outcome_path)
    news = load_news_events(news_path)
    rows = _scheduled_rows(calendar, outcomes)
    rows.extend(_news_rows(news))
    ids = [row["event_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Combined event sources contain duplicate event_id values")
    rows = _add_overlap_flags(rows)
    for row in rows:
        row.pop("public_timestamp", None)
    table = pd.DataFrame(rows, columns=EVENT_DAY_COLUMNS)
    if not table.empty:
        table = table.sort_values(["public_timestamp_utc", "event_id"], kind="stable").reset_index(drop=True)
    return table


def save_event_day_table(table, path=EVENT_DAY_TABLE_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table[EVENT_DAY_COLUMNS].to_csv(path, index=False)
    return path
