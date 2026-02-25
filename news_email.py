import os          # To read environment variables (email + password)
import ssl         # To create a secure connection to Gmail
import smtplib     # To send email via Gmail's SMTP server
import datetime    # To get today's date for the email subject
import re          # To strip HTML tags from summaries

# ── Third-party import (install with: pip install feedparser) ──
import feedparser  # Parses RSS/Atom feeds from news websites


# ──────────────────────────────────────────────────────────────
#  CONFIGURATION — edit these values to customize your bot
# ──────────────────────────────────────────────────────────────

# News sources (RSS feed URLs)
RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/worldNews",       # Reuters World News
    "http://feeds.bbci.co.uk/news/world/rss.xml",        # BBC World News
    "https://www.bloomberg.com/feed/podcast/etf-report.xml",  # Bloomberg
    "https://www.economist.com/international/rss.xml",   # The Economist
]

# Keywords used to score how "important" a headline is.
# The more of these words appear in a title, the higher it ranks.
IMPORTANCE_KEYWORDS = [
    "war", "china", "us", "economy", "ai", "market",
    "election", "oil", "inflation", "tech", "crisis",
    "nuclear", "climate", "sanctions", "trade", "recession",
]

# How many top stories to include in the email
TOP_N_STORIES = 5

# Maximum number of characters to show from each story's summary
SUMMARY_MAX_LENGTH = 250


# ──────────────────────────────────────────────────────────────
#  STEP 1 — Fetch news from all RSS feeds
# ──────────────────────────────────────────────────────────────

def fetch_all_news():
    """
    Loops through every RSS feed URL, downloads the feed,
    and collects individual news stories into one big list.

    Each story is stored as a dictionary with:
      - title     : the headline
      - summary   : a short description (may contain HTML)
      - published : when the story was published (string)
      - source    : which feed it came from
      - score     : importance score (calculated below)
    """
    all_stories = []

    for feed_url in RSS_FEEDS:
        print(f"  Fetching: {feed_url}")

        # feedparser.parse() downloads + parses the RSS XML for us
        feed = feedparser.parse(feed_url)

        # Take the first 15 entries from each feed
        # (RSS feeds usually list newest stories first)
        for entry in feed.entries[:15]:
            title     = entry.get("title", "No title")
            summary   = entry.get("summary", "")
            published = entry.get("published", "")
            source    = feed.feed.get("title", feed_url)

            # Calculate an importance score for this story
            score = calculate_importance_score(title, summary)

            all_stories.append({
                "title":     title,
                "summary":   summary,
                "published": published,
                "source":    source,
                "score":     score,
            })

    return all_stories


# ──────────────────────────────────────────────────────────────
#  STEP 2 — Score each story by importance
# ──────────────────────────────────────────────────────────────

def calculate_importance_score(title, summary):
    """
    Assigns a numeric importance score to a news story.

    Scoring logic (no AI needed!):
      +2 points  for each keyword found in the title
                 (title keywords matter more than summary ones)
      +1 point   for each keyword found in the summary
      +0.5 point bonus if the title contains a number
                 (e.g. "3 killed", "$1 billion deal" → often breaking news)

    The more keywords match, the higher the score.
    Stories are later sorted from highest to lowest score.
    """
    score = 0
    title_lower   = title.lower()
    summary_lower = summary.lower()

    for keyword in IMPORTANCE_KEYWORDS:
        if keyword in title_lower:
            score += 2   # Title match is worth more
        if keyword in summary_lower:
            score += 1   # Summary match adds a little

    # Bonus: headlines with numbers tend to be specific/breaking
    if re.search(r'\d', title):
        score += 0.5

    return score


# ──────────────────────────────────────────────────────────────
#  STEP 3 — Pick the top N stories
# ──────────────────────────────────────────────────────────────

def pick_top_stories(all_stories, n=TOP_N_STORIES):
    """
    Sorts stories by their importance score (highest first),
    then returns only the top N.

    We also deduplicate: if the same headline appears from
    multiple sources, we only keep the first occurrence.
    """
    # Remove near-duplicate headlines (same first 60 characters)
    seen_titles = set()
    unique_stories = []

    for story in all_stories:
        # Use first 60 chars as a "fingerprint" for the headline
        fingerprint = story["title"][:60].lower().strip()
        if fingerprint not in seen_titles:
            seen_titles.add(fingerprint)
            unique_stories.append(story)

    # Sort by score, highest first
    unique_stories.sort(key=lambda s: s["score"], reverse=True)

    # Return only the top N
    return unique_stories[:n]


# ──────────────────────────────────────────────────────────────
#  STEP 4 — Build the email text
# ──────────────────────────────────────────────────────────────

def strip_html(raw_text):
    """
    News summaries often contain HTML tags like <p>, <b>, <br />.
    This function removes them so the email looks clean in plain text.

    Example:
      Input:  "<p>Fighting broke out <b>near the border</b>.</p>"
      Output: "Fighting broke out near the border."
    """
    # Remove all HTML tags using a regular expression
    clean = re.sub(r"<[^>]+>", "", raw_text)
    # Collapse multiple spaces/newlines into a single space
    clean = re.sub(r"\s+", " ", clean).strip()
    # Truncate to the configured max length
    if len(clean) > SUMMARY_MAX_LENGTH:
        clean = clean[:SUMMARY_MAX_LENGTH] + "…"
    return clean


