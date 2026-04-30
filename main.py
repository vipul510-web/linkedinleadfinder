#!/usr/bin/env python3
"""
LinkedIn Lead Finder - Finds leads from LinkedIn posts and sends to email.

Uses Apify's LinkedIn Posts Search Scraper (free tier compatible).
Uses OpenAI to accurately classify leads vs builders/promoters when API key is set.
"""

from datetime import datetime, timedelta, timezone
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from apify_client import ApifyClient
from openai import OpenAI

from config import (
    APIFY_ACTOR,
    APIFY_TOKEN,
    DATE_FILTER,
    EMAIL_TO,
    FREE_TIER_MAX_KEYWORDS,
    FREE_TIER_MAX_POSTS_PER_KEYWORD,
    INCLUDE_POST_IF_DATE_MISSING,
    LEAD_INDICATORS,
    NICHE_CONTEXT,
    OPENAI_API_KEY,
    POST_MATCH_PHRASES,
    RECENT_POST_MAX_HOURS,
    SEARCH_KEYWORDS,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)


def run_apify_scraper(keywords: list[str], max_posts: int = 50) -> list[dict]:
    """Run the LinkedIn post search scraper on Apify."""
    if not APIFY_TOKEN:
        raise ValueError("APIFY_TOKEN not set. Add it to your .env file.")

    # Enforce free tier limits
    keywords = keywords[:FREE_TIER_MAX_KEYWORDS]
    max_posts = min(max_posts, FREE_TIER_MAX_POSTS_PER_KEYWORD)

    client = ApifyClient(APIFY_TOKEN)

    run_input = {
        "keywords": keywords,
        "max_posts": max_posts,
        "sort_by": "date_posted",
        "date_filter": DATE_FILTER,
    }

    print(
        f"Running scraper for keywords: {keywords} "
        f"(max {max_posts} posts each, date_filter={DATE_FILTER})..."
    )
    run = client.actor(APIFY_ACTOR).call(run_input=run_input)

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"Scraped {len(items)} posts total.")
    return items


def is_lead_post(post: dict) -> bool:
    """Keyword fallback: niche phrase + buyer-intent phrases."""
    text = _raw_post_text(post).lower()
    if not text or len(text) < 20:
        return False
    if not matched_niche_phrases(post):
        return False
    return any(indicator in text for indicator in LEAD_INDICATORS)


def filter_leads_keyword(posts: list[dict]) -> list[dict]:
    """Filter posts using keyword matching (fallback when no OpenAI key)."""
    return [p for p in posts if is_lead_post(p)]


def _raw_post_text(post: dict) -> str:
    """Full post text from Apify payload."""
    return (
        post.get("text")
        or post.get("post_text")
        or post.get("postText")
        or post.get("content")
        or ""
    )


def parse_post_datetime(post: dict) -> datetime | None:
    """Best-effort UTC datetime from common Apify / LinkedIn payload keys."""
    candidates = []
    for key in (
        "postedAt",
        "posted_at",
        "publishedAt",
        "published_at",
        "timestamp",
        "createdAt",
        "created_at",
        "datePosted",
        "post_timestamp",
        "timePosted",
    ):
        val = post.get(key)
        if val is None and isinstance(post.get("metadata"), dict):
            val = post["metadata"].get(key)
        if val is None:
            continue
        candidates.append(val)

    for val in candidates:
        if isinstance(val, (int, float)):
            ts = float(val)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(val, str):
            s = val.strip().replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
    return None


def filter_posts_by_recency(posts: list[dict], max_hours: int) -> list[dict]:
    """
    Keep posts newer than max_hours (based on parsed timestamps).
    LinkedIn search API does not offer sub-24h filters; use past-24h + this filter.
    """
    if max_hours <= 0:
        return posts

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)
    kept: list[dict] = []
    missing_ts = 0

    for p in posts:
        dt = parse_post_datetime(p)
        if dt is None:
            missing_ts += 1
            if INCLUDE_POST_IF_DATE_MISSING:
                kept.append(p)
            continue
        if dt >= cutoff:
            kept.append(p)

    print(
        f"Recency filter (last {max_hours}h): {len(kept)} posts kept "
        f"({missing_ts} without parseable timestamp)."
    )
    if missing_ts and not INCLUDE_POST_IF_DATE_MISSING:
        print(
            "Tip: If nothing passes the window, Apify may omit timestamps — "
            "set INCLUDE_POST_IF_DATE_MISSING=true in .env or disable RECENT_POST_MAX_HOURS."
        )

    return kept


