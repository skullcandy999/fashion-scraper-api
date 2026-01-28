# -*- coding: utf-8 -*-
"""
JOOP Scraper Module
Za korišćenje sa Flask API
Hybris CDN - mora da pretražuje sajt

Uses lookup table for SKU conversion (prefix varies: 300, 301, etc.)
"""

import re
import requests
from requests.adapters import HTTPAdapter, Retry

# Import lookup table
try:
    from scrapers.joop_lookup import get_joop_code, normalize_our_sku, JOOP_LOOKUP
except ImportError:
    from joop_lookup import get_joop_code, normalize_our_sku, JOOP_LOOKUP

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
    Convert our SKU to JOOP code.

    1. First try lookup table (handles different prefixes: 300, 301, etc.)
    2. Fallback to algorithmic conversion with 301 prefix

    JP10017927-00030-01 → 30100030-10017927-01
    """
    sku = sku.strip().upper()
    if not sku.startswith('JP'):
        sku = 'JP' + sku

    # Try lookup first
    joop_code = get_joop_code(sku)
    if joop_code:
        return joop_code

    # Fallback: algorithmic with 301 prefix
    clean = sku
    if clean.startswith('JP'):
        clean = clean[2:]

    parts = clean.split('-')
    if len(parts) == 3:
        model = parts[0]   # 10017927
        middle = parts[1]  # 00030
        color = parts[2]   # 01
        return f"301{middle}-{model}-{color}"

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
    sku_normalized = sku.strip().upper()
    if not sku_normalized.startswith('JP'):
        sku_normalized = 'JP' + sku_normalized

    result = {
        "sku": sku,
        "formatted_sku": sku_normalized.replace('-', '_'),
        "joop_code": "",
        "in_lookup": False,
        "images": [],
        "count": 0,
        "error": None
    }

    # Check if in lookup
    lookup_code = get_joop_code(sku_normalized)
    result["in_lookup"] = lookup_code is not None

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
