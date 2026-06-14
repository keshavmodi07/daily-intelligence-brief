#!/usr/bin/env python3
"""Daily Intelligence Brief — persistent intelligence platform."""

from __future__ import annotations

import json
import logging
import smtplib
import sys
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown
from openai import OpenAI

import config
import memory as mem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

RESEARCH_CATEGORIES = """
AI: OpenAI, Anthropic, Google DeepMind, Google Cloud, Microsoft, Nvidia, Meta AI, xAI,
Perplexity, Mistral, Alibaba Qwen, ElevenLabs, Midjourney, Hugging Face

India: PMO, Cabinet, Ministry of Railways, Ministry of Defence, Ministry of Commerce,
DPIIT, Ministry of Power, NHAI, MoRTH

Infrastructure: Railways, DFCs, Bullet Trains, Vande Bharat, Metro, Airports, Ports,
Freight Corridors, Logistics Parks, Industrial Corridors, Tunnels (Zojila, Z-Morh, Atal)

Manufacturing: Semiconductors, New Factories, Defence Manufacturing, PLI, Supply Chains

Economics: GDP, Inflation, PMI, RBI, Fed, ECB, IMF, OECD, World Bank, Trade

Geopolitics: Russia-Ukraine, Middle East, Israel, Iran, China, Taiwan, India-China,
India-Pakistan, ASEAN, NATO, White House, Pentagon, EU
"""

AGENTS = (
    {
        "name": "Builder",
        "prompt_file": config.PROMPT_BUILDER_FILE,
        "diversification": "No single company may occupy more than 25% of this brief.",
    },
    {
        "name": "Strategic",
        "prompt_file": config.PROMPT_STRATEGIC_FILE,
        "diversification": "No single topic may occupy more than 25% of this brief.",
    },
)


def today_ist() -> datetime:
    return datetime.now(IST)


def call_openai(
    client: OpenAI,
    instructions: str,
    user_input: str,
    *,
    use_web_search: bool = True,
    label: str = "openai",
) -> str:
    kwargs: dict = {
        "model": config.OPENAI_MODEL,
        "instructions": instructions,
        "input": user_input,
    }
    if use_web_search:
        kwargs["tools"] = [{"type": "web_search"}]

    logger.info("%s (model=%s, web_search=%s)", label, config.OPENAI_MODEL, use_web_search)
    response = client.responses.create(**kwargs)
    text = response.output_text
    if not text or not text.strip():
        raise RuntimeError(f"Empty response from {label}")
    logger.info("%s completed (%d characters)", label, len(text))
    return text.strip()


def run_stage1_research(client: OpenAI, protocol: str, date_str: str) -> str:
    instructions = f"{protocol}\n\nYou are executing Stage 1 — Research."
    user_input = (
        f"Today is {date_str}.\n\n"
        "STAGE 1 — RESEARCH\n\n"
        "Search broadly, then specifically, then verify. Never stop after one search.\n"
        "Minimum 3 verification attempts for any category that appears empty.\n\n"
        f"Search ALL categories:\n{RESEARCH_CATEGORIES}\n\n"
        "For each category report findings with: source, original event date, summary.\n"
        "Do NOT write the newsletter. Output structured research notes only."
    )
    return call_openai(client, instructions, user_input, label="Stage 1: Research")


def run_stage2_verification(
    client: OpenAI, protocol: str, research: str, date_str: str
) -> str:
    instructions = f"{protocol}\n\nYou are executing Stage 2 — Critical Event Verification."
    user_input = (
        f"Today is {date_str}.\n\n"
        "STAGE 2 — CRITICAL EVENT VERIFICATION\n\n"
        "Using the research below, verify every checklist item:\n\n"
        "India: GDP, inflation, RBI, Cabinet, infrastructure approvals, defence procurement, "
        "semiconductor announcements, manufacturing investments\n"
        "AI: major launches, model releases, conferences, acquisitions, funding\n"
        "Geopolitics: wars, escalations, diplomatic meetings, trade/defence agreements, sanctions\n\n"
        "For each item: FOUND (date + summary) or NOT FOUND (after 3+ search attempts).\n"
        "If a major development occurred it MUST be marked FOUND.\n\n"
        f"--- STAGE 1 RESEARCH ---\n{research}\n--- END ---\n\n"
        "Continue searching if critical items are missing. Output verification report only."
    )
    return call_openai(
        client, instructions, user_input, label="Stage 2: Critical Event Verification"
    )


