"""
Diesel Scraper Module
SKU format: DSX10464 P8768 HB176 → X10464_P8768_HB176
CDN: shop.diesel.com/dw/image/v2/BBLG_PRD
"""

import requests
import re

# CDN base URL
CDN_BASE = "https://shop.diesel.com/dw/image/v2/BBLG_PRD/on/demandware.static/-/Sites-diesel-master-catalog/default/images/large"

# Image suffixes to try
IMAGE_SUFFIXES = [
    "_C.jpg",      # Main/catalog image
    "_1.jpg",
    "_2.jpg", 
    "_3.jpg",
    "_4.jpg",
    "_5.jpg",
    "_6.jpg",
    "_7.jpg",
    "_8.jpg",
    "_F.jpg",      # Front
    "_B.jpg",      # Back
    "_D.jpg",      # Detail
    "_E.jpg",      # Extra
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.diesel.com/"
}


def format_sku(sku):
    """
    Convert SKU to Diesel CDN format.
    DSX10464 P8768 HB176 → X10464_P8768_HB176
    """
    sku = sku.strip().upper()
    
    # Remove DS prefix if present
    if sku.startswith("DS"):
        sku = sku[2:]
    
    # Replace spaces with underscores
    sku = sku.replace(" ", "_")
    
    # Remove any double underscores
    sku = re.sub(r'_+', '_', sku)
    
    return sku


def check_image(url):
    """Check if image URL exists and is valid"""
    try:
        response = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'image' in content_type:
                return True
        return False
    except:
        return False


def get_image_content(url):
    """Get image content to verify it's not a placeholder"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200 and len(response.content) > 5000:
            return True
        return False
    except:
        return False


def scrape(sku, max_images=5, validate=True):
    """
    Scrape images for a Diesel product.
    
    Args:
        sku: Product SKU (e.g., "DSX10464 P8768 HB176")
        max_images: Maximum number of images to return
        validate: Whether to validate image URLs
    
    Returns:
        dict with sku, images, count, error
    """
    result = {
        "sku": sku,
        "formatted_sku": "",
        "brand_code": "DS",
        "product_url": "",
        "images": [],
        "count": 0,
        "error": None
    }
    
    try:
        formatted = format_sku(sku)
        result["formatted_sku"] = formatted
        
        # Build product URL
        result["product_url"] = f"https://www.diesel.com/search?q={formatted}"
        
        found_images = []
        seen_urls = set()
        
        # Try each suffix
        for suffix in IMAGE_SUFFIXES:
            if len(found_images) >= max_images:
                break
            
            url = f"{CDN_BASE}/{formatted}{suffix}"
            
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Validate if requested
            if validate:
                if check_image(url) and get_image_content(url):
                    found_images.append({
                        "url": url,
                        "index": len(found_images) + 1,
                        "filename": f"{sku.replace(' ', '_')}-{len(found_images) + 1}.jpg"
                    })
            else:
                found_images.append({
                    "url": url,
                    "index": len(found_images) + 1,
                    "filename": f"{sku.replace(' ', '_')}-{len(found_images) + 1}.jpg"
                })
        
        # If no images found with standard format, try alternative formats
        if not found_images:
            # Try without underscores
            alt_formatted = formatted.replace("_", "")
            for suffix in IMAGE_SUFFIXES[:5]:
                if len(found_images) >= max_images:
                    break
                
                url = f"{CDN_BASE}/{alt_formatted}{suffix}"
                
                if validate:
                    if check_image(url) and get_image_content(url):
                        found_images.append({
                            "url": url,
                            "index": len(found_images) + 1,
                            "filename": f"{sku.replace(' ', '_')}-{len(found_images) + 1}.jpg"
                        })
        
        result["images"] = found_images
        result["count"] = len(found_images)
        
        if not found_images:
            result["error"] = "No images found"
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


# Test
if __name__ == "__main__":
    test_skus = [
        "DSX10464 P8768 HB176",
        "DSA03412 0AFAV 9XX",
    ]
    
    for sku in test_skus:
        print(f"\nTesting: {sku}")
        result = scrape(sku, max_images=5, validate=True)
        print(f"  Formatted: {result['formatted_sku']}")
        print(f"  Found: {result['count']} images")
        if result['images']:
            for img in result['images']:
                print(f"    - {img['url']}")
        if result['error']:
            print(f"  Error: {result['error']}")
