"""
Levi's Scraper - Scene7 CDN (PARALLEL)
Endpoint: /scrape-levis
"""

import re
import requests
from requests.adapters import HTTPAdapter, Retry
from concurrent.futures import ThreadPoolExecutor, as_completed

# Scene7 query params
QS = "?fmt=webp&qlt=70&resMode=sharp2&fit=crop,1&op_usm=0.6,0.6,8&wid=1760&hei=1760"

# Image variants in priority order
VARIANTS = [
    "dynamic1-pdp",
    "front-pdp",
    "back-pdp",
    "side-pdp",
    "detail1-pdp",
    "front-pdp-ld",
    "dynamic2-pdp",
    "dynamic3-pdp",
    "detail2-pdp",
]

MIN_VALID_BYTES = 20000
TIMEOUT = 10
MAX_WORKERS = 9  # All variants in parallel


def get_session():
    """Create session with retry logic"""
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    return session


def convert_sku(sku):
    """
    Convert SKU to Levi's Scene7 format
    LV000LO-0033 → 000LO0033
    LVA3381-0000 → A33810000

    Rule: Remove LV prefix and dashes, keep everything else (including letters)
    """
    code = sku.strip().upper()
    if code.startswith('LV'):
        code = code[2:]
    code = code.replace('-', '')
    return code


def check_single_image(args):
    """Check single image URL - for parallel execution"""
    url, variant_index = args
    try:
        session = get_session()
        response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        session.close()
        
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "").lower()
            if "image" in content_type and len(response.content) >= MIN_VALID_BYTES:
                return (variant_index, url, True)
    except:
        pass
    return (variant_index, url, False)


def scrape_levis(sku, max_images=5):
    """
    Scrape Levi's product images from Scene7 CDN - PARALLEL
    
    Args:
        sku: Product SKU (e.g., "LV0002L-0011")
        max_images: Maximum number of images to return
    
    Returns:
        dict with 'images' list containing image URLs
    """
    numeric = convert_sku(sku)
    
    if not numeric:
        return {"sku": sku, "images": [], "count": 0, "error": "Invalid SKU format"}
    
    # Build all URLs
    urls_to_check = []
    for i, variant in enumerate(VARIANTS):
        url = f"https://lsco.scene7.com/is/image/lsco/{numeric}-{variant}{QS}"
        urls_to_check.append((url, i))
    
    # Check all in parallel
    valid_images = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_single_image, args) for args in urls_to_check]
        for future in as_completed(futures):
            variant_index, url, is_valid = future.result()
            if is_valid:
                valid_images.append((variant_index, url))
    
    # Sort by variant priority and take max_images
    valid_images.sort(key=lambda x: x[0])
    
    images = []
    for _, url in valid_images[:max_images]:
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
    test_skus = ["LV0002L-0011", "LV00501-3718", "LV17369-3182"]
    
    start = time.time()
    for sku in test_skus:
        result = scrape_levis(sku)
        print(f"{sku}: {result['count']} images")
    print(f"\n⏱️ Total: {time.time() - start:.2f}s")