def matched_niche_phrases(post: dict) -> list[str]:
    """Which POST_MATCH_PHRASES appear in the post (lowercase substring)."""
    body = _raw_post_text(post).lower()
    return [p for p in POST_MATCH_PHRASES if p.lower() in body]


def filter_posts_by_niche_phrases(posts: list[dict]) -> list[dict]:
    """Keep posts that contain at least one configured niche phrase."""
    kept = [p for p in posts if matched_niche_phrases(p)]
    print(
        f"After niche phrase filter: {len(kept)} posts "
        f"(must match one of {len(POST_MATCH_PHRASES)} phrases)."
    )
    return kept


def _get_post_text(post: dict) -> str:
    """Extract text from post, truncated for LLM."""
    text = _raw_post_text(post)
    return text[:800] if text else ""  # Limit tokens


def filter_leads_llm(posts: list[dict], batch_size: int = 15) -> list[dict]:
    """
    Use OpenAI to classify posts: lead (seeking solution) vs not lead (building/promoting).
    Posts should already be narrowed by niche phrase match on the post body.
    """
    if not OPENAI_API_KEY:
        return filter_leads_keyword(posts)

    client = OpenAI()
    leads = []

    for i in range(0, len(posts), batch_size):
        batch = posts[i : i + batch_size]
        batch_texts = [
            f"[{j+1}] {_get_post_text(p)}" for j, p in enumerate(batch)
        ]
        posts_block = "\n\n".join(batch_texts)

        prompt = f"""You are a lead qualification expert for B2B SaaS / developer tools.

{NICHE_CONTEXT}

Classify each numbered post below.

LEAD (is_lead: true) = The author is LOOKING FOR a solution as a buyer/user: asking how to do something, requesting tools/vendors/APIs, comparing alternatives, unhappy with current provider cost (seeking switch), hiring help, learning path for integration—not selling.

NOT A LEAD (is_lead: false) = Selling or promoting their own product/service, launch announcements, case studies for clients, thought leadership to attract inbound, recruiting engineers for their startup's product, generic engagement bait without a buying question.

Examples of LEADS:
- "What's the best WhatsApp Business API alternative to Twilio? Pricing is killing us."
- "Need to send WhatsApp from Python—webhook vs official API?"
- "Anyone moved off Wati? Looking for recommendations."
- "How do we set up WhatsApp Business API webhooks for lead capture?"

Examples of NOT LEADS:
- "We built a WhatsApp automation platform—DM for demo."
- "10 tips for WhatsApp marketing (link to our course)."
- "Excited to announce our integration with WhatsApp API."

Respond with JSON ONLY: {{"results": [{{"id": 1, "is_lead": false}}, ...]}}
You MUST include one object per post, with ids 1 through N matching the post numbers [1] through [N]."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Posts to classify:\n\n{posts_block}"},
                ],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            results = {}
            for r in data.get("results", []):
                try:
                    results[int(r["id"])] = bool(r.get("is_lead"))
                except (KeyError, TypeError, ValueError):
                    continue
            for j, post in enumerate(batch):
                if results.get(j + 1, False):
                    leads.append(post)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"LLM parse error for batch: {e}, skipping batch")
        except Exception as e:
            print(f"OpenAI API error: {e}, falling back to keyword filter for batch")
            leads.extend(p for p in batch if is_lead_post(p))

    return leads


def format_post_for_email(post: dict) -> str:
    """Format a single post for the email body."""
    text = (
        post.get("text")
        or post.get("post_text")
        or post.get("postText")
        or post.get("content")
        or "(No text)"
    )
    author = post.get("author") or {}
    if isinstance(author, dict):
        name = author.get("name") or author.get("fullName") or "Unknown"
        headline = author.get("headline") or ""
        profile_url = author.get("profileUrl") or author.get("url") or ""
    else:
        name = str(author)
        headline = ""
        profile_url = ""

    post_url = post.get("url") or post.get("postUrl") or post.get("post_url") or ""

    # Truncate long posts
    if len(text) > 500:
        text = text[:497] + "..."

    link_line = f"Post: {post_url}\n" if post_url else ""
    return f"""
