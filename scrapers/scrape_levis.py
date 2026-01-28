"""
Levi's Scraper - Scene7 CDN (FIXED)
Endpoint: /scrape-levis

URL Format: https://lscoglobal.scene7.com/is/image/lscoglobal/{PREFIX}_{SKU}_{MIDDLE}{VIEW}
Example: MB_000LO-0033_GLO_CM_DA
"""

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Config
BASE_URL = "https://lscoglobal.scene7.com/is/image/lscoglobal"
QS = "?fmt=webp&qlt=70&resMode=sharp2&fit=crop,1&op_usm=0.6,0.6,8&wid=1760&hei=1760"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MIN_VALID_BYTES = 10000
TIMEOUT = 10
MAX_WORKERS = 8

# Prefixes to try (gender + category combinations)
PREFIXES = ["MB_", "MT_", "WB_", "WT_", "UB_", "UT_", "A_", ""]

# Middle parts (region + type)
MIDDLES = ["GLO_CM_", "GLO_CL_", "LSE_CL_", "LSE_CM_"]

# View suffixes (in priority order)
VIEWS = ["DA", "FV", "BV", "SV", "D1", "D2", "D3"]


def convert_sku(sku):
    """
    Convert SKU - keep the dash!
    LV000LO-0033 -> 000LO-0033
    """
    code = sku.strip().upper()
    if code.startswith("LV"):
        code = code[2:]
    return code


def check_url(url):
    """Check if image URL is valid"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and len(r.content) > MIN_VALID_BYTES:
            return True
    except:
        pass
    return False


def check_url_parallel(args):
    """For parallel checking"""
    url, idx = args
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and len(r.content) > MIN_VALID_BYTES:
            return (idx, url, True)
    except:
        pass
    return (idx, url, False)


def find_working_combo(sku_code):
    """
    Find which prefix + middle combination works for this SKU.
    Uses parallel requests to speed up discovery.
    """
    # Build all combinations to test (first view only)
    combos_to_test = []
    idx = 0
    for prefix in PREFIXES:
        for middle in MIDDLES:
            url = f"{BASE_URL}/{prefix}{sku_code}_{middle}DA{QS}"
            combos_to_test.append((url, idx, prefix, middle))
            idx += 1

    # Test in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(check_url_parallel, (c[0], c[1])): c
            for c in combos_to_test
        }
        for future in as_completed(futures):
            combo = futures[future]
            _, _, is_valid = future.result()
            if is_valid:
                return (combo[2], combo[3])  # prefix, middle

    return (None, None)


def scrape_levis(sku, max_images=5):
    """
    Scrape Levi's product images from Scene7 CDN

    Args:
        sku: Product SKU (e.g., "LV000LO-0033")
        max_images: Maximum number of images to return

    Returns:
        dict with 'images' list containing image URLs
    """
    sku_code = convert_sku(sku)

    if not sku_code:
        return {"sku": sku, "images": [], "count": 0, "error": "Invalid SKU format"}

    # Find working prefix/middle combo
    prefix, middle = find_working_combo(sku_code)

    if prefix is None:
        return {"sku": sku, "images": [], "count": 0, "error": f"No images found for {sku_code}"}

    # Build URLs for all views with this combo
    urls_to_check = []
    for i, view in enumerate(VIEWS):
        url = f"{BASE_URL}/{prefix}{sku_code}_{middle}{view}{QS}"
        urls_to_check.append((url, i))

    # Check all views in parallel
    valid_images = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_url_parallel, args) for args in urls_to_check]
        for future in as_completed(futures):
            idx, url, is_valid = future.result()
            if is_valid:
                valid_images.append((idx, url))

    # Also check alternate middles for more variety
    if len(valid_images) < max_images:
        for alt_middle in MIDDLES:
            if alt_middle == middle:
                continue
            for i, view in enumerate(VIEWS):
                url = f"{BASE_URL}/{prefix}{sku_code}_{alt_middle}{view}{QS}"
                if check_url(url):
                    # Add with high index so it comes after primary images
                    valid_images.append((100 + len(valid_images), url))
                    if len(valid_images) >= max_images + 2:
                        break
            if len(valid_images) >= max_images + 2:
                break

    # Sort by priority and dedupe
    valid_images.sort(key=lambda x: x[0])
    seen = set()
    images = []
    for _, url in valid_images:
        if url not in seen and len(images) < max_images:
            seen.add(url)
            images.append({
                "url": url,
                "index": len(images) + 1
            })

    return {
        "sku": sku,
        "images": images,
        "count": len(images)
    }


# For direct testing
if __name__ == "__main__":
    import time
    test_skus = [
        "LV000LO-0033",
        "LV003PY-0000",
        "LV0002L-0011",
        "LV00501-3718",
        "LV17369-3182",
    ]

    print("=" * 60)
    print("LEVI'S Scraper Test - FIXED")
    print("=" * 60)

    start = time.time()
    for sku in test_skus:
        result = scrape_levis(sku)
        print(f"\n{sku}: {result['count']} images")
        if result.get('error'):
            print(f"  Error: {result['error']}")
        for img in result.get('images', []):
            path = img['url'].split('/lscoglobal/')[1].split('?')[0]
            print(f"  {img['index']}: {path}")

    print(f"\nTotal time: {time.time() - start:.2f}s")
