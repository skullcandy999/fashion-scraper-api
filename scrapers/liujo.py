"""
LIU JO Scraper Module
Scrapes product images from liujo.com

SKU Format Mapping:
- Our format: LJAA6096 E0958 00070
- Their format: AA6096E095800070 (remove LJ prefix, join without spaces)

Strategy:
1. Convert our SKU to Liu Jo format
2. Search their site with partial SKU
3. Find product URL in search results
4. Extract all image URLs from product page
"""

import requests
from requests.adapters import HTTPAdapter, Retry
import re
import hashlib
import time

# ===================== CONFIGURATION =====================
BASE_URL = "https://www.liujo.com"
SEARCH_URL = f"{BASE_URL}/int/search"
TIMEOUT = 20
MIN_BYTES = 5000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ===================== HTTP SESSION =====================
def make_session():
    """Create HTTP session with retry logic"""
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.headers.update(HEADERS)
    return s

# ===================== HELPERS =====================
def sha1_hash(content: bytes) -> str:
    """Generate SHA1 hash for deduplication"""
    return hashlib.sha1(content).hexdigest()

def convert_sku(our_sku: str) -> str:
    """
    Convert our SKU format to Liu Jo format

    Our format: LJAA6096 E0958 00070 or LJ2A6001 T0300 00133
    Their format: AA6096E095800070 or 2A6001T030000133

    Rule: Remove LJ prefix, join all parts without spaces
    """
    sku = our_sku.strip().upper()
    if sku.startswith("LJ"):
        sku = sku[2:]
    sku = sku.replace(" ", "")
    return sku

