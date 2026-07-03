#!/usr/bin/env python3
"""Source-driven personal intelligence platform."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import re
import smtplib
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import feedparser
import markdown
import requests
import yaml
from bs4 import BeautifulSoup
from openai import OpenAI

import config

IST = timezone(timedelta(hours=5, minutes=30))
logger = logging.getLogger("personal-intelligence-platform")

EXCLUDE_TERMS = {
    "sports",
    "cricket",
    "ipl",
    "football",
    "celebrity",
    "entertainment",
    "movie",
    "film",
    "gossip",
    "influencer drama",
    "viral",
    "meme",
}

SERIOUS_TERMS = {
    "election",
    "parliament",
    "minister",
    "cabinet",
    "policy",
    "regulation",
    "sanction",
    "tariff",
    "trade",
    "defence",
    "defense",
    "military",
    "war",
    "diplomacy",
    "investment",
    "factory",
    "semiconductor",
    "rail",
    "infrastructure",
    "port",
    "airport",
    "energy",
    "model",
    "launch",
    "release",
    "approval",
    "procurement",
    "inflation",
    "gdp",
    "central bank",
}

CHANGE_TERMS = {
    "announces",
    "announced",
    "launches",
    "launched",
    "releases",
    "released",
    "approves",
    "approved",
    "signs",
    "signed",
    "opens",
    "opened",
    "awards",
    "awarded",
    "raises",
    "funding",
    "acquires",
    "merger",
    "sanctions",
    "tariff",
    "deploys",
    "begins",
    "starts",
    "completes",
    "milestone",
    "decision",
    "order",
    "contract",
}

MUST_NOT_MISS: dict[str, list[str]] = {
    "AI": [
        "OpenAI",
        "Anthropic",
        "Microsoft AI",
        "Nvidia AI",
        "Google DeepMind",
        "Meta AI",
        "xAI",
        "ElevenLabs",
        "Mistral",
        "Perplexity",
        "Hugging Face",
        "Alibaba Qwen",
    ],
    "Economics": [
        "India GDP",
        "India inflation",
        "RBI decision",
        "US CPI",
        "Fed decision",
        "ECB decision",
        "China GDP",
        "China PMI",
        "IMF major report",
        "World Bank major report",
        "OECD major report",
    ],
    "Geopolitics": [
        "Russia-Ukraine",
        "Israel-Iran",
        "Israel-Gaza",
        "Iran-US",
        "China-Taiwan",
        "India-China",
        "India-Pakistan",
        "NATO",
        "sanctions",
        "military escalations",
        "diplomatic meetings",
    ],
    "India": [
        "Cabinet decisions",
        "PMO announcements",
        "railways",
        "infrastructure",
        "highways",
        "airports",
        "ports",
        "tunnels",
        "semiconductors",
        "manufacturing",
        "defence procurement",
        "energy projects",
    ],
}

DEFAULT_TIMELINES: dict[str, list[str]] = {
    "AI": ["rumor", "announcement", "preview", "developer access", "enterprise rollout", "customer adoption", "second generation"],
    "Semiconductors": ["announcement", "approval", "engineering samples", "fab construction", "pilot production", "mass production", "customer adoption"],
    "India Infrastructure": ["proposal", "DPR", "approval", "land acquisition", "tender", "construction", "trial", "operations"],
    "Infrastructure": ["proposal", "DPR", "approval", "land acquisition", "tender", "construction", "trial", "operations"],
    "Defence": ["requirement", "RFI", "tender", "negotiation", "contract", "prototype", "testing", "induction"],
    "Space": ["announcement", "design", "assembly", "testing", "launch window", "launch", "operations", "follow-on mission"],
    "Geopolitics": ["stable", "tension", "escalating", "crisis", "ceasefire talks", "de-escalating", "settlement"],
}

BEAT_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "AI": {
        "subbeats": {
            "models": ["OpenAI", "Anthropic", "DeepMind", "Meta AI", "Mistral", "Qwen", "xAI"],
            "startups": ["Perplexity", "ElevenLabs", "Groq", "Together AI"],
            "research": ["arXiv", "paper", "benchmark", "research"],
            "tools": ["Cursor", "Windsurf", "Lovable", "Replit", "Vercel AI", "developer tool"],
            "enterprise": ["Microsoft", "Google Cloud", "AWS", "enterprise", "copilot"],
            "hardware": ["Nvidia", "inference chip", "GPU", "ASIC", "semiconductor"],
        },
        "fallback_queries": [
            "official AI model launches OpenAI Anthropic Google DeepMind Meta Mistral xAI last 2 days",
            "AI developer tools Cursor Windsurf Lovable Replit Vercel AI product updates last 2 days",
            "AI infrastructure Groq Together AI Nvidia inference hardware updates last 2 days",
        ],
    },
    "India": {
        "subbeats": {
            "infrastructure": ["NHAI", "MoRTH", "expressway", "highway", "metro", "airport", "port", "tunnel"],
            "manufacturing": ["DPIIT", "Invest India", "factory", "manufacturing", "electronics", "semiconductor"],
            "economy": ["RBI", "inflation", "GDP", "exports", "GST", "finance ministry"],
            "policy": ["Cabinet", "PIB", "notification", "scheme", "policy", "consultation"],
            "defence": ["defence", "DRDO", "procurement", "missile", "aircraft", "shipyard"],
            "energy": ["renewable", "solar", "wind", "power", "coal", "petroleum", "green hydrogen"],
        },
        "fallback_queries": [
            "site:pib.gov.in India Cabinet approval infrastructure manufacturing energy defence railway today",
            "site:nhai.gov.in OR site:morth.nic.in India highway expressway tender award project update",
            "site:powermin.gov.in OR site:mnre.gov.in India renewable power project policy update",
            "site:mod.gov.in India defence procurement manufacturing contract update",
        ],
    },
    "Infrastructure": {
        "subbeats": {
            "highways": ["NHAI", "MoRTH", "highway", "expressway", "Bharatmala"],
            "railways": ["railway", "DFC", "DFCCIL", "NHSRCL", "station redevelopment", "Vande Bharat"],
            "metros": ["metro", "urban rail"],
            "airports_ports": ["airport", "port", "Sagarmala", "AAI"],
            "industrial_corridors": ["industrial corridor", "logistics park", "NICDC"],
        },
        "fallback_queries": [
            "India infrastructure quiet updates NHAI DFCCIL NHSRCL metro airport port tender award last 2 days",
            "site:pib.gov.in railways highways airports ports logistics parks India approval tender last 2 days",
        ],
    },
    "Manufacturing": {
        "subbeats": {
            "electronics": ["electronics", "mobile", "PLI", "EMS"],
            "semiconductors": ["semiconductor", "fab", "ATMP", "Dholera", "Micron"],
            "automotive": ["EV", "battery", "automotive", "auto"],
            "industrial_policy": ["DPIIT", "industrial policy", "manufacturing"],
        },
        "fallback_queries": [
            "India manufacturing investment factory electronics semiconductor DPIIT Invest India last 2 days",
            "site:investindia.gov.in India factory investment manufacturing semiconductor electronics update",
        ],
    },
    "Railways": {
        "subbeats": {
            "freight": ["DFC", "DFCCIL", "freight corridor"],
            "high_speed": ["NHSRCL", "bullet train", "high speed rail"],
            "stations": ["station redevelopment", "Amrit Bharat station"],
            "rolling_stock": ["Vande Bharat", "locomotive", "coach"],
        },
        "fallback_queries": [
            "Indian Railways DFCCIL NHSRCL Vande Bharat station redevelopment tender update last 2 days",
            "site:pib.gov.in Ministry of Railways project approval tender milestone last 2 days",
        ],
    },
    "Defence": {
        "subbeats": {
            "procurement": ["procurement", "contract", "acquisition", "DAC"],
            "manufacturing": ["Make in India", "defence manufacturing", "shipyard", "HAL", "BEL"],
            "programs": ["AMCA", "Tejas", "Project 75I", "missile", "drone"],
        },
        "fallback_queries": [
            "India defence procurement manufacturing contract DRDO HAL BEL last 2 days",
            "site:mod.gov.in India defence acquisition council procurement contract update",
        ],
    },
    "Energy": {
        "subbeats": {
            "renewables": ["renewable", "solar", "wind", "green hydrogen"],
            "power": ["power ministry", "grid", "transmission", "electricity"],
            "fuels": ["coal", "petroleum", "gas", "LNG"],
        },
        "fallback_queries": [
            "India energy renewable power coal petroleum green hydrogen project approval last 2 days",
            "site:powermin.gov.in OR site:mnre.gov.in OR site:coal.nic.in India energy update",
        ],
    },
    "Economics": {
        "subbeats": {
            "india_macro": ["RBI", "India GDP", "inflation", "GST", "exports"],
            "us_europe": ["Fed", "CPI", "ECB", "OECD"],
            "china": ["China GDP", "China PMI", "NBS"],
            "global": ["IMF", "World Bank", "WTO"],
        },
        "fallback_queries": [
            "RBI India inflation GDP exports GST official update last 2 days",
            "IMF World Bank OECD WTO major report economy trade last 2 days",
        ],
    },
    "Space": {
        "subbeats": {
            "isro": ["ISRO", "Gaganyaan", "Chandrayaan", "SSLV", "PSLV"],
            "nasa": ["NASA", "Artemis"],
            "commercial": ["SpaceX", "Rocket Lab", "Blue Origin"],
            "europe": ["ESA"],
        },
        "fallback_queries": [
            "ISRO Gaganyaan Chandrayaan launch update official last 2 days",
            "NASA Artemis ESA Rocket Lab SpaceX launch mission update last 2 days",
        ],
    },
    "Science": {
        "subbeats": {
            "papers": ["Nature", "Science", "arXiv", "paper"],
            "commercialization": ["breakthrough", "prototype", "clinical", "battery", "material"],
        },
        "fallback_queries": [
            "Nature Science arXiv breakthrough battery materials physics AI research last 2 days",
        ],
    },
    "Geopolitics": {
        "subbeats": {
            "europe": ["Ukraine", "Russia", "NATO", "EU"],
            "middle_east": ["Israel", "Iran", "Gaza", "Syria"],
            "indo_pacific": ["China", "Taiwan", "South China Sea", "India-China"],
            "americas": ["United States", "White House", "Congress", "Latin America"],
        },
        "fallback_queries": [
            "Reuters AP geopolitics Ukraine NATO sanctions diplomatic meeting last 2 days",
            "Middle East Israel Iran Gaza ceasefire sanctions diplomacy last 2 days",
            "Indo-Pacific China Taiwan India China US diplomacy military update last 2 days",
        ],
    },
}


@dataclasses.dataclass(slots=True)
class Source:
    group: str
    name: str
    url: str
    rss_url: str | None = None
    kind: str = "rss"
    official: bool = False
    selectors: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(slots=True)
class RawItem:
    title: str
    url: str
    source: str
    source_group: str
    published_date: str
    fetched_date: str
    raw_summary: str
    source_official: bool = False


@dataclasses.dataclass(slots=True)
class Article:
    title: str
    url: str
    source: str
    source_group: str
    published_date: str
    fetched_date: str
    raw_summary: str
    extracted_text: str
    source_official: bool = False


@dataclasses.dataclass(slots=True)
class CandidateEvent:
    event_id: str
    title: str
    category: str
    subcategory: str
    source_urls: list[str]
    source_names: list[str]
    event_date: str
    summary: str
    why_it_matters: str
    entities: list[str]
    countries: list[str]
    confidence: str
    importance_score: float
    founder_relevance_score: float
    long_term_score: float
    freshness_score: float
    verification_status: str = "unverified"
    memory_status: str = "NEW"
    memory_reason: str = ""
    watchlist_hits: list[str] = dataclasses.field(default_factory=list)
    official_source: bool = False
    project: str = ""
    story_stage: str = ""
    previous_stage: str = ""
    stage_advanced: bool = False
    expected_next_milestone: str = ""
    silent_signal: bool = False
    first_order_implication: str = ""
    second_order_implication: str = ""
    who_benefits: list[str] = dataclasses.field(default_factory=list)
    who_loses: list[str] = dataclasses.field(default_factory=list)
    founder_opportunity: str = ""
    investor_takeaway: str = ""
    india_implication: str = ""
    probability: str = "medium"
    what_most_people_are_missing: str = ""
    five_whys: list[str] = dataclasses.field(default_factory=list)
    consequence_scores: dict[str, float] = dataclasses.field(default_factory=dict)

    @property
    def final_score(self) -> float:
        confidence_bonus = {"high": 8, "medium": 3, "low": -8}.get(self.confidence.lower(), 0)
        verification_bonus = {
            "verified_official_source": 10,
            "verified_multi_source": 8,
            "single_source_high_signal": 2,
            "fallback_search": 1,
        }.get(self.verification_status, -4)
        memory_penalty = -40 if self.memory_status == "UNCHANGED" else 0
        return (
            self.importance_score * 0.42
            + self.long_term_score * 0.28
            + self.founder_relevance_score * 0.18
            + self.freshness_score * 0.12
            + confidence_bonus
            + verification_bonus
            + memory_penalty
        )


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def now_ist() -> datetime:
    return datetime.now(IST)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).lower().encode("utf-8")).hexdigest()[:16]


def parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, time.struct_time):
        return datetime.fromtimestamp(time.mktime(value), timezone.utc)
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def date_string(dt: datetime | None) -> str:
    return dt.astimezone(IST).strftime("%Y-%m-%d") if dt else ""


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Could not parse %s; using default", path)
        return default


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def extract_json_object(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.S)
        if not match:
            raise
        return json.loads(match.group(1))


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_sources() -> list[Source]:
    data = load_yaml(config.SOURCES_FILE)
    sources: list[Source] = []
    for group, items in data.get("groups", {}).items():
        for item in items or []:
            if item.get("enabled", True) is False:
                continue
            sources.append(
                Source(
                    group=group,
                    name=item["name"],
                    url=item.get("url") or item.get("rss_url"),
                    rss_url=item.get("rss_url"),
                    kind=item.get("kind", "rss"),
                    official=bool(item.get("official", False)),
                    selectors=list(item.get("selectors") or []),
                )
            )
    return sources


def request_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def source_scouting(sources: list[Source]) -> list[RawItem]:
    logger.info("Stage 1: source scouting across %d sources", len(sources))
    session = request_session()
    items: list[RawItem] = []
    fetched_date = now_ist().isoformat()
    for source in sources:
        try:
            found = scout_rss(source, fetched_date) if source.rss_url or source.kind == "rss" else []
            if not found and source.kind != "rss":
                found = scout_html(source, session, fetched_date)
            items.extend(found)
            logger.info("%s / %s: %d items", source.group, source.name, len(found))
        except Exception as exc:
            logger.warning("Skipping broken source %s (%s): %s", source.name, source.url, exc)
    return items


def scout_rss(source: Source, fetched_date: str) -> list[RawItem]:
    parsed = feedparser.parse(source.rss_url or source.url)
    if parsed.bozo:
        logger.debug("RSS parse warning for %s: %s", source.name, parsed.bozo_exception)
    items: list[RawItem] = []
    for entry in parsed.entries[: config.MAX_ITEMS_PER_SOURCE]:
        title = normalize_text(getattr(entry, "title", ""))
        link = getattr(entry, "link", "") or source.url
        published = parse_date(
            getattr(entry, "published_parsed", None)
            or getattr(entry, "updated_parsed", None)
            or getattr(entry, "published", None)
            or getattr(entry, "updated", None)
        )
        summary = normalize_text(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        if title and link:
            items.append(
                RawItem(
                    title=title,
                    url=link,
                    source=source.name,
                    source_group=source.group,
                    published_date=date_string(published),
                    fetched_date=fetched_date,
                    raw_summary=summary[:1200],
                    source_official=source.official,
                )
            )
    return items


def scout_html(source: Source, session: requests.Session, fetched_date: str) -> list[RawItem]:
    response = session.get(source.url, timeout=config.REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    selectors = source.selectors or ["article a", "h2 a", "h3 a", "a"]
    seen: set[str] = set()
    items: list[RawItem] = []
    for selector in selectors:
        for anchor in soup.select(selector):
            title = normalize_text(anchor.get_text(" "))
            href = anchor.get("href")
            if not title or len(title) < 12 or not href:
                continue
            link = urljoin(source.url, href).split("#")[0]
            if link in seen:
                continue
            seen.add(link)
            items.append(
                RawItem(
                    title=title,
                    url=link,
                    source=source.name,
                    source_group=source.group,
                    published_date="",
                    fetched_date=fetched_date,
                    raw_summary="",
                    source_official=source.official,
                )
            )
            if len(items) >= config.MAX_ITEMS_PER_SOURCE:
                return items
    return items


def content_extraction(raw_items: list[RawItem]) -> list[Article]:
    logger.info("Stage 2: content extraction for %d raw items", len(raw_items))
    session = request_session()
    cutoff = now_ist().date() - timedelta(days=config.LOOKBACK_DAYS)
    articles: list[Article] = []
    seen_urls: set[str] = set()
    for item in raw_items:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        if item.published_date:
            try:
                if datetime.strptime(item.published_date, "%Y-%m-%d").date() < cutoff:
                    continue
            except ValueError:
                logger.debug("Unparseable date for %s: %s", item.url, item.published_date)
        articles.append(extract_article(item, session))
    logger.info("Stage 2: retained %d articles", len(articles))
    return articles


def extract_article(item: RawItem, session: requests.Session) -> Article:
    if not config.EXTRACT_ARTICLE_TEXT:
        return Article(**dataclasses.asdict(item), extracted_text="")
    try:
        response = session.get(item.url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()
        paragraphs = [normalize_text(p.get_text(" ")) for p in soup.select("article p, main p, p")]
        extracted = " ".join(p for p in paragraphs if len(p) > 40)
        return Article(**dataclasses.asdict(item), extracted_text=extracted[: config.MAX_ARTICLE_CHARS])
    except Exception as exc:
        logger.debug("Article extraction failed for %s: %s", item.url, exc)
        return Article(**dataclasses.asdict(item), extracted_text="")


def load_watchlist_terms(watchlist: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for value in watchlist.values():
        if isinstance(value, list):
            terms.extend(str(item) for item in value)
        elif isinstance(value, dict):
            terms.extend(str(item) for item in value.get("items", []))
    return sorted({term.strip() for term in terms if term.strip()})


def is_noise(article: Article) -> bool:
    text = f"{article.title} {article.raw_summary} {article.extracted_text[:500]}".lower()
    return any(term in text for term in EXCLUDE_TERMS) and not any(term in text for term in SERIOUS_TERMS)


def prefilter_articles(articles: list[Article], watchlist: dict[str, Any]) -> list[Article]:
    terms = [term.lower() for term in load_watchlist_terms(watchlist)]
    scored: list[tuple[int, Article]] = []
    for article in articles:
        if is_noise(article):
            continue
        text = f"{article.title} {article.raw_summary} {article.extracted_text}".lower()
        score = 10
        score += 18 if article.source_official else 0
        score += 8 if any(term in text for term in CHANGE_TERMS) else 0
        score += min(25, 5 * sum(1 for term in terms if term.lower() in text))
        score += 3 if article.published_date == now_ist().strftime("%Y-%m-%d") else 0
        scored.append((score, article))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [article for _, article in scored[: config.MAX_ARTICLES_FOR_EVENT_EXTRACTION]]
    logger.info("Stage 3 prefilter: %d articles selected for OpenAI event extraction", len(selected))
    return selected


def article_digest(articles: list[Article]) -> str:
    rows = []
    for idx, article in enumerate(articles, start=1):
        rows.append(
            json.dumps(
                {
                    "idx": idx,
                    "title": article.title,
                    "url": article.url,
                    "source": article.source,
                    "source_group": article.source_group,
                    "published_date": article.published_date,
                    "fetched_date": article.fetched_date,
                    "raw_summary": article.raw_summary[:900],
                    "extracted_text": article.extracted_text[:1800],
                    "source_official": article.source_official,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(rows)


def call_openai(client: OpenAI, instructions: str, user_input: str, label: str, use_web_search: bool = False) -> str:
    logger.info("OpenAI: %s", label)
    kwargs: dict[str, Any] = {
        "model": config.OPENAI_MODEL,
        "instructions": instructions,
        "input": user_input,
        "temperature": config.OPENAI_TEMPERATURE,
    }
    if use_web_search:
        kwargs["tools"] = [{"type": config.OPENAI_WEB_SEARCH_TOOL}]
    try:
        response = client.responses.create(**kwargs)
    except Exception:
        if not use_web_search or config.OPENAI_WEB_SEARCH_TOOL == "web_search":
            raise
        logger.warning("Web search tool %s failed; retrying with web_search", config.OPENAI_WEB_SEARCH_TOOL)
        kwargs["tools"] = [{"type": "web_search"}]
        response = client.responses.create(**kwargs)
    text = response.output_text.strip()
    if not text:
        raise RuntimeError(f"Empty response from {label}")
    return text


def candidate_event_creation(client: OpenAI, articles: list[Article], watchlist: dict[str, Any], date_str: str) -> list[CandidateEvent]:
    logger.info("Stage 3: OpenAI candidate event creation")
    selected_articles = prefilter_articles(articles, watchlist)
    if not selected_articles:
        return []
    instructions = (
        "You convert raw source articles into candidate intelligence events. "
        "Output ONLY valid JSON with key candidate_events. Do not invent facts. "
        "Ignore sports, celebrity, entertainment, gossip, influencer drama, and viral nonsense unless serious consequences are explicit."
    )
    user_input = (
        f"Today is {date_str} IST.\n"
        "Create candidate events with this exact schema:\n"
        "{event_id,title,category,subcategory,source_urls,event_date,summary,why_it_matters,entities,countries,"
        "confidence,importance_score,founder_relevance_score,long_term_score,freshness_score,"
        "project,story_stage,previous_stage,stage_advanced,expected_next_milestone,silent_signal,"
        "first_order_implication,second_order_implication,who_benefits,who_loses,founder_opportunity,"
        "investor_takeaway,india_implication,probability,what_most_people_are_missing,five_whys,consequence_scores}\n"
        "Scores are 0-100. confidence is high, medium, or low. event_id may be blank if unsure.\n"
        "consequence_scores is an object with economic, technological, geopolitical, founder_relevance, india_relevance, and long_term_impact, each 0-10.\n"
        "story_stage should be a compact stage such as announcement, consultation, approval, funding, engineering samples, construction, launch, mass production, adoption, escalation, de-escalation, or no_change.\n"
        "stage_advanced must be true only if the article shows a concrete new milestone versus prior stage/context.\n"
        "silent_signal should be true for quiet official/procurement/standards/consultation/research/project updates that are not front-page news but may matter later.\n"
        "Use first-order, second-order, founder, investor, India, and 5 Whys reasoning. If an implication is not supported, label it as a plausible hypothesis.\n"
        "Merge duplicate articles about the same event. Report only actual changes/developments.\n\n"
        f"WATCHLIST:\n{json.dumps(watchlist, ensure_ascii=False)}\n\n"
        f"RAW ARTICLES JSONL:\n{article_digest(selected_articles)}"
    )
    raw = call_openai(client, instructions, user_input, "candidate event creation")
    payload = extract_json_object(raw)
    return normalize_events(payload.get("candidate_events", []), selected_articles, source_label="source_scouting")


def normalize_events(raw_events: list[dict[str, Any]], articles: list[Article] | None = None, source_label: str = "") -> list[CandidateEvent]:
    article_by_url = {article.url: article for article in articles or []}
    events: list[CandidateEvent] = []
    for item in raw_events:
        urls = [str(url) for url in as_list(item.get("source_urls")) if str(url).strip()]
        if not urls and item.get("url"):
            urls = [str(item["url"])]
        title = normalize_text(str(item.get("title", "")))
        if not title or not urls:
            continue
        source_names = sorted({article_by_url[url].source for url in urls if url in article_by_url})
        official = any(article_by_url[url].source_official for url in urls if url in article_by_url)
        event_id = str(item.get("event_id") or stable_id(title, *urls))
        events.append(
            CandidateEvent(
                event_id=event_id,
                title=title,
                category=str(item.get("category") or "General"),
                subcategory=str(item.get("subcategory") or ""),
                source_urls=urls,
                source_names=source_names or [source_label or "OpenAI fallback"],
                event_date=str(item.get("event_date") or ""),
                summary=normalize_text(str(item.get("summary") or ""))[:1200],
                why_it_matters=normalize_text(str(item.get("why_it_matters") or ""))[:1200],
                entities=[str(v) for v in as_list(item.get("entities"))][:12],
                countries=[str(v) for v in as_list(item.get("countries"))][:8],
                confidence=str(item.get("confidence") or "medium").lower(),
                importance_score=as_float(item.get("importance_score")),
                founder_relevance_score=as_float(item.get("founder_relevance_score")),
                long_term_score=as_float(item.get("long_term_score")),
                freshness_score=as_float(item.get("freshness_score")),
                official_source=official,
                project=normalize_text(str(item.get("project") or ""))[:160],
                story_stage=normalize_text(str(item.get("story_stage") or ""))[:120],
                previous_stage=normalize_text(str(item.get("previous_stage") or ""))[:120],
                stage_advanced=bool(item.get("stage_advanced", False)),
                expected_next_milestone=normalize_text(str(item.get("expected_next_milestone") or ""))[:300],
                silent_signal=bool(item.get("silent_signal", False)),
                first_order_implication=normalize_text(str(item.get("first_order_implication") or ""))[:500],
                second_order_implication=normalize_text(str(item.get("second_order_implication") or ""))[:500],
                who_benefits=[str(v) for v in as_list(item.get("who_benefits"))][:8],
                who_loses=[str(v) for v in as_list(item.get("who_loses"))][:8],
                founder_opportunity=normalize_text(str(item.get("founder_opportunity") or ""))[:500],
                investor_takeaway=normalize_text(str(item.get("investor_takeaway") or ""))[:500],
                india_implication=normalize_text(str(item.get("india_implication") or ""))[:500],
                probability=str(item.get("probability") or "medium").lower(),
                what_most_people_are_missing=normalize_text(str(item.get("what_most_people_are_missing") or ""))[:700],
                five_whys=[str(v) for v in as_list(item.get("five_whys"))][:5],
                consequence_scores={
                    key: as_float(value)
                    for key, value in (item.get("consequence_scores") or {}).items()
                    if key in {
                        "economic",
                        "technological",
                        "geopolitical",
                        "founder_relevance",
                        "india_relevance",
                        "long_term_impact",
                    }
                },
            )
        )
    logger.info("Normalized %d candidate events", len(events))
    return events


def token_set(value: str) -> set[str]:
    stop = {"the", "and", "for", "with", "from", "that", "this", "into", "over", "after", "says", "new"}
    return {t for t in re.findall(r"[a-z0-9]+", value.lower()) if len(t) > 2 and t not in stop}


def similarity(a: str, b: str) -> float:
    left = token_set(a)
    right = token_set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def dedupe_events(events: list[CandidateEvent]) -> list[CandidateEvent]:
    clusters: list[list[CandidateEvent]] = []
    for event in sorted(events, key=lambda item: item.final_score, reverse=True):
        for cluster in clusters:
            if similarity(event.title, cluster[0].title) >= 0.45:
                cluster.append(event)
                break
        else:
            clusters.append([event])
    deduped: list[CandidateEvent] = []
    for cluster in clusters:
        primary = cluster[0]
        for extra in cluster[1:]:
            primary.source_urls = sorted(set(primary.source_urls + extra.source_urls))
            primary.source_names = sorted(set(primary.source_names + extra.source_names))
            primary.official_source = primary.official_source or extra.official_source
        deduped.append(primary)
    return deduped


def must_not_miss_coverage(events: list[CandidateEvent]) -> dict[str, bool]:
    coverage: dict[str, bool] = {}
    haystack = "\n".join(
        f"{event.title} {event.summary} {event.category} {event.subcategory} {' '.join(event.entities)} {' '.join(event.countries)}"
        for event in events
    ).lower()
    for group, topics in MUST_NOT_MISS.items():
        for topic in topics:
            coverage[f"{group}: {topic}"] = topic.lower() in haystack
    return coverage


def targeted_fallback_search(client: OpenAI, missing: list[str], date_str: str) -> tuple[list[CandidateEvent], list[dict[str, str]]]:
    if not missing or not config.ENABLE_TARGETED_FALLBACK_SEARCH:
        return [], [{"topic": topic, "status": "not found after local source verification"} for topic in missing]
    logger.info("Stage 4: targeted fallback search for %d must-not-miss gaps", len(missing))
    queries = missing[: config.MAX_FALLBACK_QUERIES]
    instructions = (
        "You are verifying must-not-miss intelligence categories using web search. "
        "Output ONLY valid JSON with keys candidate_events and verification_notes. "
        "Search targeted official/reputable sources. Do not invent events. If no meaningful update is found, say not_found_after_verification."
    )
    user_input = (
        f"Today is {date_str} IST. For each topic, check whether a meaningful update occurred in the last "
        f"{config.LOOKBACK_DAYS} days. Use official or reputable sources when available.\n\n"
        f"Topics:\n{json.dumps(queries, indent=2)}\n\n"
        "candidate_events schema: event_id,title,category,subcategory,source_urls,event_date,summary,why_it_matters,"
        "entities,countries,confidence,importance_score,founder_relevance_score,long_term_score,freshness_score,"
        "project,story_stage,previous_stage,stage_advanced,expected_next_milestone,silent_signal,"
        "first_order_implication,second_order_implication,who_benefits,who_loses,founder_opportunity,"
        "investor_takeaway,india_implication,probability,what_most_people_are_missing,five_whys,consequence_scores.\n"
        "verification_notes schema: topic,status,evidence_or_reason."
    )
    try:
        raw = call_openai(client, instructions, user_input, "targeted fallback search", use_web_search=True)
        payload = extract_json_object(raw)
        notes = payload.get("verification_notes", [])
        events = normalize_events(payload.get("candidate_events", []), source_label="targeted_fallback_search")
        for event in events:
            event.verification_status = "fallback_search"
        return events, notes
    except Exception as exc:
        logger.warning("Targeted fallback search failed: %s", exc)
        return [], [{"topic": topic, "status": "fallback_search_failed", "evidence_or_reason": str(exc)} for topic in queries]


def critical_event_verification(client: OpenAI, events: list[CandidateEvent], date_str: str) -> tuple[list[CandidateEvent], list[dict[str, str]]]:
    logger.info("Stage 4: critical event verification")
    events = dedupe_events(events)
    for event in events:
        if event.official_source:
            event.verification_status = "verified_official_source"
        elif len(set(event.source_urls)) >= 2 or len(set(event.source_names)) >= 2:
            event.verification_status = "verified_multi_source"
        elif event.importance_score >= config.CRITICAL_SCORE_THRESHOLD and event.confidence != "low":
            event.verification_status = "single_source_high_signal"
        else:
            event.verification_status = "single_source_monitor"

    coverage = must_not_miss_coverage(events)
    missing = [topic for topic, covered in coverage.items() if not covered]
    fallback_events, notes = targeted_fallback_search(client, missing, date_str)
    all_events = dedupe_events(events + fallback_events)
    logger.info("Stage 4: %d events after verification and fallback", len(all_events))
    return all_events, notes


def event_text(event: CandidateEvent) -> str:
    return " ".join(
        [
            event.title,
            event.category,
            event.subcategory,
            event.summary,
            event.why_it_matters,
            event.project,
            " ".join(event.entities),
            " ".join(event.countries),
            " ".join(event.source_names),
        ]
    ).lower()


def event_is_reportable_for_coverage(event: CandidateEvent) -> bool:
    return (
        event.memory_status != "UNCHANGED"
        and event.verification_status != "single_source_monitor"
        and event.final_score >= config.MIN_FINAL_SCORE
    )


def beat_event_matches(beat: str, event: CandidateEvent) -> bool:
    text = event_text(event)
    if beat == "AI":
        return event.category in {"AI", "Developer Tools", "Startups"} or any(
            term.lower() in text for term in ("openai", "anthropic", "deepmind", "mistral", "cursor", "windsurf", "replit", "groq")
        )
    if beat == "India":
        return "india" in text or event.category.startswith("India")
    if beat == "Infrastructure":
        return event.category in {"Infrastructure", "India Infrastructure", "Indian Railways"} or any(
            term in text for term in ("highway", "expressway", "railway", "metro", "airport", "port", "tunnel", "logistics")
        )
    if beat == "Manufacturing":
        return event.category in {"Manufacturing", "Semiconductors"} or any(
            term in text for term in ("manufacturing", "factory", "electronics", "semiconductor", "pli", "fab")
        )
    if beat == "Railways":
        return event.category == "Indian Railways" or any(term in text for term in ("railway", "dfc", "dfccil", "nhsrcl", "vande bharat"))
    if beat == "Defence":
        return event.category == "Defence" or any(term in text for term in ("defence", "defense", "military", "drdo", "procurement", "missile"))
    if beat == "Energy":
        return event.category == "Energy" or any(term in text for term in ("energy", "power", "renewable", "solar", "wind", "coal", "petroleum"))
    if beat == "Economics":
        return event.category == "Economics" or any(term in text for term in ("rbi", "inflation", "gdp", "fed", "ecb", "imf", "world bank"))
    if beat == "Space":
        return event.category == "Space" or any(term in text for term in ("isro", "nasa", "esa", "spacex", "rocket lab", "artemis"))
    if beat == "Science":
        return event.category == "Science" or any(term in text for term in ("nature", "science", "arxiv", "research", "paper"))
    if beat == "Geopolitics":
        return event.category == "Geopolitics" or any(
            term in text for term in ("ukraine", "russia", "nato", "israel", "iran", "taiwan", "china", "sanction", "diplomacy")
        )
    return False


def star_bar(score: int) -> str:
    bounded = max(0, min(5, score))
    return f"{bounded}/5"


def coverage_dashboard(events: list[CandidateEvent]) -> list[dict[str, Any]]:
    dashboard: list[dict[str, Any]] = []
    reportable = [event for event in events if event_is_reportable_for_coverage(event)]
    for beat, spec in BEAT_REQUIREMENTS.items():
        beat_events = [event for event in reportable if beat_event_matches(beat, event)]
        covered_subbeats: list[str] = []
        missing_subbeats: list[str] = []
        for subbeat, terms in spec["subbeats"].items():
            if any(any(term.lower() in event_text(event) for term in terms) for event in beat_events):
                covered_subbeats.append(subbeat)
            else:
                missing_subbeats.append(subbeat)
        subbeat_total = max(1, len(spec["subbeats"]))
        score = round((len(covered_subbeats) / subbeat_total) * 5)
        if beat_events and score == 0:
            score = 1
        dashboard.append(
            {
                "beat": beat,
                "stars": int(score),
                "rating": star_bar(int(score)),
                "reportable_events": len(beat_events),
                "covered_subbeats": covered_subbeats,
                "missing_subbeats": missing_subbeats,
                "status": "adequate" if score >= config.MIN_COVERAGE_STARS else "thin",
            }
        )
    return dashboard


def weak_beat_queries(dashboard: list[dict[str, Any]]) -> list[str]:
    queries: list[str] = []
    for row in dashboard:
        if int(row.get("stars", 0)) >= config.MIN_COVERAGE_STARS:
            continue
        beat = str(row.get("beat", ""))
        missing = ", ".join(row.get("missing_subbeats", []))
        for query in BEAT_REQUIREMENTS.get(beat, {}).get("fallback_queries", []):
            queries.append(f"{beat} beat thin; missing subbeats: {missing}; query: {query}")
    return queries[: config.MAX_BEAT_FALLBACK_QUERIES]


def beat_coverage_verification(
    client: OpenAI,
    events: list[CandidateEvent],
    date_str: str,
) -> tuple[list[CandidateEvent], list[dict[str, str]], list[dict[str, Any]]]:
    logger.info("Stage 4b: beat coverage dashboard")
    dashboard = coverage_dashboard(events)
    queries = weak_beat_queries(dashboard)
    if not queries:
        return [], [], dashboard
    logger.info("Stage 4b: fallback search for %d weak beat queries", len(queries))
    fallback_events, notes = targeted_fallback_search(client, queries, date_str)
    for note in notes:
        note["type"] = "beat_coverage"
    for event in fallback_events:
        event.silent_signal = event.silent_signal or event.importance_score < 55 or event.official_source
    return fallback_events, notes, dashboard


def memory_topic_text(topic: dict[str, Any]) -> str:
    return " ".join(
        str(topic.get(key, ""))
        for key in (
            "topic",
            "category",
            "status",
            "current_stage",
            "last_summary",
            "expected_next_event",
            "expected_next_milestone",
            "times_mentioned",
        )
    )


def event_project_name(event: CandidateEvent) -> str:
    if event.project:
        return event.project
    if event.watchlist_hits:
        return event.watchlist_hits[0]
    if event.entities:
        return event.entities[0]
    return re.sub(r"[:|-].*$", "", event.title).strip()[:90]


def default_timeline(category: str) -> list[str]:
    return DEFAULT_TIMELINES.get(category, ["announcement", "development", "milestone", "adoption", "next generation"])


def stage_index(stage: str, timeline: list[str]) -> int:
    normalized = stage.lower().strip()
    for idx, item in enumerate(timeline):
        if item.lower().strip() == normalized:
            return idx
    return -1


def memory_comparison(events: list[CandidateEvent], memory: dict[str, Any], watchlist: dict[str, Any], date_str: str) -> list[CandidateEvent]:
    logger.info("Stage 5: memory comparison")
    topics = memory.get("topics", [])
    recent_cutoff = now_ist().date() - timedelta(days=config.MEMORY_SUPPRESSION_DAYS)
    watch_terms = load_watchlist_terms(watchlist)

    for event in events:
        event.watchlist_hits = [term for term in watch_terms if term.lower() in f"{event.title} {event.summary}".lower()]
        best = None
        best_sim = 0.0
        event_text = f"{event.title} {event.summary} {event.project} {event.story_stage} {' '.join(event.entities)} {' '.join(event.watchlist_hits)}"
        for topic in topics:
            sim = similarity(event_text, memory_topic_text(topic))
            if sim > best_sim:
                best_sim = sim
                best = topic

        if not best or best_sim < 0.30:
            event.memory_status = "NEW"
            event.memory_reason = "No close memory match."
            continue

        last_reported_raw = str(best.get("last_reported") or best.get("last_reported_date") or "")
        last_reported = None
        try:
            last_reported = datetime.strptime(last_reported_raw, "%Y-%m-%d").date()
        except ValueError:
            pass

        timeline = [str(item) for item in best.get("timeline", [])] or default_timeline(str(best.get("category") or event.category))
        previous_stage = str(best.get("current_stage") or "")
        event.previous_stage = event.previous_stage or previous_stage
        old_idx = stage_index(previous_stage, timeline)
        new_idx = stage_index(event.story_stage, timeline)
        stage_advanced = event.stage_advanced or (new_idx >= 0 and old_idx >= 0 and new_idx > old_idx)
        event.stage_advanced = stage_advanced
        changed_language = any(term in f"{event.title} {event.summary}".lower() for term in CHANGE_TERMS)
        times_mentioned = int(as_float(best.get("times_mentioned"), 0))
        repeat_heavy_without_milestone = times_mentioned >= 3 and not stage_advanced and not changed_language
        if (last_reported and last_reported >= recent_cutoff and not changed_language and not stage_advanced) or repeat_heavy_without_milestone:
            event.memory_status = "UNCHANGED"
            event.memory_reason = (
                f"Project/story '{best.get('topic')}' has been mentioned {times_mentioned} times and remains at "
                f"stage '{previous_stage or 'unknown'}'; no clear stage advance since {last_reported_raw}."
            )
        else:
            event.memory_status = "UPDATED"
            if stage_advanced:
                event.memory_reason = f"Advances '{best.get('topic')}' from '{previous_stage or 'unknown'}' to '{event.story_stage}'."
            else:
                event.memory_reason = f"Updates memory topic '{best.get('topic')}'."
    return events


def rank_and_deduplicate(events: list[CandidateEvent]) -> tuple[list[CandidateEvent], list[CandidateEvent]]:
    logger.info("Stage 6: ranking and deduplication")
    deduped = dedupe_events(events)
    unchanged_watchlist = [event for event in deduped if event.memory_status == "UNCHANGED" and event.watchlist_hits]
    eligible = [
        event
        for event in deduped
        if event.memory_status != "UNCHANGED"
        and event.verification_status != "single_source_monitor"
        and event.final_score >= config.MIN_FINAL_SCORE
    ]
    eligible.sort(key=lambda item: item.final_score, reverse=True)
    per_category: dict[str, int] = defaultdict(int)
    selected: list[CandidateEvent] = []
    for event in eligible:
        if per_category[event.category] >= config.MAX_EVENTS_PER_GROUP:
            continue
        selected.append(event)
        per_category[event.category] += 1
        if len(selected) >= config.MAX_EVENTS_FOR_PROMPT:
            break
    logger.info("Stage 6: selected %d report events; %d unchanged watchlist items", len(selected), len(unchanged_watchlist))
    return selected, unchanged_watchlist[: config.MAX_UNCHANGED_WATCHLIST_ITEMS]


def project_tracker(events: list[CandidateEvent], unchanged: list[CandidateEvent]) -> list[dict[str, Any]]:
    tracked: dict[str, dict[str, Any]] = {}
    for event in events + unchanged:
        name = event_project_name(event)
        if not name:
            continue
        current = tracked.get(name)
        row = {
            "project": name,
            "category": event.category,
            "status": event.memory_status,
            "current_stage": event.story_stage or "unknown",
            "previous_stage": event.previous_stage,
            "stage_advanced": event.stage_advanced,
            "latest_change": event.summary,
            "expected_next_milestone": event.expected_next_milestone,
            "source_urls": event.source_urls[:3],
        }
        if not current or event.final_score > current.get("_score", 0):
            row["_score"] = event.final_score
            tracked[name] = row
    rows = []
    for row in tracked.values():
        row.pop("_score", None)
        rows.append(row)
    return rows[:30]


def emerging_story_tracker(events: list[CandidateEvent]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.category not in {"Geopolitics", "India Infrastructure", "Infrastructure", "AI", "Semiconductors", "Defence", "Space"}:
            continue
        rows.append(
            {
                "story": event_project_name(event),
                "stage": event.story_stage or "unknown",
                "yesterday_or_previous": event.previous_stage or "unknown",
                "today": event.summary,
                "confidence": event.confidence,
                "expected_next_milestone": event.expected_next_milestone,
                "source_urls": event.source_urls[:3],
            }
        )
    return rows[:20]


def probably_missed_today(verification_notes: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        note
        for note in verification_notes
        if note.get("type") == "beat_coverage"
        or "thin" in str(note.get("topic", "")).lower()
        or "not_found_after" in str(note.get("status", "")).lower()
    ][:20]


def event_digest(
    events: list[CandidateEvent],
    unchanged: list[CandidateEvent],
    verification_notes: list[dict[str, str]],
    dashboard: list[dict[str, Any]],
) -> str:
    payload = {
        "events": [dataclasses.asdict(event) | {"final_score": round(event.final_score, 2)} for event in events],
        "unchanged_watchlist_items": [dataclasses.asdict(event) for event in unchanged],
        "coverage_dashboard": dashboard,
        "what_i_probably_missed_today": probably_missed_today(verification_notes),
        "project_tracker": project_tracker(events, unchanged),
        "emerging_story_tracker": emerging_story_tracker(events),
        "silent_signals": [
            dataclasses.asdict(event) | {"final_score": round(event.final_score, 2)}
            for event in events
            if event.silent_signal
        ][:12],
        "verification_notes": verification_notes,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def generate_report(
    client: OpenAI,
    prompt_path: Path,
    events: list[CandidateEvent],
    unchanged: list[CandidateEvent],
    verification_notes: list[dict[str, str]],
    dashboard: list[dict[str, Any]],
    brief_name: str,
    date_str: str,
) -> str:
    prompt = load_prompt(prompt_path)
    user_input = (
        f"Today is {date_str} IST.\n"
        f"Generate the {brief_name}. Use only the supplied JSON evidence. Cite source names and URLs in text. "
        "Do not invent facts. Do not include unchanged items as full stories. Mention low confidence when applicable. "
        "If a date is unclear, flag it.\n\n"
        f"INTELLIGENCE_JSON:\n{event_digest(events, unchanged, verification_notes, dashboard)}"
    )
    return call_openai(client, prompt, user_input, brief_name)


def report_generation(
    client: OpenAI,
    events: list[CandidateEvent],
    unchanged: list[CandidateEvent],
    verification_notes: list[dict[str, str]],
    dashboard: list[dict[str, Any]],
    date_str: str,
) -> tuple[str, str, str]:
    logger.info("Stage 7: report generation")
    builder = generate_report(
        client,
        config.BUILDER_PROMPT_FILE,
        events,
        unchanged,
        verification_notes,
        dashboard,
        "Builder Intelligence Brief",
        date_str,
    )
    strategic = generate_report(
        client,
        config.STRATEGIC_PROMPT_FILE,
        events,
        unchanged,
        verification_notes,
        dashboard,
        "Strategic Intelligence Brief",
        date_str,
    )
    combined = f"# Daily Intelligence Brief - {date_str}\n\n{builder}\n\n---\n\n{strategic}\n"
    return builder, strategic, combined


def markdown_to_html(md_text: str) -> str:
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists", "nl2br"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Intelligence Brief</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.58; color: #111827; max-width: 760px; margin: 0 auto; padding: 24px 16px; }}
    h1 {{ font-size: 25px; margin: 0 0 18px; color: #0f172a; }}
    h2 {{ font-size: 19px; margin: 28px 0 10px; color: #1d4ed8; border-left: 4px solid #2563eb; padding-left: 10px; }}
    h3 {{ font-size: 16px; margin: 20px 0 8px; color: #334155; }}
    p, li {{ font-size: 15px; }}
    a {{ color: #2563eb; }}
    hr {{ border: 0; border-top: 1px solid #dbe3ef; margin: 28px 0; }}
    .footer {{ margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 12px; color: #64748b; font-size: 13px; }}
  </style>
</head>
<body>
{body}
<div class="footer">Generated by personal-intelligence-platform at {now_ist().strftime("%Y-%m-%d %H:%M IST")}</div>
</body>
</html>"""


