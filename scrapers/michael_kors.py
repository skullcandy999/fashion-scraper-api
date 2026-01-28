"""
Michael Kors Scraper Module
SKU format: MC30F4GY5H3T-251 -> model=30F4GY5H3T, color=251
Uses direct website scraping - michaelkors.ae works without proxy
"""

import requests
import re

# Multiple domains to try (AE works best - no geo-blocking)
BASE_DOMAINS = [
    "https://www.michaelkors.ae/en",
    "https://www.michaelkors.global/za/en",
    "https://www.michaelkors.global/us/en",
    "https://www.michaelkors.global/gb/en",
]

TIMEOUT = 12

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
})

# MK CDN (Demandware) - primary source
MK_CDN_RE = re.compile(
    r"https://www\.michaelkors\.ae/dw/image/v2/[A-Z0-9_]+/on/demandware\.static/-/Sites-michaelkors-master-catalog/default/(?:dw[0-9a-f]+/)?images/([A-Z0-9]+)_(\w+)_([0-9A-Z]+)\.jpg[^\s\"'<>]*",
    re.IGNORECASE,
)

# Scene7 CDN - secondary source
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
    """Try multiple domains - direct request (no proxy needed for AE)"""
    for base in BASE_DOMAINS:
        url = f"{base}/{model}.html"
        try:
            r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 4000:
                # Verify page has product images
                if 'demandware' in r.text.lower() or 'scene7' in r.text.lower():
                    return r.text, r.url
        except Exception:
            pass
    return None, None


def extract_images(html, target_model, target_color):
    """Extract image URLs from product page HTML"""
    candidates = []

    # A) MK CDN (Demandware) - filter by model, optionally by color
    for m in MK_CDN_RE.finditer(html):
        model, color, suffix = m.group(1), m.group(2), m.group(3)
        if model.upper() != target_model.upper():
            continue
        # Filter by color if provided (but MK uses internal color codes)
        if target_color and color.upper() != target_color.upper():
            # Still add but mark as secondary
            pass
        candidates.append((m.group(0), suffix, "cdn"))

    # B) Scene7 - filter by model only
    for m in SCENE7_RE.finditer(html):
        model = m.group("model")
        suffix = m.group("suffix")
        if model.upper() != target_model.upper():
            continue
        candidates.append((m.group(0), suffix, "scene7"))

    # C) Generic Scene7 pattern (more flexible)
    scene7_generic = re.findall(
        rf'(https?://michaelkors\.scene7\.com/is/image/MichaelKors/{re.escape(target_model)}[^"\'<>\s]+)',
        html, re.IGNORECASE
    )
    for url in scene7_generic:
        suf_match = re.search(r'_(\d+)', url)
        suf = suf_match.group(1) if suf_match else "0"
        candidates.append((url, suf, "scene7"))

    # Deduplicate by base URL
    seen = set()
    unique = []
    for url, suf, src in candidates:
        base = url.split("?", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        unique.append((url, suf, src))

    # Sort by suffix (1, 2, 3...)
    def sort_key(item):
        suf = item[1]
        try:
            return (0, int(suf))
        except:
            return (9, str(suf).upper())

    unique.sort(key=sort_key)
    return [u for (u, _, _) in unique]


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

        # Fetch product page (direct, no proxy)
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

        # Return URLs directly (no validation - URLs from page are valid)
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
    # Test SKUs from user's working examples
    test_skus = [
        "MC30T5SQNT9L-001",
        "MC30R6S9IS1E-001",
        "MC32S5GYTP1B-149",
        "MCCT52096HJQ-401",
        "MCCR640AFKEV-914",
        "MCCS15073C93-424",
        "MCMR683BSBFD-001",
        "MCMR661EW33D-409",
    ]

    print("Testing Michael Kors scraper (direct, no proxy)...")
    print("-" * 60)

    for sku in test_skus:
        result = scrape(sku, max_images=5)
        status = "✓" if result["count"] > 0 else "✗"
        print(f"{status} {sku}: {result['count']} images")
        if result["images"]:
            print(f"   {result['images'][0]['url'][:70]}...")
        if result["error"]:
            print(f"   Error: {result['error']}")