---
👤 {name}
{headline}
{profile_url}
{link_line}
📝 Content:
{text}
"""


def parse_email_recipients(raw: str | None) -> list[str]:
    """Split comma/semicolon-separated addresses; strip whitespace and stray newlines."""
    if not raw or not raw.strip():
        return []
    normalized = raw.replace("\n", ",").replace("\r", ",")
    out = []
    for part in normalized.replace(";", ",").split(","):
        addr = part.strip()
        if addr:
            out.append(addr)
    return out


def send_email(subject: str, body: str) -> None:
    """Send an email with the leads (supports multiple comma-separated recipients)."""
    recipients = parse_email_recipients(EMAIL_TO)
    if not all([SMTP_USER, SMTP_PASSWORD]) or not recipients:
        print("Email not configured. Set SMTP_USER, SMTP_PASSWORD, EMAIL_TO in .env")
        return

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, recipients, msg.as_string())

    print(f"Email sent to {', '.join(recipients)}")


def main(keywords: list[str] | None = None):
    """Main entry point."""
    # Use config keywords if none passed via CLI
    keywords = keywords or SEARCH_KEYWORDS

    # Run scraper
    posts = run_apify_scraper(keywords)

    if not posts:
        print("No posts found. Try different keywords or check Apify credits.")
        return

    posts = filter_posts_by_recency(posts, RECENT_POST_MAX_HOURS)
    if not posts:
        print("No posts after recency filter.")
        send_email(
            subject="LinkedIn Leads: No posts in recency window",
            body=(
                f"No posts matched the last {RECENT_POST_MAX_HOURS}-hour window "
                f"(or timestamps missing — see INCLUDE_POST_IF_DATE_MISSING)."
            ),
        )
        return

    posts = filter_posts_by_niche_phrases(posts)
    if not posts:
        print("No posts matched your niche phrase list (POST_MATCH_PHRASES).")
        send_email(
            subject="LinkedIn Leads: No posts matched niche phrases",
            body=(
                "Scraper returned posts but none contained any phrase from "
                "POST_MATCH_PHRASES in config.py. Broaden phrases or SEARCH_KEYWORDS."
            ),
        )
        return

    # Filter for leads (LLM when available, else keyword fallback)
    if OPENAI_API_KEY:
        print("Using OpenAI to classify leads (seeking vs building/promoting)...")
        leads = filter_leads_llm(posts)
    else:
        print("Using keyword filter (set OPENAI_API_KEY for more accurate LLM classification)...")
        leads = filter_leads_keyword(posts)
    print(f"Found {len(leads)} qualified leads.")

    # Build email
    if leads:
        body = f"LinkedIn Lead Finder - {len(leads)} new leads\n"
        body += "=" * 50 + "\n"
        for i, lead in enumerate(leads[:25], 1):  # Cap at 25 in email
            phrases = matched_niche_phrases(lead)
            match_line = f"\nMatched phrases: {', '.join(phrases)}\n" if phrases else ""
            body += f"\n--- Lead #{i} ---{match_line}"
            body += format_post_for_email(lead)
        if len(leads) > 25:
            body += f"\n... and {len(leads) - 25} more leads (run locally to see all).\n"

        send_email(
            subject=f"LinkedIn Leads: {len(leads)} new leads found",
            body=body,
        )
    else:
        body = (
            f"LinkedIn Lead Finder ran successfully.\n\n"
            f"Scraped {len(posts)} posts but none qualified as leads.\n"
            f"If using keyword filter, try config.LEAD_INDICATORS. "
            f"If using LLM, the posts may have been builders/promoters."
        )
        send_email(
            subject="LinkedIn Leads: No leads found this run",
            body=body,
        )


if __name__ == "__main__":
    import sys

    # Pass custom keywords as args: python main.py "keyword1" "keyword2"
    keywords = sys.argv[1:] if len(sys.argv) > 1 else None
    main(keywords)
