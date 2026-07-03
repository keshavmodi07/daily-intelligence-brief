"""Configuration for personal-intelligence-platform."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

PROMPTS_DIR = BASE_DIR / "prompts"
DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = DATA_DIR / "history"

BUILDER_PROMPT_FILE = PROMPTS_DIR / "builder_prompt.txt"
STRATEGIC_PROMPT_FILE = PROMPTS_DIR / "strategic_prompt.txt"
SOURCES_FILE = DATA_DIR / "sources.yaml"
WATCHLIST_FILE = DATA_DIR / "watchlist.yaml"
MEMORY_FILE = DATA_DIR / "memory.json"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TEMPERATURE = float(os.environ.get("OPENAI_TEMPERATURE", "0.2"))

RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "sendgrid").lower()
EMAIL_SENDER_NAME = os.environ.get("EMAIL_SENDER_NAME", "Personal Intelligence Platform")
FROM_EMAIL = os.environ.get("FROM_EMAIL", os.environ.get("SENDER_EMAIL", ""))

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")

GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
GMAIL_SMTP_HOST = os.environ.get("GMAIL_SMTP_HOST", "smtp.gmail.com")
GMAIL_SMTP_PORT = int(os.environ.get("GMAIL_SMTP_PORT", "587"))

BREVO_SMTP_HOST = os.environ.get("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
BREVO_SMTP_PORT = int(os.environ.get("BREVO_SMTP_PORT", "587"))
BREVO_SMTP_LOGIN = os.environ.get("BREVO_SMTP_LOGIN", "")
BREVO_SMTP_KEY = os.environ.get("BREVO_SMTP_KEY", "")

LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "2"))
MEMORY_SUPPRESSION_DAYS = int(os.environ.get("MEMORY_SUPPRESSION_DAYS", "14"))
MAX_ITEMS_PER_SOURCE = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "20"))
MAX_ARTICLE_CHARS = int(os.environ.get("MAX_ARTICLE_CHARS", "3500"))
MAX_ARTICLES_FOR_EVENT_EXTRACTION = int(os.environ.get("MAX_ARTICLES_FOR_EVENT_EXTRACTION", "90"))
MAX_EVENTS_FOR_PROMPT = int(os.environ.get("MAX_EVENTS_FOR_PROMPT", "45"))
MAX_EVENTS_PER_GROUP = int(os.environ.get("MAX_EVENTS_PER_GROUP", "8"))
MAX_MEMORY_EVENTS = int(os.environ.get("MAX_MEMORY_EVENTS", "35"))
MAX_UNCHANGED_WATCHLIST_ITEMS = int(os.environ.get("MAX_UNCHANGED_WATCHLIST_ITEMS", "10"))
MAX_FALLBACK_QUERIES = int(os.environ.get("MAX_FALLBACK_QUERIES", "24"))
MAX_BEAT_FALLBACK_QUERIES = int(os.environ.get("MAX_BEAT_FALLBACK_QUERIES", "18"))

MIN_EVENT_SCORE = float(os.environ.get("MIN_EVENT_SCORE", "18"))
MIN_FINAL_SCORE = float(os.environ.get("MIN_FINAL_SCORE", "22"))
CRITICAL_SCORE_THRESHOLD = float(os.environ.get("CRITICAL_SCORE_THRESHOLD", "38"))
MIN_COVERAGE_STARS = int(os.environ.get("MIN_COVERAGE_STARS", "3"))

EXTRACT_ARTICLE_TEXT = os.environ.get("EXTRACT_ARTICLE_TEXT", "true").lower() == "true"
ENABLE_TARGETED_FALLBACK_SEARCH = os.environ.get("ENABLE_TARGETED_FALLBACK_SEARCH", "true").lower() == "true"
OPENAI_WEB_SEARCH_TOOL = os.environ.get("OPENAI_WEB_SEARCH_TOOL", "web_search_preview")
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "20"))
USER_AGENT = os.environ.get(
    "USER_AGENT",
    "personal-intelligence-platform/1.0 (+https://github.com/)",
)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


def validate(require_email: bool = True) -> None:
    missing: list[str] = []
    for path in (BUILDER_PROMPT_FILE, STRATEGIC_PROMPT_FILE, SOURCES_FILE, WATCHLIST_FILE, MEMORY_FILE):
        if not path.exists():
            missing.append(str(path.relative_to(BASE_DIR)))

    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")

    if require_email:
        if not RECIPIENT_EMAIL:
            missing.append("RECIPIENT_EMAIL")
        if EMAIL_PROVIDER == "sendgrid":
            if not SENDGRID_API_KEY:
                missing.append("SENDGRID_API_KEY")
            if not FROM_EMAIL:
                missing.append("FROM_EMAIL")
        elif EMAIL_PROVIDER == "gmail":
            if not GMAIL_EMAIL:
                missing.append("GMAIL_EMAIL")
            if not GMAIL_APP_PASSWORD:
                missing.append("GMAIL_APP_PASSWORD")
            if not FROM_EMAIL:
                missing.append("FROM_EMAIL")
        elif EMAIL_PROVIDER == "brevo":
            if not BREVO_SMTP_LOGIN:
                missing.append("BREVO_SMTP_LOGIN")
            if not BREVO_SMTP_KEY:
                missing.append("BREVO_SMTP_KEY")
            if not FROM_EMAIL:
                missing.append("FROM_EMAIL")
        else:
            raise ValueError("EMAIL_PROVIDER must be 'sendgrid', 'gmail', or 'brevo'.")

    if missing:
        raise ValueError("Missing required configuration: " + ", ".join(missing))
