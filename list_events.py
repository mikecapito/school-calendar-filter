#!/usr/bin/env python3
"""
List all event titles from a school calendar feed.
Helps you decide what to add to your exclude filters.

Usage:
  python list_events.py                    # Show ALL events (unfiltered)
  python list_events.py --filtered         # Show only events that survive your filters
  python list_events.py <calendar_url>     # Use a URL directly
"""

import json
import re
import sys
import urllib.request
from collections import Counter

# Import filter logic from filter_calendar.py
from filter_calendar import should_exclude, should_include


def fetch_calendar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SchoolCalendarFilter/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def get_event_summary(event_block):
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


def get_event_date(event_block):
    """Extract start date from event."""
    for line in event_block.split("\n"):
        if line.strip().upper().startswith("DTSTART"):
            match = re.search(r"(\d{8})", line)
            if match:
                d = match.group(1)
                return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return "no date"


def main():
    args = sys.argv[1:]
    filtered_mode = "--filtered" in args
    args = [a for a in args if a != "--filtered"]

    # Load config
    config = {}
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        if not args:
            print("No config.json found and no URL provided.")
            print("Usage: python list_events.py <calendar_url>")
            sys.exit(1)

    # Get URL from argument or config
    if args and args[0].startswith("http"):
        url = args[0]
    else:
        url = config.get("calendar_url", "")

    if not url:
        print("ERROR: No calendar URL found.")
        sys.exit(1)

    if filtered_mode:
        print("MODE: Showing only events that PASS your filters\n")
    else:
        print("MODE: Showing ALL events (use --filtered to apply filters)\n")

    print(f"Fetching calendar from: {url}\n")
    ics_content = fetch_calendar(url)

    # Extract events
    event_blocks = re.findall(r"BEGIN:VEVENT.*?END:VEVENT", ics_content, re.DOTALL)

    if not event_blocks:
        print("No events found in feed.")
        sys.exit(0)

    # Collect events, optionally filtering
    kept_events = []
    removed_events = []
    for block in event_blocks:
        summary = get_event_summary(block)
        date = get_event_date(block)

        if filtered_mode:
            excluded, reason = should_exclude(block, config)
            if excluded:
                removed_events.append((date, summary, reason))
                continue
            if not should_include(block, config):
                removed_events.append((date, summary, "no include keyword match"))
                continue

        kept_events.append((date, summary))

    # Sort by date
    kept_events.sort()
    removed_events.sort()

    # Print kept events
    print(f"Showing {len(kept_events)} events:\n")
    print(f"{'DATE':<12}  TITLE")
    print(f"{'-'*12}  {'-'*60}")
    for date, summary in kept_events:
        print(f"{date:<12}  {summary}")

    # If filtered, also show what was removed
    if filtered_mode and removed_events:
        print(f"\n\nRemoved {len(removed_events)} events:\n")
        print(f"{'DATE':<12}  {'TITLE':<45}  REASON")
        print(f"{'-'*12}  {'-'*45}  {'-'*30}")
        for date, summary, reason in removed_events:
            print(f"{date:<12}  {summary:<45}  {reason}")

    # Print frequency of recurring titles (from kept events)
    title_counts = Counter(summary for _, summary in kept_events)
    recurring = {t: c for t, c in title_counts.items() if c > 1}

    if recurring:
        print(f"\n\nRecurring events (appear more than once):\n")
        print(f"{'COUNT':<7}  TITLE")
        print(f"{'-'*7}  {'-'*60}")
        for title, count in sorted(recurring.items(), key=lambda x: -x[1]):
            print(f"{count:<7}  {title}")


if __name__ == "__main__":
    main()
