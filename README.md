# বাংলা নিউজ বট — Automated Bangla Political News Platform

A fully automated pipeline that monitors English political news sources, filters for importance, deduplicates, and rewrites into professional Bangla journalism — all for free.

---

## Project Structure

```
bangla-news-bot/
├── main.py                       ← Master orchestration script
├── requirements.txt
├── .env.example                  ← Copy to .env and fill in keys
├── .gitignore
├── pipeline/
│   ├── sources.py                ← RSS feed URLs + keyword weights
│   ├── ingest.py                 ← Fetch and normalise all feeds
│   ├── filter.py                 ← 3-stage importance + dedup filter
│   ├── rewrite.py                ← Groq AI → Bangla journalism
│   ├── storage.py                ← SQLite or Google Sheets backend
│   └── publish.py                ← Telegram publishing (optional)
├── tests/
│   └── test_setup.py             ← Smoke tests to verify setup
└── .github/
    └── workflows/
        └── pipeline.yml          ← GitHub Actions cron job (every 5 min)
```

---

## Step-by-Step Setup Guide

### Step 1: Get your free API keys

You need two keys to run the pipeline. Get them now before anything else.

**Groq API key (required — for Bangla rewriting)**
1. Go to https://console.groq.com
2. Sign up with Google or email (free, no credit card)
3. Click "API Keys" in the left sidebar
4. Click "Create API Key" — name it "bangla-news-bot"
5. Copy and save the key immediately (shown only once)

**HuggingFace token (recommended — for zero-shot classification)**
1. Go to https://huggingface.co/join
2. Create a free account
3. Go to Settings → Access Tokens → New Token
4. Name it "bangla-news-bot", role: "read"
5. Copy and save the token

---

### Step 2: Set up the GitHub repository

