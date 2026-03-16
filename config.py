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

# Topics to search for leads (LinkedIn search keywords)
# Free tier allows max 4 keywords per run
SEARCH_KEYWORDS = [
    "AI Voice agents",
    "WhatsApp automation",
]

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
