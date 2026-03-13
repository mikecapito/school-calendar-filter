#!/usr/bin/env python3
"""
School Calendar Filter
Fetches an ICS calendar feed, filters events based on configurable rules,
and outputs a filtered .ics file for GitHub Pages hosting.

Filter levels (in priority order — if any match, the event is excluded):
  1. exclude_keywords:  Case-insensitive substring match (broad strokes)
  2. exclude_exact:     Case-insensitive exact title match (surgical)
  3. exclude_patterns:  Regex patterns against title (advanced)

Optionally, include_keywords can require events to match at least one keyword.
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path


def load_config(config_path="config.json"):
    with open(config_path, "r") as f:
        return json.load(f)


def fetch_calendar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SchoolCalendarFilter/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def get_event_summary(event_block):
    """Extract the SUMMARY (title) from a VEVENT block, handling line folding."""
    lines = event_block.split("\n")
    summary_lines = []
    capturing = False
    for line in lines:
        if line.strip().upper().startswith("SUMMARY"):
            colon_pos = line.index(":")
            summary_lines.append(line[colon_pos + 1:].strip())
            capturing = True
        elif capturing:
            if line.startswith(" ") or line.startswith("\t"):
                summary_lines.append(line.strip())
            else:
                break
    return " ".join(summary_lines)


def get_event_searchable_text(event_block):
    """Extract all searchable text (SUMMARY, DESCRIPTION, LOCATION, CATEGORIES)."""
    searchable = []
    lines = event_block.split("\n")
    target_fields = ("SUMMARY", "DESCRIPTION", "LOCATION", "CATEGORIES")
    capturing = False
    for line in lines:
        stripped = line.strip().upper()
        if any(stripped.startswith(f) for f in target_fields):
            colon_pos = line.index(":") if ":" in line else -1
            if colon_pos >= 0:
                searchable.append(line[colon_pos + 1:].strip())
            capturing = True
        elif capturing:
            if line.startswith(" ") or line.startswith("\t"):
                searchable.append(line.strip())
            else:
                capturing = False
    return " ".join(searchable).lower()


def get_event_start_date(event_block):
    """Extract start date from a VEVENT block. Returns a datetime or None."""
    for line in event_block.split("\n"):
        if line.strip().upper().startswith("DTSTART"):
            match = re.search(r"(\d{8})", line)
            if match:
                try:
                    return datetime.strptime(match.group(1), "%Y%m%d")
                except ValueError:
                    return None
    return None


def is_too_old(event_block, config):
    """Check if event is older than the configured cutoff. Returns (True, reason) or (False, None)."""
    days_back = config.get("keep_days_back", 0)
    if days_back <= 0:
        return False, None

    event_date = get_event_start_date(event_block)
    if event_date is None:
        return False, None  # Keep events we can't parse a date for

    cutoff = datetime.now() - timedelta(days=days_back)
    if event_date < cutoff:
        return True, f"older than {days_back} days ({event_date.strftime('%Y-%m-%d')})"
    return False, None


def should_exclude(event_block, config):
    """
    Check if an event should be excluded based on filter rules.
    Returns (True, reason) if excluded, (False, None) if kept.
    """
    summary = get_event_summary(event_block)
    summary_lower = summary.lower().strip()
    searchable_text = get_event_searchable_text(event_block)

    # Level 1: Exclude keywords (substring match against all searchable text)
    for kw in config.get("exclude_keywords", []):
        if kw.lower() in searchable_text:
            return True, f"keyword '{kw}'"

    # Level 2: Exclude exact titles (case-insensitive exact match on SUMMARY)
    for title in config.get("exclude_exact", []):
        if title.lower().strip() == summary_lower:
            return True, f"exact title '{title}'"

    # Level 3: Exclude patterns (regex against SUMMARY)
    for pattern in config.get("exclude_patterns", []):
        if re.search(pattern, summary, re.IGNORECASE):
            return True, f"pattern '{pattern}'"

    return False, None


def should_include(event_block, config):
    """If include_keywords are specified, event must match at least one."""
    include_keywords = config.get("include_keywords", [])
    if not include_keywords:
        return True
    searchable_text = get_event_searchable_text(event_block)
    return any(kw.lower() in searchable_text for kw in include_keywords)


def parse_events(ics_content):
    """Parse ICS into (header, [event_blocks], footer)."""
    parts = re.split(r"(BEGIN:VEVENT.*?END:VEVENT)", ics_content, flags=re.DOTALL)

    header = ""
    footer = ""
    events = []

    if parts:
        header = parts[0]
        for i, part in enumerate(parts[1:], 1):
            if part.strip().startswith("BEGIN:VEVENT"):
                events.append(part)
            elif i == len(parts) - 1:
                footer = part

    if not footer.strip():
        footer = "\nEND:VCALENDAR\n"
    header = header.replace("END:VCALENDAR", "")

    return header, events, footer


def filter_calendar(ics_content, config):
    header, events, footer = parse_events(ics_content)
    original_count = len(events)

    kept = []
    removed = []
    for event in events:
        # Check date first (cheapest filter)
        too_old, reason = is_too_old(event, config)
        if too_old:
            removed.append((get_event_summary(event), reason))
            continue
        excluded, reason = should_exclude(event, config)
        if excluded:
            removed.append((get_event_summary(event), reason))
            continue
        if not should_include(event, config):
            removed.append((get_event_summary(event), "no include keyword match"))
            continue
        kept.append(event)

    print(f"  Total events:   {original_count}")
    print(f"  Kept:           {len(kept)}")
    print(f"  Removed:        {len(removed)}")
    if removed:
        print(f"\n  Removed events:")
        for title, reason in removed:
            print(f"    x {title}  [{reason}]")

    return header + "\n".join(kept) + footer


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    config = load_config(config_path)

    calendar_url = config.get("calendar_url", "")
    output_file = config.get("output_file", "docs/filtered.ics")

    if not calendar_url:
        print("ERROR: No calendar_url specified in config.json")
        sys.exit(1)

    print(f"Fetching calendar from: {calendar_url}")
    ics_content = fetch_calendar(calendar_url)

    print("Filtering events...")
    filtered_content = filter_calendar(ics_content, config)

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(filtered_content)

    print(f"\nFiltered calendar written to: {output_file}")


if __name__ == "__main__":
    main()
