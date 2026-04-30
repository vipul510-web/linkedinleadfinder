# LinkedIn Lead Finder

Finds leads from LinkedIn posts where people are looking for solutions, using Apify's free tier. Sends results to your email.

## How It Works

1. **Searches** LinkedIn via Apify using `SEARCH_KEYWORDS` (max 4 per run on free tier).
2. **Niche match:** Keeps posts whose body contains at least one phrase from `POST_MATCH_PHRASES` (case-insensitive substring)— tuned for WhatsApp API / automation intent.
3. **Intent:** With `OPENAI_API_KEY`, an LLM scores buyer intent (looking for a solution) vs seller noise (promoting their own product). Without it, uses `LEAD_INDICATORS` + niche phrases.
4. **Emails** qualified leads; each lead line lists which niche phrases matched.

**Fine-tuning:** Edit `SEARCH_KEYWORDS` for discovery, `POST_MATCH_PHRASES` for post-level relevance, and `NICHE_CONTEXT` / examples in `main.py` for LLM behavior.

## Free Tier Limits (Apify)

- **$5/month** in platform credits (no credit card required)
- **4 keywords** per run, max **50 posts** per keyword
- ~**200 posts per run** within free limits
- At ~$1.20/1,000 posts: ~$5/month caps roughly **thousands** of scraped posts total — budget matters more than GitHub run count.

### How often can you run?

| Constraint | Practical note |
|------------|----------------|
| **GitHub Actions** | Public repos: generous fair-use on scheduled workflows. **Private repos**: included Actions minutes (~2,000 min/month free); each run is ~1–2 minutes (~700–1,400 runs/month budget). |
| **Apify** | Each schedule still runs a full scrape — **cost scales with runs × posts**. Example: **12 runs/day** × ~200 posts ≈ **2,400 posts/day** billed — likely beyond **free $5/month** unless you lower `max_posts` / keywords or upgrade Apify. |
| **LinkedIn date filter** | The actor only supports **`past-24h`**, **`past-week`**, **`past-month`** — there is **no native “past 2 hours.”** |

### Fresh posts (~last 2 hours)

Defaults in `config.py`:

- **`DATE_FILTER`** — use **`past-24h`** (narrowest LinkedIn-side filter).
- **`RECENT_POST_MAX_HOURS`** — **`2`** keeps only posts whose timestamp parses within the last 2 hours (after scrape).

If **nothing passes** the 2-hour window, Apify items may omit usable timestamps. Set **`INCLUDE_POST_IF_DATE_MISSING=true`** in `.env` to keep undated posts (less strict), or set **`RECENT_POST_MAX_HOURS=0`** to turn off client-side recency filtering.

Environment overrides (optional): `DATE_FILTER`, `RECENT_POST_MAX_HOURS`, `INCLUDE_POST_IF_DATE_MISSING`.

## Setup

### 1. Install dependencies

```bash
cd Linkedinscrapper
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get your Apify token

1. Sign up at [apify.com](https://apify.com) (free)
2. Go to [Settings → Integrations](https://console.apify.com/account/integrations)
3. Copy your API token

### 3. Configure email (Gmail)

1. Enable [2-Step Verification](https://myaccount.google.com/security) on your Google account
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Copy the 16-character app password

### 4. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and add:

```
APIFY_TOKEN=apify_api_xxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxx          # For accurate lead classification (recommended)
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
EMAIL_TO=your_email@gmail.com
```

For non-Gmail SMTP, also set:
```
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
```

## Usage

### Run with default keywords

```bash
python main.py
```

Default keywords: `looking for recommendations`, `need help with`, `recommendations for software`

### Run with custom keywords

```bash
python main.py "your niche keyword" "another keyword" "third keyword"
```

Example:
```bash
python main.py "looking for CRM" "need marketing agency" "recommendations for HR software"
```

### GitHub Actions (every 2 hours)

The workflow runs on **`schedule`: every 2 hours UTC** (`0 */2 * * *`) and supports **Run workflow** manually. Add these secrets:

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Required | Description |
|--------|----------|-------------|
| `APIFY_TOKEN` | Yes | Your Apify API token |
| `OPENAI_API_KEY` | Yes* | OpenAI key for lead classification (recommended for accuracy) |
| `SMTP_USER` | Yes | Sender email (e.g. your@gmail.com) |
| `SMTP_PASSWORD` | Yes | Gmail App Password or SMTP password |
| `EMAIL_TO` | Yes | Where to send leads |
| `SMTP_HOST` | No | Default: smtp.gmail.com |
| `SMTP_PORT` | No | Default: 587 |

*Without `OPENAI_API_KEY`, falls back to keyword filter (less accurate—catches builders/promoters).

You can also trigger a run manually: **Actions → LinkedIn Lead Finder → Run workflow**.

### Schedule locally (optional)

Run daily via cron:

```bash
crontab -e
# Add: 0 9 * * * cd /path/to/Linkedinscrapper && .venv/bin/python3 main.py
```

## Customize (`config.py`)

- **`SEARCH_KEYWORDS`** — LinkedIn search queries Apify runs (rotate across runs to cover more angles; free tier = 4 per run).
- **`POST_MATCH_PHRASES`** — Post must contain one of these substrings (exact phrase, case-insensitive).
- **`NICHE_CONTEXT`** — One-line domain hint for the LLM.
- **`LEAD_INDICATORS`** — Fallback buyer-intent keywords when OpenAI is disabled.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "APIFY_TOKEN not set" | Add token to `.env` |
| Email not sending | Use Gmail App Password, not regular password |
| No leads found | Try different keywords; add OPENAI_API_KEY for better filtering |
| Apify credits exhausted | Wait for monthly reset or upgrade plan |