def search_product(session, sku: str) -> dict:
    """
    Search Liu Jo website for a product
    Returns: {found: bool, product_url: str, liujo_sku: str}
    """
    liujo_sku = convert_sku(sku)

    try:
        # Search with partial SKU (model + material, ~11 chars)
        # This gives best results without being too specific
        search_term = liujo_sku[:11] if len(liujo_sku) >= 11 else liujo_sku

        response = session.get(
            SEARCH_URL,
            params={"q": search_term},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        html = response.text

        # Method 1: Find product URL directly in href attributes
        # Pattern: /int/[product-name]-[SKU]T.U..html
        href_pattern = r'href="(/int/[^"]+' + re.escape(liujo_sku) + r'[^"]*\.html)"'
        matches = re.findall(href_pattern, html, re.IGNORECASE)

        if matches:
            product_url = f"{BASE_URL}{matches[0]}"
            return {"found": True, "product_url": product_url, "liujo_sku": liujo_sku}

        # Method 2: Find any URL containing our SKU
        all_urls = re.findall(r'href="(/int/[^"]+\.html)"', html)
        for url in all_urls:
            if liujo_sku.upper() in url.upper():
                product_url = f"{BASE_URL}{url}"
                return {"found": True, "product_url": product_url, "liujo_sku": liujo_sku}

        # Method 3: Try broader search with just model code
        if len(liujo_sku) > 6:
            model_code = liujo_sku[:6]
            time.sleep(0.5)  # Rate limiting

            response = session.get(
                SEARCH_URL,
                params={"q": model_code},
                timeout=TIMEOUT
            )
            response.raise_for_status()
            html = response.text

            all_urls = re.findall(r'href="(/int/[^"]+\.html)"', html)
            for url in all_urls:
                if liujo_sku.upper() in url.upper():
                    product_url = f"{BASE_URL}{url}"
                    return {"found": True, "product_url": product_url, "liujo_sku": liujo_sku}

        return {"found": False, "product_url": None, "liujo_sku": liujo_sku}

    except Exception as e:
        return {"found": False, "product_url": None, "liujo_sku": liujo_sku, "error": str(e)}

def extract_images_from_page(session, product_url: str, liujo_sku: str) -> list:
    """
    Extract all product images from a product page
    Returns list of image URLs
    """
    try:
        response = session.get(product_url, timeout=TIMEOUT)
        response.raise_for_status()
        html = response.text

        images = []
        seen_urls = set()

        # Pattern for Liu Jo image URLs on Demandware CDN
        # Example: https://www.liujo.com/dw/image/v2/BDNR_PRD/on/demandware.static/-/Sites-liujo-master-catalog/default/dw.../images/8059524691340---AA6096E095800070-S-AF-N-N-6-N.jpg
        img_pattern = r'(https?://[^"\s]+/dw/image/v2/[^"\s]+' + re.escape(liujo_sku) + r'[^"\s]+\.jpg)'
        matches = re.findall(img_pattern, html, re.IGNORECASE)

        for url in matches:
            # Clean URL
            clean_url = url.split("?")[0]
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                # Add high-res params
                full_url = f"{clean_url}?sw=1200&sh=1600&q=90"
                images.append(full_url)

        # Also try to find images in data attributes and srcset
        # Pattern for any demandware image with our SKU
        broader_pattern = r'((?:https?:)?//[^"\s]*demandware\.static[^"\s]*' + re.escape(liujo_sku) + r'[^"\s]*\.(?:jpg|jpeg|png|webp))'
        broader_matches = re.findall(broader_pattern, html, re.IGNORECASE)

        for url in broader_matches:
            if url.startswith("//"):
                url = "https:" + url
            clean_url = url.split("?")[0]
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                full_url = f"{clean_url}?sw=1200&sh=1600&q=90"
                images.append(full_url)

        # Look in JSON data (often used for galleries)
        json_img_pattern = r'"(https?:[^"]+demandware\.static[^"]+\.jpg)"'
        json_matches = re.findall(json_img_pattern, html)

        for url in json_matches:
            url = url.replace("\\u002F", "/")
            if liujo_sku.upper() in url.upper():
                clean_url = url.split("?")[0]
                if clean_url not in seen_urls:
                    seen_urls.add(clean_url)
                    full_url = f"{clean_url}?sw=1200&sh=1600&q=90"
                    images.append(full_url)

        return images

    except Exception as e:
        print(f"Error extracting images: {e}")
        return []

def validate_image(session, url: str) -> tuple:
    """Check if URL returns valid image. Returns (is_valid, content, hash)"""
    try:
        r = session.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and r.content and len(r.content) > MIN_BYTES:
            content_type = r.headers.get("Content-Type", "").lower()
            if "image" in content_type or len(r.content) > 10000:
                return True, r.content, sha1_hash(r.content)
        return False, None, None
    except Exception:
        return False, None, None

def scrape(sku: str, max_images: int = 5, validate: bool = False) -> dict:
    """
    Main scrape function for LIU JO

    Args:
        sku: Our SKU format (e.g., "LJAA6096 E0958 00070")
        max_images: Maximum number of images to return
        validate: Whether to validate images exist

    Returns:
        dict with sku, images, count, etc.
    """
    result = {
        "sku": sku,
        "formatted_sku": sku.replace(" ", "_"),
        "brand": "LIU JO",
        "images": [],
        "count": 0,
        "landing_page": None,
        "error": None
    }

    session = make_session()

    try:
        # Step 1: Search for product
        search_result = search_product(session, sku)

        if not search_result.get("found"):
            result["error"] = f"Product not found for SKU: {sku} (searched as: {search_result.get('liujo_sku')})"
            return result

        result["landing_page"] = search_result["product_url"]
        result["liujo_sku"] = search_result["liujo_sku"]

        # Step 2: Extract images from product page
        time.sleep(0.3)  # Small delay between requests
        image_urls = extract_images_from_page(session, search_result["product_url"], search_result["liujo_sku"])

        if not image_urls:
            result["error"] = "No images found on product page"
            return result

        # Step 3: Process images (remove duplicates, limit count)
        images = []
        seen_hashes = set()
        formatted_sku = sku.replace(" ", "_")

        for url in image_urls:
            if len(images) >= max_images:
                break

            if validate:
                is_valid, content, img_hash = validate_image(session, url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({
                        "url": url,
                        "index": len(images) + 1,
                        "filename": f"{formatted_sku}-{len(images) + 1}"
                    })
            else:
                images.append({
                    "url": url,
                    "index": len(images) + 1,
                    "filename": f"{formatted_sku}-{len(images) + 1}"
                })

        result["images"] = images
        result["count"] = len(images)

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


# ===================== TEST =====================
if __name__ == "__main__":
    # Test SKUs from user's list
    test_skus = [
        "LJAA6096 E0958 00070",  # Should find: Medium Riccy shoulder bag (Camel)
        "LJAA6096 E0958 01679",  # Should find: Medium Riccy shoulder bag (Mud)
    ]

    for sku in test_skus:
        print(f"\n{'='*60}")
        print(f"Testing SKU: {sku}")
        print(f"Converted: {convert_sku(sku)}")

        result = scrape(sku, max_images=5, validate=False)

        print(f"Found: {result['count']} images")
        print(f"Landing page: {result.get('landing_page')}")
        if result.get('error'):
            print(f"Error: {result['error']}")

        for img in result.get('images', [])[:3]:
            print(f"  - {img['filename']}: {img['url'][:80]}...")
