"""
Levi's Scraper - Scene7 CDN (ULTRA FAST)
Endpoint: /scrape-levis

NO VALIDATION - just generates URLs with all prefix combinations.
Workflow API validates during download (same as other brands).

URL Format: https://lscoglobal.scene7.com/is/image/lscoglobal/{PREFIX}_{SKU}_{MIDDLE}{VIEW}
"""

# Config
BASE_URL = "https://lscoglobal.scene7.com/is/image/lscoglobal"
QS = "?fmt=webp&qlt=70&resMode=sharp2&fit=crop,1&op_usm=0.6,0.6,8&wid=1760&hei=1760"

# Most common prefixes (ordered by likelihood for Levi's - jeans dominant)
PREFIXES = ["MB_", "WB_", "MT_", "WT_"]

# Most common middle
MIDDLE = "GLO_CM_"

# View suffixes
VIEWS = ["DA", "FV", "BV", "SV", "D1"]


def convert_sku(sku):
    """Convert SKU - keep the dash! LV000LO-0033 -> 000LO-0033"""
    code = sku.strip().upper()
    if code.startswith("LV"):
        code = code[2:]
    return code


def scrape_levis(sku, max_images=5):
    """
    ULTRA FAST Levi's scraper - NO HTTP requests!

    Generates URLs for all common prefix combinations.
    Workflow API will filter invalid ones during download.

    Returns up to max_images * len(PREFIXES) URLs for workflow to try.
    """
    sku_code = convert_sku(sku)

    if not sku_code:
        return {"sku": sku, "images": [], "count": 0, "error": "Invalid SKU format"}

    # Generate URLs for all prefixes - workflow will filter
    images = []
    idx = 1

    for prefix in PREFIXES:
        for view in VIEWS[:max_images]:
            url = f"{BASE_URL}/{prefix}{sku_code}_{MIDDLE}{view}{QS}"
            images.append({
                "url": url,
                "index": idx
            })
            idx += 1

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
