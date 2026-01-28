# -*- coding: utf-8 -*-
"""
EMPORIO ARMANI Scraper Module
CDN: assets-cf.armani.com
SKU format: EAEM00282913666UB104 -> EM002829_AF13666_UB104_F_FW2025.jpg
"""

import requests
from requests.adapters import HTTPAdapter, Retry

# ===================== CONFIGURATION =====================
CDN_BASE = "https://assets-cf.armani.com/image/upload"
CDN_PARAMS = "f_auto,q_auto:best,ar_4:5,w_1350,c_fill"
TIMEOUT = 8

# Fabric prefixes - AF is most common, then TE
FABRIC_PREFIXES = ["AF", "TE", "TS", "TF", "TK", "TN"]

# Seasons - newest first
SEASONS = ["FW2025", "SS2025", "FW2024", "SS2024"]

# Image suffixes
IMG_SUFFIXES = ["F", "D", "R", "E", "A", "B"]

# ===================== HTTP SESSION =====================
session = requests.Session()
retries = Retry(total=2, backoff_factor=0.2, status_forcelist=(500, 502, 503, 504))
session.mount("https://", HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retries))
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"})


def http_head(url):
    """Quick check if URL exists"""
    try:
        r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code == 200
    except:
        return False


def http_get(url):
    """Download image"""
    try:
        r = session.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and len(r.content) > 5000:
            return r.content
    except:
        pass
    return None


# ===================== SKU PARSING =====================
def parse_sku(sku):
    """
    Parse SKU into components.
    EAEM00282913666UB104 -> (EM, 002829, 13666, UB104)
    EAEW00036012036M1286 -> (EW, 000360, 12036, M1286)
    """
    sku = sku.strip().replace(" ", "").replace("-", "")

    # Only EAEM and EAEW formats
    if not (sku.startswith("EAEM") or sku.startswith("EAEW")):
        return None

    code = sku[2:]  # Remove "EA"

    if len(code) < 16:
        return None

    brand = code[:2]       # EM or EW
    model = code[2:8]      # 6 digits
    fabric = code[8:13]    # 5 digits
    color = code[13:]      # rest

    return (brand, model, fabric, color)


def build_url(brand, model, prefix, fabric, color, suffix, season):
    """Build CDN URL"""
    code = f"{brand}{model}_{prefix}{fabric}_{color}_{suffix}_{season}"
    return f"{CDN_BASE}/{CDN_PARAMS}/{code}.jpg"


# ===================== PREFIX DETECTION =====================
def detect_prefix(brand, model, fabric, color):
    """
    Quickly detect which fabric prefix works (AF, TE, etc).
    Try HEAD request on F image for each prefix.
    Returns (prefix, season) or (None, None)
    """
    for prefix in FABRIC_PREFIXES:
        for season in SEASONS:
            url = build_url(brand, model, prefix, fabric, color, "F", season)
            if http_head(url):
                return (prefix, season)
    return (None, None)


# ===================== MAIN SCRAPE FUNCTION =====================
def scrape(sku: str, max_images: int = 5, validate: bool = False) -> dict:
    """
    Main scrape function for Emporio Armani.

    Args:
        sku: SKU in format EAEM00282913666UB104
        max_images: Maximum number of images
        validate: Whether to validate image downloads

    Returns:
        dict with sku, images, count, etc.
    """
    result = {
        "sku": sku,
        "formatted_sku": sku.replace(" ", "_").replace("-", "_"),
        "armani_code": "",
        "prefix": "",
        "season": "",
        "images": [],
        "count": 0,
        "error": None
    }

    # Parse SKU
    parsed = parse_sku(sku)
    if not parsed:
        result["error"] = f"Invalid SKU format: {sku}. Must start with EAEM or EAEW"
        return result

    brand, model, fabric, color = parsed

    # Detect which prefix works
    prefix, season = detect_prefix(brand, model, fabric, color)

    if not prefix:
        result["armani_code"] = f"{brand}{model}-??{fabric}-{color}"
        result["error"] = f"Product not found on CDN for {brand}{model}"
        return result

    result["prefix"] = prefix
    result["season"] = season
    result["armani_code"] = f"{brand}{model}-{prefix}{fabric}-{color}"

    # Collect image URLs
    image_urls = []
    for suffix in IMG_SUFFIXES:
        if len(image_urls) >= max_images:
            break

        url = build_url(brand, model, prefix, fabric, color, suffix, season)

        if validate:
            # Actually download to verify
            img = http_get(url)
            if img:
                image_urls.append(url)
        else:
            # Just check with HEAD
            if http_head(url):
                image_urls.append(url)

    if not image_urls:
        result["error"] = f"No images found for {result['armani_code']}"
        return result

    # Build result
    for idx, url in enumerate(image_urls, 1):
        result["images"].append({
            "url": url,
            "filename": f"{result['formatted_sku']}-{idx}",
            "index": idx
        })

    result["count"] = len(result["images"])

    return result


# ===================== TEST =====================
if __name__ == "__main__":
    test_skus = [
        "EAEM00282913666UB104",
        "EAEM00282913666UB107",
        "EAEW00036012036M1286",
        "EAEM00459310762F0201",
    ]

    for sku in test_skus:
        print(f"\n{'='*60}")
        print(f"Testing: {sku}")
        print(f"{'='*60}")

        result = scrape(sku, max_images=5, validate=False)

        print(f"Armani code: {result.get('armani_code')}")
        print(f"Prefix: {result.get('prefix')} | Season: {result.get('season')}")
        print(f"Images found: {result.get('count')}")

        if result.get('error'):
            print(f"Error: {result['error']}")

        for img in result.get('images', [])[:3]:
            print(f"  {img['filename']}: {img['url'][:60]}...")
