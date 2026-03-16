#!/usr/bin/env python3
"""
LinkedIn Lead Finder - Finds leads from LinkedIn posts and sends to email.

Uses Apify's LinkedIn Posts Search Scraper (free tier compatible).
Uses OpenAI to accurately classify leads vs builders/promoters when API key is set.
"""

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from apify_client import ApifyClient
from openai import OpenAI

from config import (
    APIFY_ACTOR,
    APIFY_TOKEN,
    EMAIL_TO,
    FREE_TIER_MAX_KEYWORDS,
    FREE_TIER_MAX_POSTS_PER_KEYWORD,
    LEAD_INDICATORS,
    OPENAI_API_KEY,
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
        "date_filter": "past-week",
    }

    print(f"Running scraper for keywords: {keywords} (max {max_posts} posts each)...")
    run = client.actor(APIFY_ACTOR).call(run_input=run_input)

    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"Scraped {len(items)} posts total.")
    return items


def is_lead_post(post: dict) -> bool:
    """Check if a post looks like someone looking for a solution (lead)."""
    text = (
        post.get("text")
        or post.get("post_text")
        or post.get("postText")
        or post.get("content")
        or ""
    ).lower()
    if not text or len(text) < 20:
        return False
    return any(indicator in text for indicator in LEAD_INDICATORS)


def filter_leads_keyword(posts: list[dict]) -> list[dict]:
    """Filter posts using keyword matching (fallback when no OpenAI key)."""
    return [p for p in posts if is_lead_post(p)]


def _get_post_text(post: dict) -> str:
    """Extract text from post, truncated for LLM."""
    text = (
        post.get("text")
        or post.get("post_text")
        or post.get("postText")
        or post.get("content")
        or ""
    )
    return text[:800] if text else ""  # Limit tokens


def filter_leads_llm(posts: list[dict], batch_size: int = 15) -> list[dict]:
    """
    Use OpenAI to classify posts: lead (seeking solution) vs not lead (building/promoting).
    Much more accurate than keyword matching.
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

        prompt = """You are a lead qualification expert. Classify each LinkedIn post below.

LEAD = The person is SEEKING to buy, use, or hire a solution. They want recommendations, help finding a vendor, or are evaluating options.
NOT A LEAD = The person is BUILDING, PROMOTING, or SHARING news about their own product. They're a vendor/seller, not a buyer.

Examples of LEADS:
- "Looking for recommendations for an AI voice agent"
- "Need help choosing a WhatsApp automation tool for our team"
- "Anyone know a good agency for WhatsApp automation?"

Examples of NOT LEADS:
- "We just launched our AI voice agent!"
- "Building an AI voice agent - here's what we learned"
- "Excited to share our new WhatsApp automation product"

For each post, respond with a JSON object: {"results": [{"id": 1, "is_lead": true/false}, ...]}
Use the [1], [2], etc. numbers as ids. Only include posts that are clearly LEADS."""

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
            results = {r["id"]: r["is_lead"] for r in data.get("results", [])}
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


def send_email(subject: str, body: str) -> None:
    """Send an email with the leads."""
    if not all([SMTP_USER, SMTP_PASSWORD, EMAIL_TO]):
        print("Email not configured. Set SMTP_USER, SMTP_PASSWORD, EMAIL_TO in .env")
        return

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())

    print(f"Email sent to {EMAIL_TO}")


def main(keywords: list[str] | None = None):
    """Main entry point."""
    # Use config keywords if none passed via CLI
    keywords = keywords or SEARCH_KEYWORDS

    # Run scraper
    posts = run_apify_scraper(keywords)

    if not posts:
        print("No posts found. Try different keywords or check Apify credits.")
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
            body += f"\n--- Lead #{i} ---"
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
