# LinkedIn Lead Finder

Finds leads from LinkedIn posts where people are looking for solutions, using Apify's free tier. Sends results to your email.

## How It Works

1. **Searches** LinkedIn posts by keywords (e.g. "looking for recommendations", "need help with")
2. **Filters** for posts that indicate someone is seeking a solution (lead indicators)
3. **Emails** you the results with author info and post links

## Free Tier Limits (Apify)

- **$5/month** in platform credits (no credit card required)
- **4 keywords** per run, max **50 posts** per keyword
- ~**200 posts per run** within free limits
- At ~$1.20/1,000 posts: ~4,000 posts/month on free tier

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

### GitHub Actions (daily run)

A workflow runs automatically every day at 9:00 AM UTC. Add these secrets in your repo:

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Required | Description |
|--------|----------|-------------|
| `APIFY_TOKEN` | Yes | Your Apify API token |
| `SMTP_USER` | Yes | Sender email (e.g. your@gmail.com) |
| `SMTP_PASSWORD` | Yes | Gmail App Password or SMTP password |
| `EMAIL_TO` | Yes | Where to send leads |
| `SMTP_HOST` | No | Default: smtp.gmail.com |
| `SMTP_PORT` | No | Default: 587 |

You can also trigger a run manually: **Actions → LinkedIn Lead Finder → Run workflow**.

### Schedule locally (optional)

Run daily via cron:

```bash
crontab -e
# Add: 0 9 * * * cd /path/to/Linkedinscrapper && .venv/bin/python3 main.py
```

## Customize Lead Indicators

Edit `config.py` and modify `LEAD_INDICATORS` to match phrases that signal someone is looking for help:

```python
LEAD_INDICATORS = [
    "looking for",
    "need help",
    "recommendations for",
    # Add your own...
]
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "APIFY_TOKEN not set" | Add token to `.env` |
| Email not sending | Use Gmail App Password, not regular password |
| No leads found | Try different keywords or add more indicators in config |
| Apify credits exhausted | Wait for monthly reset or upgrade plan |