1. Create a new repository at https://github.com/new
   - Name: `bangla-news-bot`
   - Visibility: **Public** (required for free GitHub Actions)
   - Do NOT initialise with README (you'll push existing code)

2. Clone the repository to your local machine:
   ```bash
   git clone https://github.com/YOUR_USERNAME/bangla-news-bot.git
   cd bangla-news-bot
   ```

3. Copy all the project files into this folder, then push:
   ```bash
   git add .
   git commit -m "Initial pipeline setup"
   git push origin main
   ```

---

### Step 3: Add secrets to GitHub

Your API keys must be stored as GitHub Secrets, not in code.

1. Go to your repo on GitHub → Settings → Secrets and variables → Actions
2. Click "New repository secret" for each of the following:

| Secret Name | Value | Where to get it |
|-------------|-------|----------------|
| `GROQ_API_KEY` | Your Groq key | console.groq.com |
| `HF_API_TOKEN` | Your HuggingFace token | huggingface.co/settings/tokens |
| `TELEGRAM_BOT_TOKEN` | Bot token (optional) | @BotFather on Telegram |
| `TELEGRAM_CHANNEL_ID` | Channel ID (optional) | See Telegram setup below |

For variables (non-sensitive config), go to **Variables** tab:

| Variable Name | Default | Purpose |
|---------------|---------|---------|
| `STORAGE_MODE` | `sqlite` | `sqlite` or `sheets` |
| `IMPORTANCE_SCORE_THRESHOLD` | `3.0` | Lower = more articles pass |
| `DEDUP_SIMILARITY_THRESHOLD` | `0.85` | Lower = more duplicates allowed |

---

### Step 4: Test locally before deploying

```bash
# Install Python 3.11+ if you don't have it
python --version  # Should be 3.11+

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file and fill in your keys
cp .env.example .env
# Open .env in your editor and add your API keys

# Run smoke tests
python tests/test_setup.py
```

All tests should pass before you continue. Fix any failures before deploying.

---

### Step 5: Run the pipeline manually (first run)

```bash
python main.py
```

Watch the output. You should see:
```
Step 1: Fetching RSS feeds...
  Fetched: 180 total articles
Step 2: Filtering already-seen URLs...
  New (unseen): 180 articles
Step 3: Running filter pipeline...
  Stage 1 (keyword): 24/180 passed
  Stage 2 (zero-shot): 18/24 passed
  Stage 3 (dedup): 14/18 passed
  Passed filters: 14 articles
Step 4: Loading recent stories for context...
Step 5: Rewriting articles into Bangla...
  Rewriting 1/14: BREAKING: Prime Minister...
  ...
Step 6: Saving output stories...
```

Your first run will produce the most results since nothing is seen yet. Subsequent runs will only process truly new articles.

---

### Step 6: Review your first outputs

**If using SQLite (default):**
```bash
# Install a SQLite viewer, or use the command line:
sqlite3 news_pipeline.sqlite

# See what was generated:
.mode column
.headers on
SELECT timestamp, source, headline FROM output_stories ORDER BY timestamp DESC LIMIT 10;

# See the full Bangla story for one article:
SELECT headline, caption, story FROM output_stories LIMIT 1;

.quit
```

**If using Google Sheets:** Open the spreadsheet and check the "Output" tab.

Manually review 5–10 entries. Ask yourself:
- Is the Bangla natural and journalist-sounding?
- Are the stories genuinely newsworthy?
- Any obvious duplicates slipping through?

---

### Step 7: Enable the automated scheduler

The GitHub Actions workflow is already configured. Once you push to GitHub:

1. Go to your repo → Actions tab
2. Click "Bangla News Pipeline" in the left sidebar
3. Click "Run workflow" → "Run workflow" to trigger a manual test run
4. Watch it execute in the browser

If it runs successfully, the cron schedule (`*/5 * * * *`) will fire automatically every 5 minutes.

**Note:** GitHub may delay the very first scheduled run by up to 15 minutes. This is normal.

---

### Step 8: (Optional) Set up Telegram publishing

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow instructions to create your bot
3. Copy the bot token shown (format: `1234567890:ABCdefGHI...`)
4. Create a new Telegram channel (or use an existing one)
5. Add your bot as an Administrator of the channel
6. Get your channel ID:
   - Forward any message from your channel to `@userinfobot`
   - It will show you the channel ID (format: `-1001234567890`)
7. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL_ID` as GitHub Secrets

Once both secrets are set, the pipeline will automatically post to your channel.

---

### Step 9: (Optional) Switch to Google Sheets storage

Google Sheets is better than SQLite if you want to:
- Review and edit output stories easily
- Share the data with collaborators
- Build a simple dashboard

**Setup:**
1. Go to https://console.cloud.google.com
2. Create a new project → Enable Google Sheets API + Google Drive API
3. Go to IAM → Service Accounts → Create Service Account
4. Download the JSON key file
5. Create a new Google Spreadsheet and share it with the service account's email address (give Editor access)
6. Copy the Spreadsheet ID from the URL (the long string between `/d/` and `/edit`)

**Configure:**
- Add the service account JSON content as a GitHub Secret named `GOOGLE_CREDENTIALS_JSON`
- Set `STORAGE_MODE` variable to `sheets`
- Set `GOOGLE_SHEET_ID` secret to your spreadsheet ID

---

## Tuning Your Filters

After running for a few days, you'll want to adjust thresholds:

**Too many irrelevant articles passing through?**
- Increase `IMPORTANCE_SCORE_THRESHOLD` from 3.0 to 4.0 or 5.0
- Increase `HF_CLASSIFICATION_THRESHOLD` from 0.55 to 0.65

**Missing important stories?**
- Decrease `IMPORTANCE_SCORE_THRESHOLD` to 2.0
- Add more keywords to `KEYWORD_WEIGHTS` in `pipeline/sources.py`
- Add more RSS feeds for South Asia coverage in `RSS_SOURCES`

**Too many near-duplicate stories?**
- Decrease `DEDUP_SIMILARITY_THRESHOLD` from 0.85 to 0.75

**Bangla quality issues?**
- Edit the `SYSTEM_PROMPT` in `pipeline/rewrite.py`
- Add specific instructions for tone, vocabulary, or formatting

---

## Cost Summary

| Component | Free limit | Your usage |
|-----------|-----------|------------|
| GitHub Actions | 2,000 min/month (public repo: unlimited) | ~8 min/run × 288 runs/day = well within free |
| Groq API | 30 req/min, ~14,400/day | Max ~50 req/run × 288 = 14,400/day (tight but OK) |
| HuggingFace | ~30 req/min Inference API | ~5-25 req/run = fine |
| Google Sheets API | 300 reads/min, 60 writes/min | Well within limits |
| SQLite | Unlimited | Free forever |

**Total monthly cost: $0**

---

## Daily Quality Review Checklist

Spend 5 minutes each morning reviewing 10 random output stories:

- [ ] Are the Bangla headlines punchy and clear?
- [ ] Does the caption work as a standalone social post?
- [ ] Are proper nouns (country names, people) correctly transliterated?
- [ ] Does the story have good context and flow?
- [ ] Any fabricated details not in the source?
- [ ] Any stories that clearly shouldn't have passed the importance filter?

Log your findings in a simple notes file and adjust thresholds accordingly.