def send_email_sendgrid(subject: str, html_body: str, plain_body: str) -> None:
    payload = {
        "personalizations": [{"to": [{"email": config.RECIPIENT_EMAIL}]}],
        "from": {"email": config.FROM_EMAIL, "name": config.EMAIL_SENDER_NAME},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": plain_body},
            {"type": "text/html", "value": html_body},
        ],
    }
    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {config.SENDGRID_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if response.status_code not in (200, 202):
        raise RuntimeError(f"SendGrid failed: {response.status_code} {response.text[:500]}")


def send_email_gmail(subject: str, html_body: str, plain_body: str) -> None:
    from_email = config.FROM_EMAIL or config.GMAIL_EMAIL
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = config.RECIPIENT_EMAIL
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP(config.GMAIL_SMTP_HOST, config.GMAIL_SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config.GMAIL_EMAIL, config.GMAIL_APP_PASSWORD)
        server.sendmail(from_email, config.RECIPIENT_EMAIL, msg.as_string())


def send_email_brevo(subject: str, html_body: str, plain_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.FROM_EMAIL
    msg["To"] = config.RECIPIENT_EMAIL
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP(config.BREVO_SMTP_HOST, config.BREVO_SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config.BREVO_SMTP_LOGIN, config.BREVO_SMTP_KEY)
        server.sendmail(config.FROM_EMAIL, config.RECIPIENT_EMAIL, msg.as_string())


def email_delivery(markdown_body: str, date_str: str, dry_run: bool) -> None:
    logger.info("Stage 8: email delivery")
    if dry_run:
        logger.info("Dry run enabled; skipping email send")
        return
    subject = f"Daily Intelligence Brief - {date_str}"
    html_body = markdown_to_html(markdown_body)
    if config.EMAIL_PROVIDER == "sendgrid":
        send_email_sendgrid(subject, html_body, markdown_body)
    elif config.EMAIL_PROVIDER == "gmail":
        send_email_gmail(subject, html_body, markdown_body)
    elif config.EMAIL_PROVIDER == "brevo":
        send_email_brevo(subject, html_body, markdown_body)
    else:
        raise ValueError(f"Unsupported EMAIL_PROVIDER: {config.EMAIL_PROVIDER}")


def normalize_memory(memory: dict[str, Any]) -> dict[str, Any]:
    normalized = {"topics": []}
    for item in memory.get("topics", []):
        category = item.get("category", "")
        timeline = [str(value) for value in item.get("timeline", [])] or default_timeline(str(category))
        normalized["topics"].append(
            {
                "topic": item.get("topic", ""),
                "category": category,
                "first_seen": item.get("first_seen", item.get("last_reported_date", "")),
                "last_reported": item.get("last_reported", item.get("last_reported_date", "")),
                "last_checked": item.get("last_checked", ""),
                "status": item.get("status", "monitoring"),
                "last_summary": item.get("last_summary", ""),
                "expected_next_event": item.get("expected_next_event", ""),
                "importance": item.get("importance", "medium"),
                "source_urls": item.get("source_urls", item.get("last_sources", [])),
                "times_mentioned": int(as_float(item.get("times_mentioned"), 1)),
                "timeline": timeline,
                "current_stage": item.get("current_stage", ""),
                "stage_history": item.get("stage_history", []),
                "expected_next_milestone": item.get("expected_next_milestone", item.get("expected_next_event", "")),
                "emerging_story": item.get("emerging_story", {}),
            }
        )
    return normalized


def memory_update(memory: dict[str, Any], events: list[CandidateEvent], date_str: str) -> dict[str, Any]:
    logger.info("Stage 9: memory update")
    normalized = normalize_memory(memory)
    by_topic = {item["topic"].lower(): item for item in normalized["topics"] if item.get("topic")}
    for event in events[: config.MAX_MEMORY_EVENTS]:
        topic = event_project_name(event)
        key = topic.lower()
        existing = by_topic.get(key, {})
        timeline = [str(value) for value in existing.get("timeline", [])] or default_timeline(event.category)
        current_stage = event.story_stage or existing.get("current_stage") or (timeline[0] if timeline else "")
        times_mentioned = int(as_float(existing.get("times_mentioned"), 0)) + 1
        stage_history = list(existing.get("stage_history", []))
        if current_stage and (not stage_history or stage_history[-1].get("stage") != current_stage):
            stage_history.append(
                {
                    "date": date_str,
                    "stage": current_stage,
                    "summary": event.summary[:220],
                    "source_urls": event.source_urls[:3],
                }
            )
        by_topic[key] = {
            "topic": topic,
            "category": event.category,
            "first_seen": existing.get("first_seen") or date_str,
            "last_reported": date_str,
            "last_checked": date_str,
            "status": event.memory_status,
            "last_summary": event.summary[:300],
            "expected_next_event": event.expected_next_milestone
            or existing.get("expected_next_event")
            or "Watch for the next official update, funding, policy decision, milestone, or measurable consequence.",
            "importance": "high" if event.importance_score >= 70 or event.long_term_score >= 70 else "medium",
            "source_urls": event.source_urls[:5],
            "times_mentioned": times_mentioned,
            "timeline": timeline,
            "current_stage": current_stage,
            "stage_history": stage_history[-10:],
            "expected_next_milestone": event.expected_next_milestone,
            "emerging_story": {
                "stage": current_stage,
                "previous_stage": event.previous_stage,
                "confidence": event.confidence,
                "expected_next_milestone": event.expected_next_milestone,
            },
        }
    for item in by_topic.values():
        if not item.get("last_checked"):
            item["last_checked"] = date_str
    updated = {
        "project": "personal-intelligence-platform",
        "last_updated": date_str,
        "suppression_days": config.MEMORY_SUPPRESSION_DAYS,
        "topics": sorted(by_topic.values(), key=lambda value: (value.get("category", ""), value.get("topic", ""))),
    }
    save_json(config.MEMORY_FILE, updated)
    return updated


def write_history(
    markdown_body: str,
    raw_items: list[RawItem],
    articles: list[Article],
    events: list[CandidateEvent],
    unchanged: list[CandidateEvent],
    verification_notes: list[dict[str, str]],
    dashboard: list[dict[str, Any]],
    builder: str,
    strategic: str,
    date_str: str,
) -> None:
    config.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    (config.HISTORY_DIR / f"{date_str}.md").write_text(markdown_body, encoding="utf-8")
    save_json(
        config.HISTORY_DIR / f"{date_str}.json",
        {
            "date": date_str,
            "generated_at": now_ist().isoformat(),
            "raw_items": [dataclasses.asdict(item) for item in raw_items],
            "articles": [dataclasses.asdict(article) for article in articles],
            "events": [dataclasses.asdict(event) | {"final_score": round(event.final_score, 2)} for event in events],
            "unchanged_watchlist_items": [dataclasses.asdict(event) for event in unchanged],
            "verification_notes": verification_notes,
            "coverage_dashboard": dashboard,
            "what_i_probably_missed_today": probably_missed_today(verification_notes),
            "builder_brief": builder,
            "strategic_brief": strategic,
        },
    )


def run(dry_run: bool = False, skip_email: bool = False) -> int:
    config.validate(require_email=not (dry_run or skip_email))
    date_str = now_ist().strftime("%Y-%m-%d")
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    sources = load_sources()
    watchlist = load_yaml(config.WATCHLIST_FILE)
    memory = load_json(config.MEMORY_FILE, {"topics": []})

    raw_items = source_scouting(sources)
    articles = content_extraction(raw_items)
    candidates = candidate_event_creation(client, articles, watchlist, date_str)
    verified, verification_notes = critical_event_verification(client, candidates, date_str)
    compared = memory_comparison(verified, memory, watchlist, date_str)
    beat_fallback_events, beat_notes, initial_dashboard = beat_coverage_verification(client, compared, date_str)
    if beat_fallback_events:
        beat_compared = memory_comparison(beat_fallback_events, memory, watchlist, date_str)
        compared = dedupe_events(compared + beat_compared)
    verification_notes.extend(beat_notes)
    dashboard = coverage_dashboard(compared) if beat_fallback_events else initial_dashboard
    selected, unchanged = rank_and_deduplicate(compared)

    if not selected:
        logger.warning("No reportable events survived ranking; report will rely on verification notes.")

    builder, strategic, combined = report_generation(client, selected, unchanged, verification_notes, dashboard, date_str)
    write_history(combined, raw_items, articles, selected, unchanged, verification_notes, dashboard, builder, strategic, date_str)
    if not skip_email:
        email_delivery(combined, date_str, dry_run)
    memory_update(memory, selected, date_str)
    logger.info("Completed daily run for %s", date_str)
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate source-driven daily intelligence briefs.")
    parser.add_argument("--dry-run", action="store_true", help="Run pipeline without sending email.")
    parser.add_argument("--skip-email", action="store_true", help="Generate reports and update memory without sending email.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = parse_args(argv or sys.argv[1:])
    try:
        return run(dry_run=args.dry_run, skip_email=args.skip_email)
    except Exception:
        logger.exception("Pipeline failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
