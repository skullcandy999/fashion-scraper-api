"""
Golden Goose Scraper - Static CDN (PARALLEL)
Endpoint: /scrape-golden-goose
"""

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

TIMEOUT = 10
MIN_VALID_BYTES = 5000
MAX_WORKERS = 5  # Check all 5 images in parallel


def convert_sku(sku):
    """
    Convert SKU format: GGMF667 10502 F7555 → GMF00667.F007555.10502
    """
    # Handle both space and dash separators
    sku = sku.replace("-", " ")
    parts = sku.split()
    
    if len(parts) != 3:
        return None
    
    part1, part2, part3 = parts
    
    # GGMF667 → GMF00667
    # Remove first G, keep MF/WF/WP, pad number
    prefix = part1[1:3]  # MF, WF, WP
    number = part1[4:] if len(part1) > 4 else part1[3:]
    formatted_part1 = f"G{prefix}{number.zfill(5)}"
    
    # F7555 → F007555
    formatted_part2 = f"F{part3[1:].zfill(6)}"
    
    # Middle number stays as is
    formatted_part3 = part2
    
    return f"{formatted_part1}.{formatted_part2}.{formatted_part3}"


def check_single_image(args):
    """Check single image URL - for parallel execution"""
    url, index = args
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if response.status_code == 200 and len(response.content) > MIN_VALID_BYTES:
            return (index, url, True)
    except:
        pass
    return (index, url, False)


def scrape_golden_goose(sku, max_images=5):
    """
    Scrape Golden Goose product images - PARALLEL
    
    Args:
        sku: Product SKU (e.g., "GGMF667 10502 F7555")
        max_images: Maximum number of images to return
    
    Returns:
        dict with 'images' list containing image URLs
    """
    formatted_sku = convert_sku(sku)
    
    if not formatted_sku:
        return {"sku": sku, "images": [], "count": 0, "error": "Invalid SKU format"}
    
    # Base URL with dashes instead of dots
    base_url = f"https://static2.goldengoose.com/public/Style/ECOMM/{formatted_sku.replace('.', '-')}"
    
    # Build all URLs to check
    urls_to_check = []
    for i in range(1, max_images + 1):
        if i == 1:
            url = f"{base_url}.jpg?im=Resize=(1200)"
        else:
            url = f"{base_url}-{i}.jpg?im=Resize=(1200)"
        urls_to_check.append((url, i))
    
    # Check all in parallel
    valid_images = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_single_image, args) for args in urls_to_check]
        for future in as_completed(futures):
            index, url, is_valid = future.result()
            if is_valid:
                valid_images.append((index, url))
    
    # Sort by index order
    valid_images.sort(key=lambda x: x[0])
    
    images = []
    for _, url in valid_images:
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
        "GGMF667 10502 F7555",
        "GGWF101 12282 F7539",
        "GGMF101 15430 F4164"
    ]
    
    start = time.time()
    for sku in test_skus:
        result = scrape_golden_goose(sku)
        print(f"{sku}: {result['count']} images")
    print(f"\n⏱️ Total: {time.time() - start:.2f}s")
