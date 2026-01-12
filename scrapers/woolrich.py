# -*- coding: utf-8 -*-
"""
WOOLRICH Scraper Module
Za korišćenje sa Flask API
Pretražuje woolrich.com sajt
"""

import re
import requests
from bs4 import BeautifulSoup
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
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120",
        "Accept": "text/html,application/xhtml+xml",
    })
    return s

SESSION = make_session()

BASES = [
    "https://www.woolrich.com/eu/en/",
    "https://www.woolrich.com/us/en/",
]


def convert_sku(sku):
    """
    WKN0278MRUF0469-7417 → CFWOWKN0278MRUF0469_7417 (muško)
    Vraća listu kandidata (CFWO za muško, CFWW za žensko)
    """
    if "-" in sku:
        style, color = sku.split("-", 1)
    else:
        style, color = sku, ""
    
    candidates = []
    for prefix in ["CFWO", "CFWW"]:
        code = f"{prefix}{style}_{color}" if color else f"{prefix}{style}"
        img_token = code.replace("_", "-")
        candidates.append((code, img_token))
    
    return candidates


def find_product_url(their_code):
    """Traži proizvod na sajtu"""
    for base in BASES:
        search_url = f"{base}search?q={their_code}"
        
        try:
            r = SESSION.get(search_url, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            
            soup = BeautifulSoup(r.text, "html.parser")
            a = soup.find("a", href=re.compile(re.escape(their_code) + r"\.html", re.I))
            
            if a and a.get("href"):
                href = a["href"]
                if href.startswith("/"):
                    return base.rstrip("/") + href
                elif href.startswith("http"):
                    return href
                else:
                    return base + href
        except:
            continue
    
    return None


def extract_images(html, img_token):
    """Izvuci URL-ove slika"""
    urls = []
    
    # Regex za CDN slike
    for m in re.finditer(r'https://[^"\']+woolrich[^"\']+/' + re.escape(img_token) + r'\.jpg[^"\']*', html, re.I):
        urls.append(m.group(0))
    
    # Deduplikuj
    seen = set()
    clean = []
    for u in urls:
        if u.startswith("//"):
            u = "https:" + u
        u = u.replace("&amp;", "&")
        if u not in seen:
            seen.add(u)
            clean.append(u)
    
    return clean


def validate_image(url):
    """Proveri da li slika postoji"""
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
        "woolrich_code": "",
        "images": [],
        "count": 0,
        "error": None
    }
    
    # Konvertuj SKU - dobijamo listu kandidata
    candidates = convert_sku(sku)
    if not candidates:
        result["error"] = f"Invalid SKU format: {sku}"
        return result
    
    # Probaj svaki kandidat
    for their_code, img_token in candidates:
        product_url = find_product_url(their_code)
        if not product_url:
            continue
        
        try:
            r = SESSION.get(product_url, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            
            image_urls = extract_images(r.text, img_token)
            if not image_urls:
                continue
            
            result["woolrich_code"] = their_code
            result["product_url"] = product_url
            
            # Validiraj i dodaj slike
            images = []
            for url in image_urls:
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
            
            if images:
                result["images"] = images
                result["count"] = len(images)
                return result
        except:
            continue
    
    result["error"] = f"Product not found for any variant"
    return result
