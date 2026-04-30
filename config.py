"""Configuration for LinkedIn Lead Finder."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")

# Apify
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_ACTOR = "datadoping/linkedin-posts-search-scraper"

# Free tier limits (datadoping actor)
FREE_TIER_MAX_KEYWORDS = 4
FREE_TIER_MAX_POSTS_PER_KEYWORD = 50

# Apify LinkedIn search date filter (actor enum only — no "past 2 hours").
# Use past-24h when combining with RECENT_POST_MAX_HOURS below.
DATE_FILTER = os.getenv("DATE_FILTER") or "past-24h"

# Keep posts newer than this many hours (parsed from Apify timestamps).
# Set 0 to disable client-side recency filter.
RECENT_POST_MAX_HOURS = int(os.getenv("RECENT_POST_MAX_HOURS") or "2")

# If True, posts without a parseable timestamp still pass the recency filter.
INCLUDE_POST_IF_DATE_MISSING = os.getenv(
    "INCLUDE_POST_IF_DATE_MISSING", ""
).lower() in ("1", "true", "yes")

# LinkedIn search keywords for Apify (max 4 per run on free tier).
# Pick diverse queries; rotate or edit between runs to cover more angles.
SEARCH_KEYWORDS = [
    "whatsapp business api",
    "whatsapp automation",
    "whatsapp api",
    "wati alternative",
]

# Post body must contain at least one phrase (case-insensitive substring).
# Fine-tunes relevance to WhatsApp automation / API / tooling intent.
POST_MATCH_PHRASES = [
    "whatsapp api",
    "whatsapp mcp",
    "whatsapp cursor",
    "whatsapp claude code",
    "whatsapp codex",
    "whatsapp lovable",
    "twilio whatsapp",
    "twilio expensive",
    "whatsapp business api developer",
    "whatsapp webhook",
    "whatsapp node js",
    "whatsapp python",
    "how to send whatsapp from",
    "whatsapp api alternative",
    "whatsapp form",
    "whatsapp survey",
    "whatsapp lead capture",
    "whatsapp drip",
    "whatsapp business api setup",
    "whatsapp business api cost",
    "wati alternative",
    "wati pricing",
    "aisensy alternative",
]

# Short context injected into the LLM prompt (buyer vs seller for this niche)
NICHE_CONTEXT = (
    "Niche: WhatsApp automation, WhatsApp Business API, webhooks, messaging builders, "
    "alternatives to Twilio/Wati/AISensy, developers integrating WhatsApp from Node/Python."
)

# Email (empty env vars fall back to Gmail defaults)
SMTP_HOST = os.getenv("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.getenv("SMTP_PORT") or "587")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

# OpenAI - when set, uses LLM to classify leads (much more accurate than keyword filter)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Lead filter keywords - fallback when OPENAI_API_KEY not set (less accurate)
LEAD_INDICATORS = [
    "looking for",
    "need help",
    "need a",
    "recommendations for",
    "suggestions for",
    "anyone know",
    "can anyone recommend",
    "searching for",
    "in the market for",
    "would love to find",
]
