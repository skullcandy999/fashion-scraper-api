# -*- coding: utf-8 -*-
"""
ETRO Scraper Module
CDN: content.etro.com
SKU format: EWP1B0002 E272 F0575 -> WP1B0002AE272F0575
"""

import requests
from requests.adapters import HTTPAdapter, Retry

# ===================== CONFIGURATION =====================
CDN_BASE = "https://content.etro.com/Adaptations"
TIMEOUT = 10
MIN_SIZE = 2000

# Size directories to try (larger first)
SIZE_DIRS = ["1500", "1200", "900", "600"]

# Image suffixes
SUFFIXES = ["SF_01", "SF_02", "ST_01", "SS_01", "WF_01"]

# ===================== HTTP SESSION =====================
session = requests.Session()
retries = Retry(total=2, backoff_factor=0.3)
adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retries)
session.mount("https://", adapter)
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124",
    "Referer": "https://www.etro.com/"
})


# ===================== SKU CONVERSION =====================
def convert_sku(sku):
    """
    Convert SKU to ETRO CDN format.
    EWP1B0002 E272 F0575 -> WP1B0002AE272F0575
    - Remove E prefix
    - Join: STYLE + A + FABRIC + COLOR
    """
    sku = sku.strip()

    # Remove E prefix if present
    if sku.startswith('E'):
        sku = sku[1:]

    parts = sku.split()
    if len(parts) == 3:
        style = parts[0]   # WP1B0002
        fabric = parts[1]  # E272
        color = parts[2]   # F0575
        return f"{style}A{fabric}{color}"

    # Fallback: just remove spaces
    if len(parts) == 1 and len(sku) > 10:
        return sku

    return sku.replace(" ", "")


def try_url(url):
    """Try to fetch URL, return True if valid image"""
    try:
        r = session.get(url, stream=True, timeout=TIMEOUT)
        if r.status_code == 200:
            content_length = int(r.headers.get("Content-Length", "0"))
            if content_length > MIN_SIZE:
                return True
    except:
        pass
    return False


# ===================== MAIN SCRAPE FUNCTION =====================
def scrape(sku: str, max_images: int = 5, validate: bool = True) -> dict:
    """
    Main scrape function for ETRO.

    Args:
        sku: SKU in format EWP1B0002 E272 F0575
        max_images: Maximum number of images
        validate: Whether to validate image downloads

    Returns:
        dict with sku, images, count, etc.
    """
    result = {
        "sku": sku,
        "formatted_sku": sku.replace(" ", "_"),
        "etro_code": "",
        "images": [],
        "count": 0,
        "error": None
    }

    # Convert SKU
    etro_code = convert_sku(sku)
    if not etro_code:
        result["error"] = f"Invalid SKU format: {sku}"
        return result

    result["etro_code"] = etro_code

    # Try each suffix with multiple sizes
    for suffix in SUFFIXES:
        if len(result["images"]) >= max_images:
            break

        found_url = None

        # Try all size/extension combinations
        for size in SIZE_DIRS:
            if found_url:
                break
            for ext in [".jpg", ".JPG"]:
                url = f"{CDN_BASE}/{size}/{etro_code}_{suffix}{ext}"
                if try_url(url):
                    found_url = url
                    break

        if found_url:
            idx = len(result["images"]) + 1
            result["images"].append({
                "url": found_url,
                "filename": f"{result['formatted_sku']}-{idx}",
                "index": idx,
                "suffix": suffix
            })

    if not result["images"]:
        result["error"] = f"No images found for {etro_code}"

    result["count"] = len(result["images"])

    return result


# ===================== TEST =====================
if __name__ == "__main__":
    test_skus = [
        "EWP1B0001 E225 N0000",
        "EWP1B0002 E272 F0575",
        "EWP1C0019 P340 N0000",
        "EWP1D0024 A001 M0019",
    ]

    for sku in test_skus:
        print(f"\n{'='*60}")
        print(f"Testing: {sku}")
        print(f"{'='*60}")

        result = scrape(sku, max_images=5, validate=True)

        print(f"ETRO code: {result.get('etro_code')}")
        print(f"Images found: {result.get('count')}")

        if result.get('error'):
            print(f"Error: {result['error']}")

        for img in result.get('images', [])[:3]:
            print(f"  {img['filename']}: {img['url'][:65]}...")
