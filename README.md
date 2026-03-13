# School Calendar Filter

Filters a school's ICS calendar feed to remove events you don't care about, then hosts the filtered version on GitHub Pages so you can subscribe to it in Google Calendar.

## How it works

A GitHub Action runs every 6 hours, fetches your school's calendar, applies your filters, and publishes a cleaned-up `.ics` file to GitHub Pages. You subscribe to the GitHub Pages URL instead of the original feed.

## Filter levels

Edit `config.json` to control what gets filtered:

| Filter | What it does | Example |
|---|---|---|
| `exclude_keywords` | Hides any event containing these words (in title, description, or location) | `"staff development"` hides all events with those words anywhere |
| `exclude_exact` | Hides events with this exact title | `"Board Meeting"` hides that specific event but keeps "Parent-Teacher Meeting" |
| `exclude_patterns` | Regex matched against event title | `"^Board.*"` hides anything starting with "Board" |
| `include_keywords` | If non-empty, ONLY keeps events matching at least one keyword | `"grade 3"` would only show Grade 3 events |

**Priority:** Excludes are checked first. If an event matches any exclude rule, it's gone — even if it also matches an include keyword.

## Setup

See the setup instructions below or in the repo wiki.

## Listing events

To see all events in your feed (helpful for deciding what to filter):

```bash
python list_events.py
```

This shows every event title sorted by date, plus a summary of recurring events.

## Adjusting the schedule

The Action runs every 6 hours by default. Edit `.github/workflows/update-calendar.yml` and change the cron expression:

- Every 6 hours: `0 */6 * * *` (default)
- Every 3 hours: `0 */3 * * *`
- Once daily at 6am UTC: `0 6 * * *`
- Every 12 hours: `0 */12 * * *`