def build_email_body(top_stories):
    """
    Formats the top stories into a readable plain-text email.

    Example output:
    ─────────────────────────────────
    🌍 Top Global News — 23 Feb 2026
    ─────────────────────────────────

    1. US and China resume trade talks
       Source: Reuters
       Diplomats met in Geneva to discuss tariff reductions…

    2. Oil prices surge amid Middle East tension
       ...
    """
    today = datetime.date.today().strftime("%d %b %Y")

    lines = []
    lines.append("=" * 50)
    lines.append(f"  Top Global News — {today}")
    lines.append("=" * 50)
    lines.append("")  # Blank line

    if not top_stories:
        lines.append("No stories could be fetched today. Please check your internet connection.")
        return "\n".join(lines)

    for rank, story in enumerate(top_stories, start=1):
        title     = story["title"]
        summary   = strip_html(story["summary"])
        source    = story["source"]
        published = story["published"]

        lines.append(f"{rank}. {title}")
        lines.append(f"   Source: {source}")
        if published:
            lines.append(f"   Published: {published}")
        if summary:
            lines.append(f"   {summary}")
        lines.append("")  # Blank line between stories

    lines.append("-" * 50)
    lines.append("Delivered by your Daily News Bot 🤖")
    lines.append("Powered by feedparser + GitHub Actions (free!)")
    lines.append("=" * 50)

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
#  STEP 5 — Send the email via Gmail
# ──────────────────────────────────────────────────────────────

def send_email(email_body):
    """
    Sends the formatted email to yourself using Gmail's SMTP server.

    Requires two environment variables to be set:
      EMAIL_ADDRESS  → your Gmail address
      EMAIL_PASSWORD → your 16-character Gmail App Password
                       (NOT your normal Gmail password!)

    The email is sent over SSL (encrypted) on port 465.
    """
    # Read credentials from environment variables (never hardcode these!)
    sender_email   = os.environ.get("EMAIL_ADDRESS")
    sender_password = os.environ.get("EMAIL_PASSWORD")

    # Safety check: make sure the variables are actually set
    if not sender_email or not sender_password:
        raise ValueError(
            "Missing environment variables!\n"
            "Please set EMAIL_ADDRESS and EMAIL_PASSWORD before running.\n"
            "Example:\n"
            "  export EMAIL_ADDRESS='your@gmail.com'\n"
            "  export EMAIL_PASSWORD='abcd efgh ijkl mnop'"
        )

    receiver_email = sender_email  # Send the email to yourself

    # Build the email message
    # Using the email library to create a proper MIME message
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    message = MIMEMultipart()
    message["Subject"] = f"📰 Daily Global News — {datetime.date.today().strftime('%d %b %Y')}"
    message["From"]    = sender_email
    message["To"]      = receiver_email

    # Attach the plain-text body
    message.attach(MIMEText(email_body, "plain", "utf-8"))

    # Connect to Gmail's SMTP server over SSL and send the email
    print("  Connecting to Gmail SMTP server…")
    ssl_context = ssl.create_default_context()

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl_context) as smtp_server:
        smtp_server.login(sender_email, sender_password)
        smtp_server.sendmail(sender_email, receiver_email, message.as_string())

    print(f"  ✅ Email sent successfully to {receiver_email}")


# ──────────────────────────────────────────────────────────────
#  MAIN — Runs everything in order
# ──────────────────────────────────────────────────────────────

def main():
    """
    Entry point. Runs all steps in sequence:
      1. Fetch news from RSS feeds
      2. Score and rank the stories
      3. Pick the top 5
      4. Build the email text
      5. Send it to your Gmail
    """
    print("\n📡 Daily News Bot starting…\n")

    # ── Step 1: Fetch ───────────────────────────────────────
    print("Step 1/4 — Fetching news feeds…")
    all_stories = fetch_all_news()
    print(f"  Collected {len(all_stories)} stories total.\n")

    # ── Step 2 & 3: Score + Select ──────────────────────────
    print(f"Step 2/4 — Scoring and selecting top {TOP_N_STORIES} stories…")
    top_stories = pick_top_stories(all_stories, n=TOP_N_STORIES)
    print(f"  Top stories selected:\n")
    for i, story in enumerate(top_stories, 1):
        print(f"    {i}. [{story['score']:.1f}pts] {story['title']}")
    print()

    # ── Step 3: Build email ─────────────────────────────────
    print("Step 3/4 — Building email…")
    email_body = build_email_body(top_stories)
    print("  Email body ready.\n")

    # ── Step 4: Send email ──────────────────────────────────
    print("Step 4/4 — Sending email…")
    send_email(email_body)

    print("\n✅ All done! Check your inbox.\n")


# ── Run main() only when this file is executed directly ────────
# (Not when it's imported as a module by another script)
if __name__ == "__main__":
    main()

import os

# IMPORTANT: Replace 'your@gmail.com' with your actual Gmail address
# and 'your_16_character_app_password' with your Gmail App Password.
# You can generate an App Password from your Google Account security settings.

os.environ['EMAIL_ADDRESS'] = 'liumy121108@gmail.com'
os.environ['EMAIL_PASSWORD'] = 'gupzscnqidktqjev'

print("EMAIL_ADDRESS and EMAIL_PASSWORD environment variables set.")
