# -*- coding: utf-8 -*-
"""
JOOP Scraper Module
Za korišćenje sa Flask API
Hybris CDN - mora da pretražuje sajt
"""

import re
import requests
from requests.adapters import HTTPAdapter, Retry

TIMEOUT = (5, 15)
MIN_SIZE = 5000

# Session
def make_session():
    s = requests.Session()
    retries = Retry(total=2, backoff_factor=0.3)
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retries)
    s.mount("https://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124",
        "Accept": "text/html,application/xhtml+xml",
    })
    return s

SESSION = make_session()


def convert_sku(sku):
    """
    JP10017927-00030-001 → 30100030-10017927-001
    - Ukloni JP
    - Zameni prvi i drugi deo
    - Dodaj 301 ispred drugog dela (koji postaje prvi)
    """
    clean = sku.strip()
    if clean.startswith('JP'):
        clean = clean[2:]

    parts = clean.split('-')
    if len(parts) == 3:
        part1 = parts[0]  # 10017927
        part2 = parts[1]  # 00030
        color = parts[2]  # 001
        return f"301{part2}-{part1}-{color}"
    return None


def search_product(joop_code):
    """Traži proizvod na Joop sajtu"""
    search_url = f"https://joop.com/int/en/search?text={joop_code}"
    
    try:
        r = SESSION.get(search_url, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        
        # Traži link do proizvoda
        pattern = rf'/p/{re.escape(joop_code)}'
        match = re.search(pattern, r.text)
        
        if match:
            return f"https://joop.com{match.group()}"
        
        # Probaj bez boje
        code_no_color = '-'.join(joop_code.split('-')[:2])
        pattern2 = rf'/p/{re.escape(code_no_color)}-\d+'
        match2 = re.search(pattern2, r.text)
        if match2:
            return f"https://joop.com{match2.group()}"
        
        return None
    except:
        return None


def get_images_from_page(url):
    """Izvlači URL-ove slika sa stranice proizvoda"""
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        
        # Traži slike iz medias/sys_master
        pattern = r'https://joop\.com/medias/sys_master/images/images/[^"\'>\s]+'
        matches = re.findall(pattern, r.text)
        
        # Dedupliciraj i filtriraj
        seen = set()
        images = []
        for img_url in matches:
            clean = img_url.split('?')[0]
            if clean.endswith('.jpg') and clean not in seen:
                seen.add(clean)
                images.append(clean)
        
        return images
    except:
        return []


def validate_image(url):
    """Proveri da li slika postoji i vraća content"""
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and len(r.content) > MIN_SIZE:
            return True, r.content
        return False, None
    except:
        return False, None


def scrape(sku, max_images=5, validate=True):
    """
    Glavni scrape funkcija
    Vraća dict sa rezultatima
    """
    result = {
        "sku": sku,
        "formatted_sku": sku,
        "joop_code": "",
        "images": [],
        "count": 0,
        "error": None
    }
    
    # Konvertuj SKU
    joop_code = convert_sku(sku)
    if not joop_code:
        result["error"] = f"Invalid SKU format: {sku}"
        return result
    
    result["joop_code"] = joop_code
    
    # Nađi stranicu proizvoda
    product_url = search_product(joop_code)
    if not product_url:
        result["error"] = f"Product not found: {joop_code}"
        return result
    
    result["product_url"] = product_url
    
    # Izvuci slike
    image_urls = get_images_from_page(product_url)
    if not image_urls:
        result["error"] = "No images found on product page"
        return result
    
    # Validiraj i dodaj slike
    images = []
    for i, url in enumerate(image_urls):
        if len(images) >= max_images:
            break
        
        if validate:
            is_valid, _ = validate_image(url)
            if not is_valid:
                continue
        
        images.append({
            "url": url,
            "index": len(images) + 1,
            "filename": f"{sku.replace('-', '_')}-{len(images) + 1}"
        })
    
    result["images"] = images
    result["count"] = len(images)
    
    return result
