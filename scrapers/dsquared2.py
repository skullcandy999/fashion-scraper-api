"""
DSQUARED2 Scraper Module
Koristi lookup tabelu za mapiranje SKU -> full original code
Fallback na search ako SKU nije u tabeli
"""

import requests
from bs4 import BeautifulSoup
import re
import time

# Import lookup table
try:
    from scrapers.dsquared2_lookup import get_full_code, DSQUARED2_LOOKUP
except ImportError:
    from dsquared2_lookup import get_full_code, DSQUARED2_LOOKUP

# ============================================
# CONFIGURATION
# ============================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

HIGH_RES_PARAMS = "?sw=2000&sh=3000&sm=fit&q=100"
BASE_URL = "https://www.dsquared2.com"
TIMEOUT = 15

# ============================================
# HELPER FUNCTIONS
# ============================================

def request_url(url, timeout=TIMEOUT):
    """Simple request with error handling"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r
    except Exception as e:
        pass
    return None


def extract_model_code(sku: str) -> str:
    """
    Izvlači MODEL kod (bez boje).
    DQS71GD1572-205 → S71GD1572
    DQBCM0376-2124 → BCM0376
    """
    code = sku
    if code.startswith("DQ"):
        code = code[2:]
    if "-" in code:
        code = code.split("-")[0]
    return code


def extract_color_code(sku: str) -> str:
    """
    Izvlači BOJU iz SKU.
    DQS71GD1572-205 → 205
    """
    if "-" in sku:
        return sku.split("-")[-1]
    return ""


def find_pdp_by_original(original_code):
    """
    Traži PDP preko site search. Vraća prvi link koji u href sadrži original_code.
    """
    search_paths = [
        f"{BASE_URL}/us/search?q={original_code}",
        f"{BASE_URL}/us/search?text={original_code}",
        f"{BASE_URL}/search?q={original_code}",
        f"{BASE_URL}/search?text={original_code}"
    ]
    for url in search_paths:
        r = request_url(url)
        if not r:
            continue
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if original_code.lower() in href.lower():
                if href.startswith("http"):
                    return href
                if href.startswith("/"):
                    return BASE_URL + href
                return BASE_URL + "/" + href
        time.sleep(0.1)
    return None


def is_thumbnail(url):
    """Proverava da li je URL thumbnail (mala slika)."""
    thumbnail_indicators = [
        'sw=50', 'sw=80', 'sw=100', 'sw=150', 'sw=200', 'sw=300',
        'sh=50', 'sh=80', 'sh=100', 'sh=150', 'sh=200', 'sh=300',
        'thumb', 'small', 'mini', '_xs', '_sm'
    ]
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in thumbnail_indicators)


def convert_to_high_res(url):
    """Konvertuje URL slike u high-resolution verziju."""
    base_url = url.split("?")[0]
    return base_url + HIGH_RES_PARAMS


def extract_image_urls_from_pdp(html_text, original_code, max_images=5):
    """
    Parsira PDP i skuplja SAMO image URL-ove koji sadrže TAČAN original_code.
    Filtrira "Complete the Look" i druge proizvode.
    Vraća listu HIGH-RES URL-ova.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    urls = []
    seen_bases = set()
    original_lower = original_code.lower()

    # 1) Traži sve tagove <img src=...> koji MORAJU imati original code
    for img in soup.find_all("img", src=True):
        src = img["src"]
        # STRICT: mora sadržati original_code
        if original_lower not in src.lower():
            continue
        if "dw/image" not in src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        if is_thumbnail(src):
            continue
        base = src.split("?")[0]
        if base not in seen_bases:
            seen_bases.add(base)
            urls.append(convert_to_high_res(src))

    # 2) Traži data-src atribute (lazy loading slike)
    for img in soup.find_all("img", attrs={"data-src": True}):
        src = img["data-src"]
        # STRICT: mora sadržati original_code
        if original_lower not in src.lower():
            continue
        if "dw/image" not in src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        if is_thumbnail(src):
            continue
        base = src.split("?")[0]
        if base not in seen_bases:
            seen_bases.add(base)
            urls.append(convert_to_high_res(src))

    # 3) Traži srcset atribute - STRICT filtering
    for img in soup.find_all("img", attrs={"srcset": True}):
        srcset = img["srcset"]
        for part in srcset.split(","):
            part = part.strip()
            if original_lower not in part.lower():
                continue
            if "dw/image" not in part:
                continue
            src = part.split()[0]
            if src.startswith("//"):
                src = "https:" + src
            base = src.split("?")[0]
            if base not in seen_bases:
                seen_bases.add(base)
                urls.append(convert_to_high_res(src))

    # 4) Regex fallback - STRICT: pattern mora sadržati original_code
    if len(urls) < max_images:
        # Build pattern that requires original_code in URL
        pattern = r'https?://[^"\'\s]+dw/image/[^"\'\s]*' + re.escape(original_code) + r'[^"\'\s]*\.jpg'
        found = re.findall(pattern, html_text, re.IGNORECASE)
        for f in found:
            if is_thumbnail(f):
                continue
            base = f.split("?")[0]
            if base not in seen_bases:
                seen_bases.add(base)
                urls.append(convert_to_high_res(f))

    return urls[:max_images]


