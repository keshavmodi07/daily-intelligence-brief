"""Configuration loaded from environment variables."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

PROMPT_BUILDER_FILE = BASE_DIR / "prompt_builder.txt"
PROMPT_STRATEGIC_FILE = BASE_DIR / "prompt_strategic.txt"
PROTOCOL_FILE = BASE_DIR / "prompt_protocol.txt"
OUTPUT_RULES_FILE = BASE_DIR / "prompt_output.txt"
MEMORY_FILE = BASE_DIR / "memory.json"
WATCHLIST_FILE = BASE_DIR / "watchlist.json"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o"

RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")

# Email provider: "sendgrid" (recommended) or "gmail"
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "sendgrid").lower()

# SendGrid (free tier — no Gmail App Password needed)
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")

# Gmail SMTP (requires App Password — not available on all accounts)
GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


def validate() -> None:
    """Raise ValueError if required environment variables are missing."""
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not RECIPIENT_EMAIL:
        missing.append("RECIPIENT_EMAIL")

    if EMAIL_PROVIDER == "sendgrid":
        if not SENDGRID_API_KEY:
            missing.append("SENDGRID_API_KEY")
        if not SENDER_EMAIL:
            missing.append("SENDER_EMAIL")
    elif EMAIL_PROVIDER == "gmail":
        if not GMAIL_EMAIL:
            missing.append("GMAIL_EMAIL")
        if not GMAIL_APP_PASSWORD:
            missing.append("GMAIL_APP_PASSWORD")
    else:
        raise ValueError(
            f"Invalid EMAIL_PROVIDER: {EMAIL_PROVIDER!r}. Use 'sendgrid' or 'gmail'."
        )

    if missing:
        raise ValueError(
            "Missing required environment variables: " + ", ".join(missing)
        )


def load_prompt(path: Path) -> str:
    """Load a prompt file."""
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
