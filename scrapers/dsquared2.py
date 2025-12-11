"""
DSQUARED2 Scraper Module
Koristi search-based pristup + filtriranje po BOJI
"""

import requests
from bs4 import BeautifulSoup
import re
import time

# ============================================
# CONFIGURATION
# ============================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

HIGH_RES_PARAMS = "?sw=2000&sh=3000&sm=fit&q=100"
BASE_URL = "https://www.dsquared2.com"

# ============================================
# HELPER FUNCTIONS
# ============================================

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
    DQBCM0376-2124 → 2124
    DQS74GU0894-860M → 860M
    """
    if "-" in sku:
        return sku.split("-")[-1]
    return ""


def find_product_page(model_code: str, color_code: str, session: requests.Session) -> tuple:
    """
    Pronalazi product page za TAČNU BOJU.
    Vraća (pdp_url, html_content) ili (None, None)
    """
    # Pokušaj direktne URL-ove sa bojom
    # Format: model + middle_code + color (npr. S71GD1572D20035205)
    direct_patterns = [
        f"{BASE_URL}/us/{model_code}.html",
        f"{BASE_URL}/us/{model_code.lower()}.html",
    ]
    
    for url in direct_patterns:
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                # Proveri da li stranica sadrži našu boju
                if color_code.lower() in r.text.lower():
                    return (url, r.text)
        except:
            pass
        time.sleep(0.1)
    
    # Fallback: search sa modelom
    search_urls = [
        f"{BASE_URL}/us/search?q={model_code}",
        f"{BASE_URL}/search?q={model_code}",
        # Probaj i sa bojom
        f"{BASE_URL}/us/search?q={model_code}+{color_code}",
    ]
    
    for search_url in search_urls:
        try:
            r = session.get(search_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Traži link koji sadrži model I boju
            for a in soup.find_all("a", href=True):
                href = a["href"]
                href_lower = href.lower()
                
                # Prioritet: linkovi koji imaju i model i boju
                if model_code.lower() in href_lower and color_code.lower() in href_lower:
                    if href.startswith("http"):
                        pdp_url = href
                    elif href.startswith("/"):
                        pdp_url = BASE_URL + href
                    else:
                        pdp_url = BASE_URL + "/" + href
                    
                    pdp_r = session.get(pdp_url, headers=HEADERS, timeout=15)
                    if pdp_r.status_code == 200:
                        return (pdp_url, pdp_r.text)
            
            # Ako nema sa bojom, probaj samo model
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if model_code.lower() in href.lower():
                    if href.startswith("http"):
                        pdp_url = href
                    elif href.startswith("/"):
                        pdp_url = BASE_URL + href
                    else:
                        pdp_url = BASE_URL + "/" + href
                    
                    pdp_r = session.get(pdp_url, headers=HEADERS, timeout=15)
                    if pdp_r.status_code == 200 and color_code.lower() in pdp_r.text.lower():
                        return (pdp_url, pdp_r.text)
                        
        except:
            pass
        time.sleep(0.1)
    
    return (None, None)


def is_thumbnail(url: str) -> bool:
    """Proverava da li je thumbnail"""
    indicators = ['sw=50', 'sw=80', 'sw=100', 'sw=150', 'sw=200', 'sw=300',
                  'sh=50', 'sh=80', 'sh=100', 'sh=150', 'sh=200', 'sh=300']
    return any(ind in url.lower() for ind in indicators)


def is_product_image(url: str, model_code: str, color_code: str) -> bool:
    """
    Proverava da li je URL slika PROIZVODA za TAČNU BOJU.
    
    Vraća True samo ako:
    1. URL sadrži 'dw/image' (DSQUARED2 image CDN)
    2. URL sadrži model code
    3. URL sadrži color code (BITNO!)
    4. Nije thumbnail
    """
    url_lower = url.lower()
    
    # Mora biti sa image CDN-a
    if 'dw/image' not in url_lower:
        return False
    
    # Mora sadržati model
    if model_code.lower() not in url_lower:
        return False
    
    # MORA sadržati boju - OVO JE KLJUČNO!
    if color_code.lower() not in url_lower:
        return False
    
    # Ne sme biti thumbnail
    if is_thumbnail(url):
        return False
    
    # Izbaci poznate non-product slike
    bad_patterns = ['logo', 'banner', 'icon', 'sprite', 'placeholder', 'loading']
    if any(bad in url_lower for bad in bad_patterns):
        return False
    
    return True


def convert_to_high_res(url: str) -> str:
    """Konvertuje URL u high-res verziju"""
    return url.split("?")[0] + HIGH_RES_PARAMS


def extract_images(html: str, model_code: str, color_code: str, max_images: int = 5) -> list:
    """
    Izvlači high-res image URL-ove SAMO ZA TAČNU BOJU.
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    seen = set()
    
    # 1) <img src=...>
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if src.startswith("//"):
            src = "https:" + src
        
        if is_product_image(src, model_code, color_code):
            base = src.split("?")[0]
            if base not in seen:
                seen.add(base)
                urls.append(convert_to_high_res(src))
    
    # 2) data-src (lazy loading)
    for img in soup.find_all("img", attrs={"data-src": True}):
        src = img["data-src"]
        if src.startswith("//"):
            src = "https:" + src
        
        if is_product_image(src, model_code, color_code):
            base = src.split("?")[0]
            if base not in seen:
                seen.add(base)
                urls.append(convert_to_high_res(src))
    
    # 3) srcset
    for img in soup.find_all("img", attrs={"srcset": True}):
        srcset = img["srcset"]
        parts = srcset.split(",")
        for part in parts:
            part = part.strip()
            src = part.split()[0]
            if src.startswith("//"):
                src = "https:" + src
            
            if is_product_image(src, model_code, color_code):
                base = src.split("?")[0]
                if base not in seen:
                    seen.add(base)
                    urls.append(convert_to_high_res(src))
    
    # 4) Regex fallback u HTML-u
    if len(urls) < max_images:
        # Traži sve URL-ove slika u HTML-u
        found = re.findall(r'https?://[^"\']+dw/image/[^"\']+', html)
        for f in found:
            if is_product_image(f, model_code, color_code):
                base = f.split("?")[0]
                if base not in seen:
                    seen.add(base)
                    urls.append(convert_to_high_res(f))
    
    return urls[:max_images]


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
    # Izvuci MODEL i BOJU
    model_code = extract_model_code(sku)
    color_code = extract_color_code(sku)
    
    # Formatiraj SKU za imenovanje fajlova
    formatted_sku = sku if sku.startswith("DQ") else f"DQ{sku}"
    
    result = {
        "sku": sku,
        "formatted_sku": formatted_sku,
        "model_code": model_code,
        "color_code": color_code,
        "landing_page": "",
        "images": [],
        "count": 0,
        "error": None
    }
    
    # Proveri da li imamo boju
    if not color_code:
        result["error"] = f"No color code found in SKU: {sku}"
        return result
    
    # Pronađi product page
    session = requests.Session()
    pdp_url, html = find_product_page(model_code, color_code, session)
    
    if not pdp_url or not html:
        result["error"] = f"Product page not found for {model_code} color {color_code}"
        return result
    
    result["landing_page"] = pdp_url
    
    # Izvuci slike SAMO ZA OVU BOJU
    image_urls = extract_images(html, model_code, color_code, max_images)
    
    if not image_urls:
        result["error"] = f"No images found for color {color_code}"
        return result
    
    # Validiraj ako treba
    if validate:
        valid_urls = []
        for url in image_urls:
            try:
                r = session.head(url, headers=HEADERS, timeout=10)
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
    # Test sa različitim bojama istog modela
    test_skus = [
        "DQS71GD1572-205",    # Boja 205
        "DQS74GD1456-100",    # Boja 100
        "DQS74GD1456-900",    # Boja 900 (isti model, druga boja!)
        "DQS74GU0894-860M",   # Boja sa slovom
    ]
    
    for sku in test_skus:
        print(f"\n{'='*60}")
        print(f"Testing: {sku}")
        print(f"{'='*60}")
        
        result = scrape(sku, max_images=5, validate=False)
        
        print(f"Model: {result['model_code']}")
        print(f"Color: {result['color_code']}")
        print(f"Landing page: {result['landing_page']}")
        print(f"Images found: {result['count']}")
        
        if result['error']:
            print(f"Error: {result['error']}")
        
        for img in result['images']:
            print(f"  {img['filename']}: {img['url'][:70]}...")
