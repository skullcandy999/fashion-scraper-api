"""
Coach Scraper - Scene7 CDN (PARALLEL)
Endpoint: /scrape-coach
Uses $desktopProductZoom$ for high-res images
"""

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://coach.scene7.com/is/image/Coach/"
SUFFIXES = ["a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10"]
TIMEOUT = 10
MIN_VALID_BYTES = 5000
MAX_WORKERS = 11  # All suffixes in parallel


def convert_sku(sku):
    """
    Convert SKU format: CHCAF55-B4-MPL → caf55_b4mpl
    """
    sku = sku.replace("CH", "").lower()
    parts = sku.split("-")
    if len(parts) >= 3:
        return f"{parts[0]}_{parts[1]}{parts[2]}"
    return sku.lower()


def check_single_image(args):
    """Check single image URL - for parallel execution"""
    url, index = args
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type and len(response.content) > MIN_VALID_BYTES:
                return (index, url, True)
    except:
        pass
    return (index, url, False)


def scrape_coach(sku, max_images=5):
    """
    Scrape Coach product images from Scene7 CDN - PARALLEL
    
    Args:
        sku: Product SKU (e.g., "CHCAF55-B4-MPL")
        max_images: Maximum number of images to return
    
    Returns:
        dict with 'images' list containing image URLs
    """
    code = convert_sku(sku)
    
    # Build all URLs to check
    urls_to_check = []
    for i, suffix in enumerate(SUFFIXES):
        url = f"{BASE_URL}{code}_{suffix}?$desktopProductZoom$"
        urls_to_check.append((url, i))
    
    # Check all in parallel
    valid_images = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_single_image, args) for args in urls_to_check]
        for future in as_completed(futures):
            index, url, is_valid = future.result()
            if is_valid:
                valid_images.append((index, url))
    
    # Sort by suffix order and take max_images
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
    test_skus = ["CHCAF55-B4-MPL", "CHCAM16-B4-OL", "CHCCY32-B4-BK"]
    
    start = time.time()
    for sku in test_skus:
        result = scrape_coach(sku)
        print(f"{sku}: {result['count']} images")
    print(f"\n⏱️ Total: {time.time() - start:.2f}s")
