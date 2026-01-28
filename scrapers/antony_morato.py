# -*- coding: utf-8 -*-
"""
ANTONY MORATO Scraper Module
CDN: cdn.antonymorato.com.filoblu.com

SKU format:
- Our: AMFL011181501789000
- Their: MMFL01118-FA150178-9000

Prefix mapping varies (FA, LE, YA) - scraper probes all possibilities.
"""

import requests
from requests.adapters import HTTPAdapter, Retry

# ===================== CONFIGURATION =====================
CDN_BASE = "https://cdn.antonymorato.com.filoblu.com/rx/ofmt_webp/media/catalog/product"
TIMEOUT = 8
MIN_SIZE = 1000

# Prefix mapping - for ambiguous codes, lists all possibilities to try
PREFIX_MAP = {
    "10": ["FA", "LE", "YA"],  # ambiguous
    "14": ["FA"],
    "15": ["FA"],
    "20": ["FA"],
    "21": ["FA"],
    "30": ["LE", "FA"],  # ambiguous
    "40": ["YA"],
    "43": ["FA"],
    "50": ["YA", "FA"],  # ambiguous
    "60": ["FA"],
    "75": ["FA"],
    "80": ["FA"],
}

# ===================== HTTP SESSION =====================
session = requests.Session()
retries = Retry(total=2, backoff_factor=0.3)
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retries)
session.mount("https://", adapter)
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"
})


# ===================== SKU CONVERSION =====================
def convert_sku_candidates(our_sku):
    """
    Convert our SKU to list of possible Morato codes.

    AMFL011181501789000 -> ["MMFL01118-FA150178-9000"]
    AMKS026011002581016 -> ["MMKS02601-FA100258-1016", "MMKS02601-LE100258-1016", "MMKS02601-YA100258-1016"]

    Returns list of candidates to try (for ambiguous prefixes).
    """
    sku = our_sku.strip().upper()
    if sku.startswith('AM'):
        sku = sku[2:]

    if len(sku) < 15:
        return []

    model = sku[:7]           # FL01118
    rest = sku[7:]            # 1501789000

    fabric_start = rest[:2]   # 15
    fabric_num = rest[2:6]    # 0178
    color = rest[6:]          # 9000

    prefixes = PREFIX_MAP.get(fabric_start, ["FA"])

    candidates = []
    for prefix in prefixes:
        morato = f"MM{model}-{prefix}{fabric_start}{fabric_num}-{color}"
        candidates.append(morato)

    return candidates


def check_cdn_url(morato_code):
    """Check if CDN URL exists, return first working URL or None."""
    fn = morato_code.upper()
    fnL = fn.lower()
    d1, d2 = fn[0], fn[1]
    d1L, d2L = d1.lower(), d2.lower()

    for i in [1, 2]:
        sfx = f"_{i:02d}.jpg"
        urls = [
            f"{CDN_BASE}/{d1}/{d2}/{fn}{sfx}",
            f"{CDN_BASE}/{d1L}/{d2L}/{fnL}{sfx}",
            f"{CDN_BASE}/{d1}/{d2}/{fn}-UN{sfx}",
            f"{CDN_BASE}/{d1L}/{d2L}/{fnL}-UN{sfx}",
        ]

        for url in urls:
            try:
                r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
                if r.status_code == 200:
                    cl = r.headers.get("Content-Length")
                    if cl is None or int(cl) > MIN_SIZE:
                        return url
            except:
                pass

    return None


def get_all_images(morato_code, max_images=5):
    """Get all image URLs for a working Morato code."""
    fn = morato_code.upper()
    fnL = fn.lower()
    d1, d2 = fn[0], fn[1]
    d1L, d2L = d1.lower(), d2.lower()

    images = []
    for i in range(1, max_images + 5):
        if len(images) >= max_images:
            break

        sfx = f"_{i:02d}.jpg"
        urls_to_try = [
            f"{CDN_BASE}/{d1}/{d2}/{fn}{sfx}",
            f"{CDN_BASE}/{d1L}/{d2L}/{fnL}{sfx}",
            f"{CDN_BASE}/{d1}/{d2}/{fn}-UN{sfx}",
            f"{CDN_BASE}/{d1L}/{d2L}/{fnL}-UN{sfx}",
        ]

        found = False
        for url in urls_to_try:
            try:
                r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
                if r.status_code == 200:
                    cl = r.headers.get("Content-Length")
                    if cl is None or int(cl) > MIN_SIZE:
                        images.append(url)
                        found = True
                        break
            except:
                pass

        # If no image found at this index, stop looking
        if not found and i > 1:
            break

    return images


# ===================== MAIN SCRAPE FUNCTION =====================
def scrape(sku: str, max_images: int = 5, validate: bool = False) -> dict:
    """
    Main scrape function for Antony Morato.

    Args:
        sku: SKU in format AMFL011181501789000
        max_images: Maximum number of images
        validate: Whether to validate images (not used, always validates via HEAD)

    Returns:
        dict with sku, images, count, etc.
    """
    result = {
        "sku": sku,
        "formatted_sku": sku.replace(" ", "_"),
        "morato_code": "",
        "images": [],
        "count": 0,
        "error": None
    }

    # Get candidate codes
    candidates = convert_sku_candidates(sku)

    if not candidates:
        result["error"] = f"Invalid SKU format: {sku}"
        return result

    # Try each candidate until one works
    working_code = None
    for code in candidates:
        url = check_cdn_url(code)
        if url:
            working_code = code
            break

    if not working_code:
        result["error"] = f"No images found on CDN. Tried: {', '.join(candidates)}"
        result["tried_codes"] = candidates
        return result

    result["morato_code"] = working_code

    # Get all images
    image_urls = get_all_images(working_code, max_images)

    if not image_urls:
        result["error"] = f"No images found for {working_code}"
        return result

    # Build result
    formatted_sku = sku.replace(" ", "_")
    for idx, url in enumerate(image_urls, 1):
        result["images"].append({
            "url": url,
            "filename": f"{formatted_sku}-{idx}",
            "index": idx
        })

    result["count"] = len(result["images"])

    return result


# ===================== TEST =====================
if __name__ == "__main__":
    test_skus = [
        "AMFL011181501789000",
        "AMFW017743001059100",
        "AMKS026011002581016",
        "AMSW015781000719000",
    ]

    for sku in test_skus:
        print(f"\n{'='*60}")
        print(f"Testing: {sku}")
        print(f"{'='*60}")

        result = scrape(sku, max_images=5)

        print(f"Morato code: {result.get('morato_code')}")
        print(f"Images found: {result.get('count')}")

        if result.get('error'):
            print(f"Error: {result['error']}")

        for img in result.get('images', [])[:3]:
            print(f"  {img['filename']}: {img['url'][:70]}...")