def run_stage3_memory_comparison(
    client: OpenAI,
    protocol: str,
    research: str,
    verification: str,
    memory_data: dict,
    watchlist: dict,
    date_str: str,
) -> str:
    instructions = (
        f"{protocol}\n\nYou are executing Stage 3 — Memory Comparison.\n\n"
        "MEMORY RULES:\n"
        "- Do NOT repeat topics from last 14 days unless: milestone, new announcement, "
        "major consequence, or strategic change occurred.\n"
        "- Report WHAT CHANGED, not WHAT EXISTS.\n"
        "- Watchlist items: only report meaningful progress.\n"
        "- Classify each relevant topic: NEW, UPDATED, or UNCHANGED.\n"
        "- UNCHANGED topics should NOT appear in the final newsletter unless a watchlist "
        "item had meaningful progress."
    )
    user_input = (
        f"Today is {date_str}.\n\n"
        "STAGE 3 — MEMORY COMPARISON\n\n"
        f"--- MEMORY.JSON ---\n{mem.format_for_prompt(memory_data)}\n--- END ---\n\n"
        f"--- WATCHLIST.JSON ---\n{mem.format_for_prompt(watchlist)}\n--- END ---\n\n"
        f"--- STAGE 1 RESEARCH ---\n{research}\n--- END ---\n\n"
        f"--- STAGE 2 VERIFICATION ---\n{verification}\n--- END ---\n\n"
        "For every memory topic and watchlist item touched today, output:\n"
        "- Topic\n- Status: NEW / UPDATED / UNCHANGED\n- What changed (if UPDATED/NEW)\n"
        "- Include in newsletter: YES / NO\n- Reason\n\n"
        "Also identify: Missed Yesterday — major events that should have been in yesterday's "
        "report but were not in memory.\n\n"
        "Output structured comparison only — not the full newsletter."
    )
    return call_openai(
        client, instructions, user_input, label="Stage 3: Memory Comparison"
    )


def run_stage4_report(
    client: OpenAI,
    agent_prompt: str,
    protocol: str,
    output_rules: str,
    verification: str,
    memory_comparison: str,
    date_str: str,
    agent_name: str,
    diversification: str,
) -> str:
    instructions = f"{protocol}\n\n{agent_prompt}\n\n{output_rules}"
    user_input = (
        f"Today is {date_str}. Execute Stage 4 — Report Generation for {agent_name}.\n\n"
        f"{diversification}\n\n"
        "MANDATORY RULES:\n"
        "- Every FOUND Tier 1 event from verification MUST appear.\n"
        "- Only include NEW and UPDATED topics from memory comparison (not UNCHANGED).\n"
        "- Report WHAT CHANGED, never restate existence without new information.\n"
        "- GDP, RBI, major conflicts, major launches cannot be omitted if FOUND.\n\n"
        f"--- STAGE 2 VERIFICATION ---\n{verification}\n--- END ---\n\n"
        f"--- STAGE 3 MEMORY COMPARISON ---\n{memory_comparison}\n--- END ---\n\n"
        "Follow output format exactly. Include platform sections: What Changed Since Yesterday, "
        "Source Quality Score, Missed Yesterday (if any). Cite sources with dates."
    )
    return call_openai(
        client,
        instructions,
        user_input,
        label=f"Stage 4: {agent_name} Report",
    )


