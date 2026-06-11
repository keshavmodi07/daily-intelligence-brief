#!/usr/bin/env python3
"""Daily Intelligence Brief — generate and email personalized briefings."""

from __future__ import annotations

import logging
import smtplib
import sys
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown
from openai import OpenAI

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

AGENTS = (
    {
        "name": "Builder",
        "prompt_file": config.PROMPT_BUILDER_FILE,
        "audit_focus": (
            "Tier 1 AI (OpenAI, Anthropic, Google DeepMind, Google Cloud, Microsoft, Nvidia, "
            "Meta AI, xAI, ElevenLabs, Midjourney, Perplexity, Hugging Face, Mistral, Alibaba Qwen), "
            "major tech events (Build, I/O, GTC, WWDC, CES, re:Invent, Meta Connect), "
            "product/API launches, acquisitions, major funding, open source"
        ),
    },
    {
        "name": "Strategic",
        "prompt_file": config.PROMPT_STRATEGIC_FILE,
        "audit_focus": (
            "India: GDP, RBI, PMO, Cabinet, infrastructure, railways, ports, airports, PLI, "
            "semiconductors, defence manufacturing, energy, logistics; Global economics: GDP, "
            "inflation, PMI, Fed, ECB, IMF, World Bank; Geopolitics: Russia-Ukraine, Middle East, "
            "China-Taiwan, India-China, India-Pakistan, US, China, EU, ASEAN; AI labs for strategic "
            "tech impact; diplomacy last 7 days; 3 verification attempts per empty category"
        ),
    },
)


def today_ist() -> datetime:
    return datetime.now(IST)


def run_critical_audit(
    client: OpenAI,
    protocol: str,
    agent_name: str,
    date_str: str,
    audit_focus: str,
) -> str:
    """Stage 1 (Search) + Stage 2 (Critical Event Audit) via web search."""
    instructions = (
        f"{protocol}\n\n"
        f"You are running Stages 1 and 2 for the {agent_name} Intelligence Officer."
    )
    user_input = (
        f"Today is {date_str}. Execute Stage 1 (Search) and Stage 2 (Critical Event Audit).\n\n"
        f"Focus areas for this agent: {audit_focus}\n\n"
        "STAGE 1 — SEARCH:\n"
        "Individually search every Tier 1 source and category relevant to this agent. "
        "Do not use generic news queries. Search each company and institution by name.\n\n"
        "STAGE 2 — CRITICAL EVENT AUDIT:\n"
        "Run the Final Verification Checklist. For each item report: FOUND (with date and summary) "
        "or NOT FOUND. If a Tier 1 event occurred but you have not found it yet, keep searching.\n\n"
        "Output a structured audit report only — do NOT write the full newsletter yet."
    )

    logger.info(
        "Stage 1+2: %s critical audit (model=%s, web_search=enabled)",
        agent_name,
        config.OPENAI_MODEL,
    )

    response = client.responses.create(
        model=config.OPENAI_MODEL,
        instructions=instructions,
        input=user_input,
        tools=[{"type": "web_search"}],
    )

    audit = response.output_text
    if not audit or not audit.strip():
        raise RuntimeError(f"OpenAI returned an empty {agent_name} audit.")

    logger.info("%s audit completed (%d characters)", agent_name, len(audit))
    return audit.strip()


def write_brief(
    client: OpenAI,
    agent_prompt: str,
    protocol: str,
    audit_report: str,
    date_str: str,
    agent_name: str,
) -> str:
    """Stage 3: Write the full briefing using the audit report."""
    instructions = f"{protocol}\n\n{agent_prompt}"
    user_input = (
        f"Today is {date_str}. Execute Stage 3: Write the full {agent_name} Intelligence Brief.\n\n"
        "Use the Critical Event Audit below. Every FOUND Tier 1 event MUST appear prominently "
        "in the newsletter. Do not omit GDP, major launches, or major escalations if they "
        "were found in the audit.\n\n"
        "Apply Recency Rule (72-hour primary, 14-day secondary) and Diversification Rule.\n\n"
        "--- CRITICAL EVENT AUDIT (Stages 1+2) ---\n"
        f"{audit_report}\n"
        "--- END AUDIT ---\n\n"
        "Follow the output format in your prompt exactly. Use markdown with clear headers "
        "and bullet points. Include the Critical Events Audit section at the top. "
        "Cite sources with dates where possible."
    )

    logger.info(
        "Stage 3: Writing %s brief (model=%s, web_search=enabled)",
        agent_name,
        config.OPENAI_MODEL,
    )

    response = client.responses.create(
        model=config.OPENAI_MODEL,
        instructions=instructions,
        input=user_input,
        tools=[{"type": "web_search"}],
    )

    brief = response.output_text
    if not brief or not brief.strip():
        raise RuntimeError(f"OpenAI returned an empty {agent_name} briefing.")

    logger.info("%s brief written (%d characters)", agent_name, len(brief))
    return brief.strip()


def generate_brief(
    client: OpenAI,
    agent_prompt: str,
    protocol: str,
    date_str: str,
    agent_name: str,
    audit_focus: str,
) -> str:
    """Run the full 3-stage pipeline for one agent."""
    audit = run_critical_audit(client, protocol, agent_name, date_str, audit_focus)
    return write_brief(client, agent_prompt, protocol, audit, date_str, agent_name)


