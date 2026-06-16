from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from core.extractor import extract_page_data
from core.storage import save_data
from core.ai_extractor import analyze_investor_text


visited_links = set()


BLOCKED_DOMAINS = [
    "twitter.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "wikipedia.org",
    "wiktionary.org",
    "login",
    "signin",
    "privacy",
    "terms",
    "cookie",
    "legal",
    "jobs"
]


KEYWORDS = [
    "portfolio",
    "fund",
    "funds",
    "strategy",
    "investment",
    "investments",
    "performance",
    "track-record",
    "trackrecord",
    "returns",
    "exits",
    "about",
    "focus",
    "thesis"
]


def is_valid_url(url):

    if not url:
        return False

    url = url.lower()

    if not url.startswith("http"):
        return False

    if any(blocked in url for blocked in BLOCKED_DOMAINS):
        return False

    return True


def score_firm(row):

    score = 0

    irr = str(row.get("irr", "")).lower()
    tvpi = str(row.get("tvpi", "")).lower()
    dpi = str(row.get("dpi", "")).lower()

    strategy = str(row.get("strategy", "")).lower()
    sector = str(row.get("sector_focus", "")).lower()

    notable = str(row.get("notable_investments", "")).lower()

    # PERFORMANCE METRICS

    if irr and irr != "":
        score += 30

    if tvpi and tvpi != "":
        score += 25

    if dpi and dpi != "":
        score += 25

    # STRATEGY QUALITY

    top_strategies = [
        "growth",
        "buyout",
        "late stage",
        "venture",
        "private equity"
    ]

    if any(x in strategy for x in top_strategies):
        score += 10

    # HIGH VALUE SECTORS

    top_sectors = [
        "ai",
        "enterprise",
        "software",
        "saas",
        "fintech",
        "infrastructure",
        "healthcare",
        "cybersecurity"
    ]

    if any(x in sector for x in top_sectors):
        score += 10

    # TOP INVESTMENTS

    elite_companies = [
        "openai",
        "stripe",
        "databricks",
        "figma",
        "canva",
        "uber",
        "airbnb",
        "facebook",
        "spotify"
    ]

    if any(x in notable for x in elite_companies):
        score += 25

    return score


def crawl_page(page, url, depth=0, max_depth=2):

    if depth > max_depth:
        return

    if url in visited_links:
        return

    if not is_valid_url(url):
        return

    visited_links.add(url)

    print(f"\nCrawling: {url}")

    try:

        page.goto(
            url,
            timeout=60000,
            wait_until="domcontentloaded"
        )

        page.wait_for_timeout(2000)

        html = page.content()

        soup = BeautifulSoup(html, "lxml")

        data = extract_page_data(html, url)

        print("\nRUNNING AI ANALYSIS...\n")

        ai_rows = analyze_investor_text(
            data["text"]
        )

        final_rows = []

        if isinstance(ai_rows, list):

            for row in ai_rows:

                if not isinstance(row, dict):
                    continue

                row["source_url"] = url

                row["score"] = score_firm(row)

                final_rows.append(row)

                print(row)

        if final_rows:
            save_data(final_rows)

        links = soup.find_all("a")

        for link in links:

            href = link.get("href")

            if not href:
                continue

            full_url = urljoin(url, href)

            full_url_lower = full_url.lower()

            if any(
                keyword in full_url_lower
                for keyword in KEYWORDS
            ):

                crawl_page(
                    page,
                    full_url,
                    depth + 1,
                    max_depth
                )

    except Exception as e:

        print("\nERROR:")
        print(e)


def crawl_site(site):

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        crawl_page(
            page,
            site["url"]
        )

        browser.close()