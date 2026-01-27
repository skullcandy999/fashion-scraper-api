"""
Michael Kors Scraper Module
SKU format: MC30F4GY5H3T-251 -> model=30F4GY5H3T, color=251
Uses website scraping to extract image URLs from product pages
"""

import requests
import re

SCRAPER_API_KEY = "1ae7aa2a67a44259b694e92b2d069789"

# Multiple domains to try
BASE_DOMAINS = [
    "https://www.michaelkors.ae/en",
    "https://www.michaelkors.global/za/en",
    "https://www.michaelkors.global/us/en",
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})

# Regex patterns for MK images
MK_CDN_RE = re.compile(
    r"https://www\.michaelkors\.ae/dw/image/v2/[A-Z0-9_]+/on/demandware\.static/-/Sites-michaelkors-master-catalog/default/(?:dw[0-9a-f]+/)?images/([A-Z0-9]+)_(\w+)_([0-9A-Z]+)\.jpg[^\s\"'<>]*",
    re.IGNORECASE,
)

SCENE7_RE = re.compile(
    r"https?://michaelkors\.scene7\.com/is/image/MichaelKors/"
    r"(?P<model>[0-9A-Z]+)-(?P<variant>[0-9A-Z]+)_(?P<suffix>\d+)\?[^\s\"'<>]*",
    re.IGNORECASE,
)


def parse_sku(sku):
    """Parse MK SKU: MC30F4GY5H3T-251 -> (model, color)"""
    sku = sku.strip().upper()
    if not sku.startswith("MC"):
        return None, None

    code = sku[2:]  # Remove MC prefix
    if "-" in code:
        model, color = code.split("-", 1)
    else:
        model, color = code, ""

    return model, color


def fetch_product_page(model):
    """Try multiple domains to fetch product page with JS rendering"""
    # First try with ScraperAPI + render (most reliable)
    for base in BASE_DOMAINS:
        url = f"{base}/{model}.html"
        api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&render=true"
        try:
            r = requests.get(api_url, timeout=60)
            if r.status_code == 200 and len(r.text) > 4000:
                # Check if page has images
                if 'scene7' in r.text.lower() or 'michaelkors' in r.text.lower():
                    return r.text, url
        except:
            pass

    # Fallback to direct request
    for base in BASE_DOMAINS:
        url = f"{base}/{model}.html"
        try:
            r = session.get(url, timeout=15, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 4000:
                return r.text, r.url
        except:
            pass

    return None, None


def extract_images(html, target_model, target_color):
    """Extract image URLs from product page HTML"""
    candidates = []

    # MK CDN images (any color variant)
    for m in MK_CDN_RE.finditer(html):
        model, color, suffix = m.group(1), m.group(2), m.group(3)
        if model.upper() != target_model.upper():
            continue
        # Don't filter by color - MK uses different internal color codes
        candidates.append((m.group(0), suffix))

    # Scene7 images - more flexible pattern
    scene7_pattern = re.compile(
        rf"https?://michaelkors\.scene7\.com/is/image/MichaelKors/{re.escape(target_model)}-(\w+)_(\d+)[^\s\"'<>]*",
        re.IGNORECASE
    )
    for m in scene7_pattern.finditer(html):
        variant, suffix = m.group(1), m.group(2)
        candidates.append((m.group(0), suffix))

    # Also try generic Scene7 pattern
    for m in SCENE7_RE.finditer(html):
        model = m.group("model")
        suffix = m.group("suffix")
        if model.upper() == target_model.upper():
            candidates.append((m.group(0), suffix))

    # Additional: find any scene7 URLs with this model
    all_scene7 = re.findall(
        rf'(https?://michaelkors\.scene7\.com/is/image/MichaelKors/{re.escape(target_model)}[^"\'<>\s]+)',
        html, re.IGNORECASE
    )
    for url in all_scene7:
        # Extract suffix from URL
        suf_match = re.search(r'_(\d+)', url)
        suf = suf_match.group(1) if suf_match else "0"
        candidates.append((url, suf))

    # Deduplicate
    seen = set()
    unique = []
    for url, suf in candidates:
        base = url.split("?", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        unique.append((url, suf))

    # Sort by suffix (1, 2, 3...)
    def sort_key(pair):
        suf = pair[1]
        try:
            return (0, int(suf))
        except:
            return (9, str(suf).upper())

    unique.sort(key=sort_key)
    return [u for (u, _) in unique]


def scrape(sku, max_images=5):
    """
    Scrape Michael Kors product images

    Args:
        sku: Product SKU (e.g., "MC30F4GY5H3T-251")
        max_images: Maximum number of images

    Returns:
        dict with sku, images, count, error
    """
    result = {
        "sku": sku,
        "model": "",
        "color": "",
        "brand_code": "MK",
        "product_url": "",
        "images": [],
        "count": 0,
        "error": None
    }

    try:
        model, color = parse_sku(sku)
        if not model:
            result["error"] = f"Invalid SKU format: {sku}"
            return result

        result["model"] = model
        result["color"] = color

        # Fetch product page
        html, page_url = fetch_product_page(model)
        if not html:
            result["error"] = "Product page not found"
            return result

        result["product_url"] = page_url

        # Extract images
        urls = extract_images(html, model, color)
        if not urls:
            result["error"] = "No images found on product page"
            return result

        # Format result
        for i, url in enumerate(urls[:max_images]):
            result["images"].append({
                "url": url,
                "index": i + 1,
                "filename": f"{sku.replace('-', '_')}-{i + 1}.jpg"
            })

        result["count"] = len(result["images"])

    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    test_skus = [
        "MC30F4GY5H3T-251",
        "MC32F5GNXC0L-457",
        "MCMT5531FH69-120",
    ]

    for sku in test_skus:
        print(f"\nTesting: {sku}")
        result = scrape(sku, max_images=5)
        print(f"  Model: {result['model']}, Color: {result['color']}")
        print(f"  URL: {result['product_url']}")
        print(f"  Images: {result['count']}")
        if result['images']:
            print(f"  First: {result['images'][0]['url'][:70]}...")
        if result['error']:
            print(f"  Error: {result['error']}")
