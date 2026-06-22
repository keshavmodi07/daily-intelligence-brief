# personal-intelligence-platform

A source-driven Daily Intelligence Brief system that scouts RSS and official sources first, then uses OpenAI to turn evidence into structured candidate events and write two daily email briefings:

- Builder Intelligence Brief
- Strategic Intelligence Brief

It is designed to report what changed, avoid stale repeats, include quiet official-source updates, and keep costs low.

## Pipeline

1. Source Scouting: RSS-first collection from `data/sources.yaml`
2. Content Extraction: `requests` + `BeautifulSoup` fallback for article text
3. Candidate Event Creation: OpenAI converts raw articles into structured events
4. Critical Event Verification: must-not-miss coverage checks plus targeted fallback web search
5. Memory Comparison: NEW / UPDATED / UNCHANGED against `data/memory.json`
6. Ranking and Deduplication: removes duplicates and suppresses unchanged repeats
7. Report Generation: Builder and Strategic briefs
8. Email Delivery: Gmail SMTP or SendGrid
9. Memory Update: updates memory and saves markdown/JSON history

## Files

```text
main.py
config.py
requirements.txt
.env.example
README.md
prompts/
  builder_prompt.txt
  strategic_prompt.txt
data/
  sources.yaml
  watchlist.yaml
  memory.json
  history/
.github/workflows/daily_brief.yml
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill `.env` with:

```text
OPENAI_API_KEY=
EMAIL_PROVIDER=sendgrid
RECIPIENT_EMAIL=
FROM_EMAIL=
SENDGRID_API_KEY=
```

For Brevo instead:

```text
EMAIL_PROVIDER=brevo
RECIPIENT_EMAIL=
FROM_EMAIL=
BREVO_SMTP_LOGIN=
BREVO_SMTP_KEY=
```

For Gmail instead:

```text
EMAIL_PROVIDER=gmail
RECIPIENT_EMAIL=
FROM_EMAIL=
GMAIL_EMAIL=
GMAIL_APP_PASSWORD=
```

## Gmail App Password

1. Enable 2-Step Verification on your Google account.
2. Go to Google Account Security.
3. Create an app password for Mail.
4. Set `GMAIL_EMAIL` and `GMAIL_APP_PASSWORD`.

Some work/school Google accounts block app passwords. Use SendGrid in that case.

## Brevo SMTP

1. Verify your sender email or domain in Brevo.
2. In Brevo, open SMTP & API settings.
3. Copy the SMTP login and SMTP key.
4. Set `EMAIL_PROVIDER=brevo`, `FROM_EMAIL`, `BREVO_SMTP_LOGIN`, and `BREVO_SMTP_KEY`.

Brevo uses `smtp-relay.brevo.com` on port `587` by default.

## Run Locally

PowerShell:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') {
    [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
  }
}
python main.py --dry-run
```

`--dry-run` runs the full intelligence pipeline and saves history, but does not send email.

## GitHub Actions

The workflow runs at `01:30 UTC`, which is `07:00 IST`, and also supports manual `workflow_dispatch`.

Add repository secrets:

| Secret | Required |
|---|---|
| `OPENAI_API_KEY` | Yes |
| `RECIPIENT_EMAIL` | Yes |
| `FROM_EMAIL` | Yes |
| `SENDGRID_API_KEY` | If using SendGrid |
| `BREVO_SMTP_LOGIN` | If using Brevo |
| `BREVO_SMTP_KEY` | If using Brevo |
| `GMAIL_EMAIL` | If using Gmail |
| `GMAIL_APP_PASSWORD` | If using Gmail |

Optional repository variables:

| Variable | Default |
|---|---|
| `OPENAI_MODEL` | `gpt-4.1-mini` |
| `EMAIL_PROVIDER` | `sendgrid` |

## Add RSS Sources

Edit `data/sources.yaml`:

```yaml
groups:
  AI:
    - name: Example Official Blog
      rss_url: https://example.com/feed.xml
      url: https://example.com/news
      official: true
```

For pages without RSS:

```yaml
    - name: Example Press Page
      kind: html
      url: https://example.com/press
      official: true
      selectors: ["article a", "h2 a", "a"]
```

Broken sources are skipped gracefully with a warning.

## Add Watchlist Topics

Edit `data/watchlist.yaml`:

```yaml
AI:
  - OpenAI
  - Anthropic
```

Watchlist topics influence scoring and memory comparison. Unchanged watchlist items may appear only in a compact unchanged list.

## Memory

`data/memory.json` uses this schema:

```json
{
  "topic": "",
  "category": "",
  "first_seen": "",
  "last_reported": "",
  "last_checked": "",
  "status": "",
  "last_summary": "",
  "expected_next_event": "",
  "importance": "",
  "source_urls": []
}
```

Before reporting, candidates are classified as:

- `NEW`
- `UPDATED`
- `UNCHANGED`

Items reported in the last 14 days are suppressed unless there is a real update.

## Must-Not-Miss Verification

The verifier checks required areas across AI, economics, geopolitics, and India. If a category has no candidate events, the platform runs targeted OpenAI web-search fallback when available. If nothing is found, it logs `not found after verification` rather than assuming nothing happened.

## Outputs

Each run saves:

- `data/history/YYYY-MM-DD.md`
- `data/history/YYYY-MM-DD.json`
- updated `data/memory.json`

Email subject:

```text
Daily Intelligence Brief - YYYY-MM-DD
```

## Cost Controls

The system avoids generic broad search. It first scouts sources locally, sends only selected article evidence to OpenAI, and caps fallback searches.

Useful knobs:

- `MAX_ITEMS_PER_SOURCE`
- `MAX_ARTICLES_FOR_EVENT_EXTRACTION`
- `MAX_EVENTS_FOR_PROMPT`
- `MAX_FALLBACK_QUERIES`
- `LOOKBACK_DAYS`
- `OPENAI_MODEL`

## Verify

```bash
python -m py_compile main.py config.py
python - <<'PY'
import json, yaml
from pathlib import Path
yaml.safe_load(Path("data/sources.yaml").read_text())
yaml.safe_load(Path("data/watchlist.yaml").read_text())
json.loads(Path("data/memory.json").read_text())
print("ok")
PY
```