def combine_briefs(briefs: list[str], date_str: str) -> str:
    """Merge multiple agent briefs into one document."""
    header = f"# DAILY INTELLIGENCE BRIEF\n\n*{date_str} — Builder + Strategic Reports*\n"
    separator = "\n\n---\n\n"
    return header + separator.join(briefs)


def markdown_to_html(md_text: str) -> str:
    """Convert markdown briefing to mobile-friendly HTML."""
    body_html = markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists", "nl2br"],
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Intelligence Brief</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #1a1a1a;
      max-width: 680px;
      margin: 0 auto;
      padding: 20px 16px;
      background: #ffffff;
    }}
    h1 {{
      font-size: 1.5rem;
      border-bottom: 2px solid #2563eb;
      padding-bottom: 8px;
      margin-top: 0;
      color: #1e40af;
    }}
    h2 {{
      font-size: 1.2rem;
      color: #1e3a5f;
      margin-top: 28px;
      margin-bottom: 12px;
      border-left: 4px solid #2563eb;
      padding-left: 12px;
    }}
    h3 {{
      font-size: 1.05rem;
      color: #334155;
      margin-top: 20px;
    }}
    p {{
      margin: 0 0 12px 0;
    }}
    ul, ol {{
      margin: 0 0 16px 0;
      padding-left: 24px;
    }}
    li {{
      margin-bottom: 6px;
    }}
    strong {{
      color: #0f172a;
    }}
    hr {{
      border: none;
      border-top: 2px solid #e2e8f0;
      margin: 32px 0;
    }}
    a {{
      color: #2563eb;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .footer {{
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid #e2e8f0;
      font-size: 0.85rem;
      color: #64748b;
    }}
  </style>
</head>
<body>
  {body_html}
  <div class="footer">
    Generated automatically by Daily Intelligence Brief &middot; {today_ist().strftime("%Y-%m-%d %H:%M IST")}
  </div>
</body>
</html>"""


def send_email_sendgrid(subject: str, html_body: str, plain_body: str) -> None:
    """Send the briefing via SendGrid API."""
    import json
    import time
    import urllib.error
    import urllib.request

    payload = {
        "personalizations": [{"to": [{"email": config.RECIPIENT_EMAIL}]}],
        "from": {
            "email": config.SENDER_EMAIL,
            "name": "Keshav — Daily Intelligence Brief",
        },
        "reply_to": {"email": config.SENDER_EMAIL, "name": "Daily Intelligence Brief"},
        "subject": subject,
        "headers": {
            "List-Unsubscribe": f"<mailto:{config.SENDER_EMAIL}?subject=unsubscribe>",
            "X-Entity-Ref-ID": f"daily-brief-{today_ist().strftime('%Y-%m-%d')}",
        },
        "categories": ["daily-intelligence-brief"],
        "content": [
            {"type": "text/plain", "value": plain_body},
            {"type": "text/html", "value": html_body},
        ],
        "mail_settings": {
            "footer": {"enable": False},
        },
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {config.SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }

    logger.info("Sending email via SendGrid to %s", config.RECIPIENT_EMAIL)

    last_error: Exception | None = None
    for attempt in range(1, 4):
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.status not in (200, 202):
                    raise RuntimeError(f"SendGrid returned status {response.status}")
            logger.info("Email sent successfully via SendGrid")
            return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_error = exc
            logger.warning("SendGrid attempt %d failed: %s", attempt, exc)
            if attempt < 3:
                time.sleep(5 * attempt)

    raise RuntimeError(f"SendGrid failed after 3 attempts: {last_error}") from last_error


def send_email_gmail(subject: str, html_body: str, plain_body: str) -> None:
    """Send the briefing via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_EMAIL
    msg["To"] = config.RECIPIENT_EMAIL

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    logger.info("Sending email via Gmail to %s", config.RECIPIENT_EMAIL)

    with smtplib.SMTP(config.GMAIL_SMTP_HOST, config.GMAIL_SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config.GMAIL_EMAIL, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_EMAIL, config.RECIPIENT_EMAIL, msg.as_string())

    logger.info("Email sent successfully via Gmail")


def send_email(subject: str, html_body: str, plain_body: str) -> None:
    """Send the briefing using the configured email provider."""
    if config.EMAIL_PROVIDER == "sendgrid":
        send_email_sendgrid(subject, html_body, plain_body)
    else:
        send_email_gmail(subject, html_body, plain_body)


def main() -> int:
    try:
        config.validate()
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    date_str = today_ist().strftime("%Y-%m-%d")
    subject = f"Daily Intelligence Brief - {date_str}"

    try:
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        protocol = config.load_prompt(config.PROTOCOL_FILE)
        briefs: list[str] = []

        for agent in AGENTS:
            agent_prompt = config.load_prompt(agent["prompt_file"])
            brief = generate_brief(
                client,
                agent_prompt,
                protocol,
                date_str,
                agent["name"],
                agent["audit_focus"],
            )
            briefs.append(brief)

        combined_md = combine_briefs(briefs, date_str)
        html_body = markdown_to_html(combined_md)
        send_email(subject, html_body, combined_md)
    except Exception:
        logger.exception("Failed to generate or send daily briefing")
        return 1

    logger.info("Daily Intelligence Brief completed for %s (2 agents)", date_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
