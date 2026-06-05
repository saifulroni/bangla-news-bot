"""
RSS feed sources for political news.
Each source has a name, URL, tier (1=highest weight), and optional tags.
"""

RSS_SOURCES = [
    # ── Tier 1: Wire services (highest importance weight) ──────────────────
    {
        "name": "Reuters Top News",
        "url": "https://feeds.reuters.com/reuters/topNews",
        "tier": 1,
        "tags": ["wire", "breaking"],
    },
    {
        "name": "Reuters Politics",
        "url": "https://feeds.reuters.com/Reuters/PoliticsNews",
        "tier": 1,
        "tags": ["wire", "politics"],
    },
    {
        "name": "AP News Top Headlines",
        "url": "https://feeds.apnews.com/rss/topnews",
        "tier": 1,
        "tags": ["wire", "breaking"],
    },

    # ── Tier 2: Major international outlets ────────────────────────────────
    {
        "name": "BBC World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "tier": 2,
        "tags": ["outlet"],
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "tier": 2,
        "tags": ["outlet", "global-south"],
    },
    {
        "name": "NYT Politics",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
        "tier": 2,
        "tags": ["outlet", "politics"],
    },
    {
        "name": "CNN Top Stories",
        "url": "http://rss.cnn.com/rss/edition.rss",
        "tier": 2,
        "tags": ["outlet"],
    },
    {
        "name": "The Guardian World",
        "url": "https://www.theguardian.com/world/rss",
        "tier": 2,
        "tags": ["outlet"],
    },

    # ── Tier 3: Google News keyword feeds (broadest coverage) ─────────────
    {
        "name": "Google News – Breaking Politics",
        "url": "https://news.google.com/rss/search?q=breaking+politics&hl=en-US&gl=US&ceid=US:en",
        "tier": 2,
        "tags": ["aggregator", "politics"],
    },
    {
        "name": "Google News – World Politics",
        "url": "https://news.google.com/rss/search?q=world+politics+crisis&hl=en-US&gl=US&ceid=US:en",
        "tier": 2,
        "tags": ["aggregator", "politics"],
    },
    {
        "name": "Google News – Bangladesh",
        "url": "https://news.google.com/rss/search?q=Bangladesh+politics&hl=en-US&gl=US&ceid=US:en",
        "tier": 2,
        "tags": ["aggregator", "bangladesh"],
    },
    {
        "name": "Google News – South Asia Politics",
        "url": "https://news.google.com/rss/search?q=South+Asia+political+crisis&hl=en-US&gl=US&ceid=US:en",
        "tier": 2,
        "tags": ["aggregator", "south-asia"],
    },
]

# ── Breaking news keywords with score weights ──────────────────────────────
KEYWORD_WEIGHTS = {
    # Highest urgency
    "breaking": 3.0,
    "urgent": 3.0,
    "just in": 3.0,
    "breaking news": 3.0,
    "developing": 2.5,
    "flash": 2.5,

    # Political events
    "coup": 4.0,
    "assassination": 4.0,
    "resign": 3.5,
    "resigns": 3.5,
    "resignation": 3.5,
    "election": 3.0,
    "protest": 2.5,
    "protests": 2.5,
    "crisis": 2.5,
    "emergency": 3.0,
    "war": 3.5,
    "ceasefire": 3.5,
    "sanctions": 2.5,
    "impeach": 3.5,
    "arrested": 2.0,
    "detained": 2.0,
    "killed": 2.5,
    "attack": 2.5,
    "bombing": 3.0,
    "summit": 2.0,
    "treaty": 2.5,
    "parliament": 2.0,
    "minister": 1.5,
    "government": 1.0,
    "opposition": 1.5,
    "military": 2.0,
    "revolt": 3.0,
    "uprising": 3.0,
}

# ── Source tier score bonuses ──────────────────────────────────────────────
TIER_BONUSES = {
    1: 3.0,   # Wire services
    2: 1.5,   # Major outlets / Google News
    3: 0.5,   # Other sources
}
