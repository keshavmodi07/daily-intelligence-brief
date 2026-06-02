# Daily Intelligence Brief

An automated daily intelligence briefing system that runs in GitHub Actions every morning and emails you a personalized intelligence report.

No VPS. No paid infrastructure except OpenAI API usage.

## What It Does

Every day at **7:00 AM IST**, GitHub Actions:

1. Calls the OpenAI Responses API with **web search** enabled
2. Searches for important developments from the previous 24 hours
3. Analyzes and scores them against your audience profile
4. Generates a structured intelligence briefing
5. Emails it to your inbox as clean, mobile-friendly HTML

You can also trigger a run manually from the **Actions** tab at any time.

## Project Structure

```
daily-intelligence-brief/
├── main.py                          # Orchestrates generation and email delivery
├── config.py                        # Environment variable configuration
├── prompt.txt                       # Configurable intelligence officer prompt
├── requirements.txt                 # Python dependencies
├── .env.example                     # Local development environment template
├── .github/workflows/daily_brief.yml # GitHub Actions workflow
└── README.md
```

## Prerequisites

- A [GitHub](https://github.com) account
- An [OpenAI API key](https://platform.openai.com/api-keys) with billing enabled
- A Gmail account with 2-Step Verification enabled

## Quick Start

### 1. Create the GitHub Repository

```bash
git clone https://github.com/YOUR_USERNAME/daily-intelligence-brief.git
cd daily-intelligence-brief
```

Or push this folder to a new repo:

```bash
git init
git add .
git commit -m "Initial commit: Daily Intelligence Brief"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/daily-intelligence-brief.git
git push -u origin main
```

### 2. Set Up Email (SendGrid — recommended)

Gmail App Passwords are **not available on all accounts** (common if 2-Step Verification isn't enabled, or on school/work accounts). **SendGrid** is free (100 emails/day) and only needs an API key.

1. Sign up at [sendgrid.com](https://signup.sendgrid.com/) (free)
2. Go to **Settings → Sender Authentication → Single Sender Verification**
3. Add and verify `founder.effinova@gmail.com` (check inbox for verification link)
4. Go to **Settings → API Keys → Create API Key**
5. Name it `Daily Brief`, enable **Mail Send** permission, copy the key (`SG....`)

<details>
<summary>Alternative: Gmail App Password (if available on your account)</summary>

1. Enable **2-Step Verification** at [Google Security](https://myaccount.google.com/security)
2. Go to [App passwords](https://myaccount.google.com/apppasswords)
3. Generate a password for Mail → Other ("Daily Intelligence Brief")
4. Set `EMAIL_PROVIDER=gmail` and use `GMAIL_EMAIL` + `GMAIL_APP_PASSWORD` secrets instead

</details>

### 3. Configure GitHub Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name | Value | Required |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key (`sk-...`) | Yes |
| `RECIPIENT_EMAIL` | Where to receive the briefing | Yes |
| `SENDGRID_API_KEY` | SendGrid API key (`SG....`) | Yes |
| `SENDER_EMAIL` | Verified sender email (e.g. `founder.effinova@gmail.com`) | Yes |
| `OPENAI_MODEL` | OpenAI model override (default: `gpt-4o`) | No |

### 4. Enable GitHub Actions

GitHub Actions is enabled by default on new repositories. If disabled:

1. Go to **Settings → Actions → General**
2. Select **Allow all actions and reusable workflows**
3. Save

### 5. Test It

**Manual run:**

1. Go to the **Actions** tab in your repository
2. Select **Daily Intelligence Brief**
3. Click **Run workflow → Run workflow**
4. Check your inbox (and spam folder on first run)

The scheduled run fires automatically every day at **7:00 AM IST** (1:30 AM UTC).

## Local Development

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
# Edit .env with your credentials

# Load env vars and run (Windows PowerShell)
Get-Content .env | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
python main.py

# Load env vars and run (macOS/Linux)
export $(grep -v '^#' .env | xargs) && python main.py
```

## Customizing the Briefing

Edit `prompt.txt` to change the intelligence officer's focus areas, scoring criteria, report sections, or audience profile. Changes take effect on the next run — no code changes needed.

To use a different OpenAI model, set the `OPENAI_MODEL` secret (or env var locally). Models that support the Responses API with web search (e.g. `gpt-4o`) are recommended.

## Email Format

- **Subject:** `Daily Intelligence Brief - YYYY-MM-DD`
- **Body:** Clean HTML with section headers, bullet points, and mobile-friendly styling
- A plain-text version is included as a fallback

## Cost Estimate

Each daily run uses one OpenAI Responses API call with web search. Typical cost is roughly **$0.05–$0.30 per briefing** depending on model and search depth. GitHub Actions free tier (2,000 minutes/month) is more than sufficient.

## Troubleshooting

| Problem | Fix |
|---|---|
| Workflow doesn't run on schedule | Scheduled workflows only run on the default branch (`main`). Confirm the workflow file is on `main`. |
| Email not received | Check spam. Verify sender email in SendGrid. Confirm `SENDGRID_API_KEY` has Mail Send permission. |
| OpenAI error | Verify `OPENAI_API_KEY` is valid and billing is enabled. Check Actions logs for the exact error. |
| Empty briefing | Check Actions logs. The model may have failed to search — retry manually. |

## License

MIT