def update_memory(
    client: OpenAI,
    memory_data: dict,
    verification: str,
    memory_comparison: str,
    briefs: list[str],
    date_str: str,
) -> dict:
    instructions = (
        "You maintain persistent intelligence memory. "
        "Output ONLY valid JSON — no markdown, no commentary."
    )
    user_input = (
        f"Today is {date_str}. Update memory based on today's intelligence run.\n\n"
        f"Current memory:\n{mem.format_for_prompt(memory_data)}\n\n"
        f"Verification:\n{verification}\n\n"
        f"Memory comparison:\n{memory_comparison}\n\n"
        f"Reports generated:\n{chr(10).join(briefs)}\n\n"
        'Return JSON: {"topics": [{"topic": "", "category": "", '
        '"last_reported_date": "YYYY-MM-DD", "importance": "high|medium|low", '
        '"status": "NEW|UPDATED|UNCHANGED|monitoring", '
        '"expected_next_event": "", "last_summary": "one line max"}]}\n'
        "Include all previously tracked topics plus any new ones from today."
    )
    raw = call_openai(
        client,
        instructions,
        user_input,
        use_web_search=False,
        label="Memory update",
    )
    try:
        updated = mem.extract_json_object(raw)
        return mem.merge_memory(memory_data, updated, date_str)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Memory update parse failed, keeping existing memory: %s", exc)
        memory_data["last_updated"] = date_str
        return memory_data


def combine_briefs(briefs: list[str], date_str: str) -> str:
    header = (
        f"# DAILY INTELLIGENCE BRIEF\n\n"
        f"*{date_str} — Builder + Strategic Reports | Intelligence Platform v4*\n"
    )
    return header + "\n\n---\n\n".join(briefs)


def markdown_to_html(md_text: str) -> str:
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
    h1 {{ font-size: 1.5rem; border-bottom: 2px solid #2563eb; padding-bottom: 8px; margin-top: 0; color: #1e40af; }}
    h2 {{ font-size: 1.2rem; color: #1e3a5f; margin-top: 28px; margin-bottom: 12px; border-left: 4px solid #2563eb; padding-left: 12px; }}
    h3 {{ font-size: 1.05rem; color: #334155; margin-top: 20px; }}
    p {{ margin: 0 0 12px 0; }}
    ul, ol {{ margin: 0 0 16px 0; padding-left: 24px; }}
    li {{ margin-bottom: 6px; }}
    strong {{ color: #0f172a; }}
    hr {{ border: none; border-top: 2px solid #e2e8f0; margin: 32px 0; }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 0.85rem; color: #64748b; }}
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
    import urllib.error
    import urllib.request

    payload = {
        "personalizations": [{"to": [{"email": config.RECIPIENT_EMAIL}]}],
        "from": {"email": config.SENDER_EMAIL, "name": "Keshav — Daily Intelligence Brief"},
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
        "mail_settings": {"footer": {"enable": False}},
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
        output_rules = config.load_prompt(config.OUTPUT_RULES_FILE)
        memory_data = mem.load_memory(config.MEMORY_FILE)
        watchlist = mem.load_watchlist(config.WATCHLIST_FILE)

        research = run_stage1_research(client, protocol, date_str)
        verification = run_stage2_verification(client, protocol, research, date_str)
        memory_comparison = run_stage3_memory_comparison(
            client, protocol, research, verification, memory_data, watchlist, date_str
        )

        briefs: list[str] = []
        for agent in AGENTS:
            agent_prompt = config.load_prompt(agent["prompt_file"])
            brief = run_stage4_report(
                client,
                agent_prompt,
                protocol,
                output_rules,
                verification,
                memory_comparison,
                date_str,
                agent["name"],
                agent["diversification"],
            )
            briefs.append(brief)

        combined_md = combine_briefs(briefs, date_str)
        html_body = markdown_to_html(combined_md)
        send_email(subject, html_body, combined_md)

        updated_memory = update_memory(
            client, memory_data, verification, memory_comparison, briefs, date_str
        )
        mem.save_json(config.MEMORY_FILE, updated_memory)
        logger.info("Memory updated (%d topics tracked)", len(updated_memory.get("topics", [])))

    except Exception:
        logger.exception("Failed to generate or send daily briefing")
        return 1

    logger.info("Daily Intelligence Brief completed for %s (4-stage pipeline)", date_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
