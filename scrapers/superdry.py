"""
Superdry Scraper Module
SKU format: SDM1012761A AUU or M1012761A AUU
Images: Random IDs on laguna-live CDN - must scrape website
"""

import requests
import re
import json

SCRAPER_API_KEY = "1ae7aa2a67a44259b694e92b2d069789"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9"
}


def parse_sku(sku):
    """
    Parse Superdry SKU to extract model and color code.
    SDM1012761A AUU -> model=M1012761A, color=AUU
    M1012761A AUU -> model=M1012761A, color=AUU
    """
    sku = sku.strip().upper()

    # Remove SD prefix if present
    if sku.startswith("SD"):
        sku = sku[2:]

    # Split by space
    parts = sku.split()
    if len(parts) >= 2:
        model = parts[0]  # M1012761A
        color = parts[1]  # AUU
        return model, color
    elif len(parts) == 1:
        # Try to split M1012761AAUU format
        match = re.match(r'(M\d{7}[A-Z]?)([A-Z]{2,4})', parts[0])
        if match:
            return match.group(1), match.group(2)
        return parts[0], None

    return None, None


def search_product(model, color=None):
    """Search for product on Superdry website"""

    # Build search query
    search_term = model
    if color:
        search_term = f"{model} {color}"

    # Use ScraperAPI for JS rendering
    search_url = f"https://www.superdry.com/search?q={search_term}"

    api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={search_url}&render=true"

    try:
        response = requests.get(api_url, timeout=60)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"Search error: {e}")

    return None


def extract_product_url(html, model, color=None):
    """Extract product URL from search results"""

    if not html:
        return None

    # Look for product links containing the model number
    # Pattern: /product/title-model-color
    patterns = [
        rf'href="(/[^"]*{model.lower()}[^"]*)"',
        rf'href="(https://www\.superdry\.com/[^"]*{model.lower()}[^"]*)"',
        r'href="(/product/[^"]+)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            # Filter by color if provided
            if color and color.lower() not in match.lower():
                continue

            if match.startswith('/'):
                return f"https://www.superdry.com{match}"
            return match

    return None


def extract_images_from_page(html):
    """Extract image URLs from product page"""

    images = []

    if not html:
        return images

    # Laguna-live CDN (primary)
    laguna_pattern = r'(https://images\.laguna-live\.sd\.co\.uk/[^"\'<>\s]+\.(?:jpg|png|webp))'
    laguna_images = re.findall(laguna_pattern, html)
    images.extend(laguna_images)

    # CDN-colect (alternative)
    colect_pattern = r'(https://images\.cdn-colect\.com/[^"\'<>\s]+\.(?:jpg|png|webp))'
    colect_images = re.findall(colect_pattern, html)
    images.extend(colect_images)

    # Superdry static CDN
    static_pattern = r'(https://static\.superdry\.com/[^"\'<>\s]+\.(?:jpg|png|webp))'
    static_images = re.findall(static_pattern, html)
    images.extend(static_images)

    # Deduplicate and filter
    unique_images = []
    seen = set()

    for img in images:
        # Get base URL without query params
        base = img.split('?')[0]

        # Skip thumbnails and small images
        if any(x in img.lower() for x in ['thumb', 'small', '100x', '50x', 'icon']):
            continue

        if base not in seen:
            seen.add(base)
            # Prefer zoom/large versions
            if 'zoom' in img or 'large' in img:
                unique_images.insert(0, img)
            else:
                unique_images.append(img)

    return unique_images


def get_product_page(url):
    """Fetch product page with ScraperAPI"""

    api_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}&render=true"

    try:
        response = requests.get(api_url, timeout=60)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"Product page error: {e}")

    return None


def scrape(sku, max_images=5):
    """
    Scrape images for a Superdry product.

    Args:
        sku: Product SKU (e.g., "SDM1012761A AUU" or "M1012761A AUU")
        max_images: Maximum number of images to return

    Returns:
        dict with sku, images, count, error
    """
    result = {
        "sku": sku,
        "model": "",
        "color": "",
        "brand_code": "SD",
        "product_url": "",
        "images": [],
        "count": 0,
        "error": None
    }

    try:
        # Parse SKU
        model, color = parse_sku(sku)
        if not model:
            result["error"] = f"Invalid SKU format: {sku}"
            return result

        result["model"] = model
        result["color"] = color or ""

        # Search for product
        print(f"Searching for {model} {color or ''}...")
        search_html = search_product(model, color)

        if not search_html:
            result["error"] = "Search failed"
            return result

        # Extract product URL
        product_url = extract_product_url(search_html, model, color)

        if not product_url:
            # Try extracting images directly from search results
            images = extract_images_from_page(search_html)
            if images:
                result["images"] = [{"url": img, "index": i+1} for i, img in enumerate(images[:max_images])]
                result["count"] = len(result["images"])
                return result

            result["error"] = "Product not found"
            return result

        result["product_url"] = product_url

        # Fetch product page
        print(f"Fetching product page: {product_url}")
        product_html = get_product_page(product_url)

        if not product_html:
            result["error"] = "Failed to fetch product page"
            return result

        # Extract images
        images = extract_images_from_page(product_html)

        if not images:
            result["error"] = "No images found on product page"
            return result

        # Format result
        result["images"] = []
        for i, img in enumerate(images[:max_images]):
            result["images"].append({
                "url": img,
                "index": i + 1,
                "filename": f"{sku.replace(' ', '_')}-{i + 1}.jpg"
            })

        result["count"] = len(result["images"])

    except Exception as e:
        result["error"] = str(e)

    return result


# Test
if __name__ == "__main__":
    test_skus = [
        "SDM1012761A AUU",
        "M1012210A OYC",
    ]

    for sku in test_skus:
        print(f"\nTesting: {sku}")
        result = scrape(sku, max_images=5)
        print(f"  Model: {result['model']}")
        print(f"  Color: {result['color']}")
        print(f"  URL: {result['product_url']}")
        print(f"  Found: {result['count']} images")
        if result['images']:
            for img in result['images']:
                print(f"    - {img['url'][:80]}...")
        if result['error']:
            print(f"  Error: {result['error']}")
