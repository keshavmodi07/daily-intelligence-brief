#!/usr/bin/env python3
"""Daily Intelligence Brief — generate and email a personalized briefing."""

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


def today_ist() -> datetime:
    return datetime.now(IST)


def generate_brief(client: OpenAI, instructions: str, date_str: str) -> str:
    """Use OpenAI Responses API with web search to produce the briefing."""
    user_input = (
        f"Generate today's Daily Intelligence Brief for {date_str}. "
        "Search the web for the most important developments from the previous 24 hours "
        "across AI, startups, venture capital, technology, economics, geopolitics, "
        "manufacturing, defence, semiconductors, energy, science, India, the United States, "
        "and China. "
        "Follow the prompt structure exactly. Use markdown formatting with clear headers "
        "and bullet points. Cite sources where possible."
    )

    logger.info("Requesting briefing from OpenAI (model=%s, web_search=enabled)", config.OPENAI_MODEL)

    response = client.responses.create(
        model=config.OPENAI_MODEL,
        instructions=instructions,
        input=user_input,
        tools=[{"type": "web_search"}],
    )

    brief = response.output_text
    if not brief or not brief.strip():
        raise RuntimeError("OpenAI returned an empty briefing.")

    logger.info("Briefing generated (%d characters)", len(brief))
    return brief.strip()


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
      border-top: 1px solid #e2e8f0;
      margin: 24px 0;
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


def send_email(subject: str, html_body: str, plain_body: str) -> None:
    """Send the briefing via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_EMAIL
    msg["To"] = config.RECIPIENT_EMAIL

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    logger.info("Sending email to %s", config.RECIPIENT_EMAIL)

    with smtplib.SMTP(config.GMAIL_SMTP_HOST, config.GMAIL_SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config.GMAIL_EMAIL, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_EMAIL, config.RECIPIENT_EMAIL, msg.as_string())

    logger.info("Email sent successfully")


def main() -> int:
    try:
        config.validate()
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    date_str = today_ist().strftime("%Y-%m-%d")
    subject = f"Daily Intelligence Brief - {date_str}"

    try:
        instructions = config.load_prompt()
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        brief_md = generate_brief(client, instructions, date_str)
        html_body = markdown_to_html(brief_md)
        send_email(subject, html_body, brief_md)
    except Exception:
        logger.exception("Failed to generate or send daily briefing")
        return 1

    logger.info("Daily Intelligence Brief completed for %s", date_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