def find_product_page(original_code):
    """
    Pronalazi product page za dati original code.
    Vraća (pdp_url, html_content) ili (None, None)
    """
    # 1) Pokušaj direktne URL-ove
    candidate_urls = [
        f"{BASE_URL}/us/{original_code}.html",
        f"{BASE_URL}/us/{original_code.lower()}.html",
        f"{BASE_URL}/{original_code}.html",
    ]

    for url in candidate_urls:
        r = request_url(url)
        if r and original_code.lower() in r.text.lower():
            return (url, r.text)
        time.sleep(0.05)

    # 2) Fallback: search
    pdp = find_pdp_by_original(original_code)
    if pdp:
        r = request_url(pdp)
        if r:
            return (pdp, r.text)

    return (None, None)


# ============================================
# MAIN SCRAPE FUNCTION
# ============================================

def scrape(sku: str, max_images: int = 5, validate: bool = False) -> dict:
    """
    Glavna funkcija za scraping DSQUARED2 proizvoda.

    Args:
        sku: Fashion Company Code (npr. "DQS71GD1572-205")
        max_images: Maksimalan broj slika
        validate: Da li da validira URL-ove (sporije)

    Returns:
        dict sa sku, formatted_sku, images, count, landing_page
    """
    # Formatiraj SKU
    formatted_sku = sku.strip().upper()
    if not formatted_sku.startswith("DQ"):
        formatted_sku = f"DQ{formatted_sku}"

    # Izvuci MODEL i BOJU
    model_code = extract_model_code(formatted_sku)
    color_code = extract_color_code(formatted_sku)

    # Proveri lookup tabelu za full original code
    full_original = get_full_code(formatted_sku)
    in_lookup = full_original is not None

    result = {
        "sku": sku,
        "formatted_sku": formatted_sku,
        "model_code": model_code,
        "color_code": color_code,
        "full_original": full_original,
        "in_lookup": in_lookup,
        "landing_page": "",
        "images": [],
        "count": 0,
        "error": None
    }

    # Proveri da li imamo boju
    if not color_code:
        result["error"] = f"No color code found in SKU: {sku}"
        return result

    # Proveri da li imamo full_original iz lookup tabele
    if not full_original:
        result["error"] = f"SKU not in lookup table: {formatted_sku}"
        return result

    # Pronađi product page
    pdp_url, html = find_product_page(full_original)

    if not pdp_url or not html:
        result["error"] = f"Product page not found for {full_original}"
        return result

    result["landing_page"] = pdp_url

    # Izvuci slike
    image_urls = extract_image_urls_from_pdp(html, full_original, max_images)

    if not image_urls:
        result["error"] = f"No images found for {full_original}"
        return result

    # Validiraj ako treba
    if validate:
        valid_urls = []
        for url in image_urls:
            try:
                r = requests.head(url, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    valid_urls.append(url)
            except:
                pass
            time.sleep(0.1)
        image_urls = valid_urls

    # Kreiraj image objekte
    for idx, url in enumerate(image_urls, 1):
        result["images"].append({
            "url": url,
            "filename": f"{formatted_sku}-{idx}",
            "index": idx
        })

    result["count"] = len(result["images"])

    return result


# ============================================
# TEST
# ============================================

if __name__ == "__main__":
    test_skus = [
        "DQS71GD1609-100",
        "DQS74GD1456-100",
        "DQS74GD1456-900",
        "DQS74GU0894-860M",
    ]

    for sku in test_skus:
        print(f"\n{'='*60}")
        print(f"Testing: {sku}")
        print(f"{'='*60}")

        result = scrape(sku, max_images=5, validate=False)

        print(f"Full original: {result.get('full_original')}")
        print(f"Landing page: {result.get('landing_page')}")
        print(f"Images found: {result.get('count')}")

        if result.get('error'):
            print(f"Error: {result['error']}")

        for img in result.get('images', [])[:3]:
            print(f"  {img['filename']}: {img['url'][:70]}...")
