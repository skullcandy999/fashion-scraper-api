"""
Diesel Scraper Module
SKU format: DSA06268 0AFAA 100 → A06268_0AFAA_100
CDN: shop.diesel.com/dw/image/v2/BBLG_PRD
"""

import requests
import re
from requests.adapters import HTTPAdapter, Retry
from concurrent.futures import ThreadPoolExecutor, as_completed

# CDN base URL
CDN_BASE = "https://shop.diesel.com/dw/image/v2/BBLG_PRD/on/demandware.static/-/Sites-diesel-master-catalog/default/images/large"

# Query params for proper image sizing
QS = "?sw=1200&sh=1600&sm=fit"

# Image views to try (in priority order)
VIEWS = ["C", "E", "F", "I", "B", "D", "A", "G", "H"]

MIN_SIZE = 20000  # Minimum valid image size
TIMEOUT = 8
MAX_WORKERS = 9

# Prefix mapping (for DSA, DSX, DSY format)
PREFIX_MAP = {
    "DSA": "A",
    "DSX": "X",
    "DSY": "Y",
}

def get_session():
    """Create session with retry logic"""
    s = requests.Session()
    r = Retry(total=2, connect=2, read=2, backoff_factor=0.2,
              status_forcelist=(429, 500, 502, 503, 504))
    s.mount("https://", HTTPAdapter(max_retries=r, pool_connections=16, pool_maxsize=16))
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
    })
    return s


def format_sku(sku):
    """
    Convert SKU to Diesel CDN parts.
    DSA06268 0AFAA 100 → ("A06268", "0AFAA", "100")
    DS00C06P 09N49 02 → ("00C06P", "09N49", "02")
    DS1DR166 PR389 T8013 → ("1DR166", "PR389", "T8013")
    """
    parts = re.split(r"\s+", sku.strip().upper())
    if len(parts) != 3:
        return None

    first_part = parts[0]  # DSA06268 or DS00C06P

    # Check if it starts with DS
    if not first_part.startswith("DS"):
        return None

    # Get prefix (A, X, Y) based on DSA/DSX/DSY prefix
    prefix_code = first_part[:3]  # DSA, DSX, DSY
    prefix = PREFIX_MAP.get(prefix_code)

    if prefix:
        # DSA/DSX/DSY format: DSA06268 -> A06268
        num = first_part[3:]
        code = f"{prefix}{num}"
    else:
        # Other formats: DS00C06P -> 00C06P, DS1DR166 -> 1DR166
        code = first_part[2:]  # Just remove DS prefix

    return (code, parts[1], parts[2])


def check_single_image(args):
    """Check single image URL - for parallel execution"""
    session, url, view_index = args
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code == 200 and len(response.content) >= MIN_SIZE:
            return (view_index, url, True)
    except:
        pass
    return (view_index, url, False)


def scrape(sku, max_images=5, validate=True):
    """
    Scrape images for a Diesel product - PARALLEL.

    Args:
        sku: Product SKU (e.g., "DSA06268 0AFAA 100")
        max_images: Maximum number of images to return
        validate: Whether to validate image URLs (always True for this scraper)

    Returns:
        dict with sku, images, count, error
    """
    result = {
        "sku": sku,
        "formatted_sku": sku.replace(" ", "_"),
        "brand_code": "DS",
        "images": [],
        "count": 0,
        "error": None
    }

    # Parse SKU
    parts = format_sku(sku)
    if not parts:
        result["error"] = f"Invalid SKU format: {sku}"
        return result

    first, second, third = parts
    result["diesel_code"] = f"{first}_{second}_{third}"

    # Build all URLs to check
    session = get_session()
    urls_to_check = []
    for i, view in enumerate(VIEWS):
        filename = f"{first}_{second}_{third}_{view}.jpg"
        url = f"{CDN_BASE}/{filename}{QS}"
        urls_to_check.append((session, url, i))

    # Check all views in parallel
    valid_images = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_single_image, args) for args in urls_to_check]
        for future in as_completed(futures):
            view_index, url, is_valid = future.result()
            if is_valid:
                valid_images.append((view_index, url))

    session.close()

    # Sort by view priority and take max_images
    valid_images.sort(key=lambda x: x[0])

    for _, url in valid_images[:max_images]:
        idx = len(result["images"]) + 1
        result["images"].append({
            "url": url,
            "index": idx,
            "filename": f"{result['formatted_sku']}-{idx}.jpg"
        })

    result["count"] = len(result["images"])

    if not result["images"]:
        result["error"] = "No images found"

    return result


# Test
if __name__ == "__main__":
    import time

    test_skus = [
        "DSA06268 0AFAA 100",
        "DSA06268 0AFAA 9XXA",
        "DSX08396 P8238 H8457",
        "DSY03650 P8140 HA947",
        "DSA03624 09M70 08",
    ]

    start = time.time()
    working = 0
    for sku in test_skus:
        result = scrape(sku, max_images=5)
        if result['count'] > 0:
            working += 1
            print(f"✓ {sku}: {result['count']} images")
            for img in result['images'][:2]:
                print(f"    {img['url'][:80]}...")
        else:
            print(f"✗ {sku}: {result.get('error', 'No images')}")

    print(f"\n=== SUMMARY ===")
    print(f"Working: {working}/{len(test_skus)}")
    print(f"Time: {time.time() - start:.2f}s")
