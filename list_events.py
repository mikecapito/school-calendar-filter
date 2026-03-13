#!/usr/bin/env python3
"""
List all event titles from a school calendar feed.
Helps you decide what to add to your exclude filters.

Usage:
  python list_events.py                  # Uses calendar_url from config.json
  python list_events.py <calendar_url>   # Use a URL directly
"""

import json
import re
import sys
import urllib.request
from collections import Counter


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
            # Handle both DTSTART:20240101 and DTSTART;VALUE=DATE:20240101
            match = re.search(r"(\d{8})", line)
            if match:
                d = match.group(1)
                return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return "no date"


def main():
    # Get URL from argument or config
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        url = sys.argv[1]
    else:
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
            url = config.get("calendar_url", "")
        except FileNotFoundError:
            print("No config.json found and no URL provided.")
            print("Usage: python list_events.py <calendar_url>")
            sys.exit(1)

    if not url:
        print("ERROR: No calendar URL found.")
        sys.exit(1)

    print(f"Fetching calendar from: {url}\n")
    ics_content = fetch_calendar(url)

    # Extract events
    event_blocks = re.findall(r"BEGIN:VEVENT.*?END:VEVENT", ics_content, re.DOTALL)

    if not event_blocks:
        print("No events found in feed.")
        sys.exit(0)

    # Collect events with dates
    events = []
    for block in event_blocks:
        summary = get_event_summary(block)
        date = get_event_date(block)
        events.append((date, summary))

    # Sort by date
    events.sort()

    # Print all events
    print(f"Found {len(events)} events:\n")
    print(f"{'DATE':<12}  TITLE")
    print(f"{'-'*12}  {'-'*60}")
    for date, summary in events:
        print(f"{date:<12}  {summary}")

    # Print frequency of recurring titles
    title_counts = Counter(summary for _, summary in events)
    recurring = {t: c for t, c in title_counts.items() if c > 1}

    if recurring:
        print(f"\n\nRecurring events (appear more than once):\n")
        print(f"{'COUNT':<7}  TITLE")
        print(f"{'-'*7}  {'-'*60}")
        for title, count in sorted(recurring.items(), key=lambda x: -x[1]):
            print(f"{count:<7}  {title}")


if __name__ == "__main__":
    main()
