# -*- coding: utf-8 -*-
"""
FALKE Scraper Module
Za korišćenje sa Flask API
Zahteva website search
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from io import BytesIO

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

TIMEOUT = 25
MIN_SIZE = 8000
PAUSE = 0.5

LOCALES = ["uk_en", "en", "de_en", "de_de"]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,de;q=0.6",
    "Referer": "https://www.falke.com/",
})


def convert_sku(sku):
    """
    FA14633-3000 → 14633_3000
    """
    m = re.match(r"FA(\d+)-(\d+)", sku.strip())
    if not m:
        return ""
    return f"{m.group(1)}_{m.group(2)}"


def get_url(url):
    """HTTP GET with retry"""
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                return r
            time.sleep(PAUSE + attempt * 0.3)
        except:
            time.sleep(PAUSE)
    return None


def find_product_url(their_code):
    """Search for product on Falke website"""
    for loc in LOCALES:
        for q in (their_code, their_code.replace("_", " ")):
            search_url = f"https://www.falke.com/{loc}/search?q={quote_plus(q)}"
            rs = get_url(search_url)
            if not rs:
                continue
            
            soup = BeautifulSoup(rs.text, "html.parser")
            
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if their_code in href and "/p/" in href:
                    if href.startswith("//"):
                        prod_url = "https:" + href
                    elif href.startswith("/"):
                        prod_url = urljoin(search_url, href)
                    else:
                        prod_url = href
                    
                    rp = get_url(prod_url)
                    if rp and their_code in rp.text:
                        return rp.url, rp.text
    
    return "", ""


def extract_images(html):
    """Extract image URLs from product page"""
    if not html:
        return []
    
    candidates = re.findall(
        r"https://static\.falke\.com/(?:pdmain|pdzoom)/[^\s\"']+?\.jpg",
        html
    )
    
    seen = set()
    out = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def download_image(url):
    """Download and validate image"""
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=TIMEOUT, stream=True)
            if r.status_code == 200:
                content = r.content
                if content and len(content) >= MIN_SIZE:
                    if HAS_PIL:
                        try:
                            Image.open(BytesIO(content)).verify()
                            return content
                        except:
                            pass
                    else:
                        return content
            time.sleep(PAUSE)
        except:
            time.sleep(PAUSE)
    return None


def scrape(sku, max_images=5, validate=True):
    """Main scrape function"""
    result = {
        "sku": sku,
        "formatted_sku": sku,
        "brand_code": "",
        "product_url": "",
        "images": [],
        "count": 0,
        "error": None
    }
    
    their_code = convert_sku(sku)
    if not their_code:
        result["error"] = f"Invalid SKU format: {sku}"
        return result
    
    result["brand_code"] = their_code
    
    prod_url, prod_html = find_product_url(their_code)
    if not prod_url:
        result["error"] = "Product not found on website"
        return result
    
    result["product_url"] = prod_url
    
    gallery = extract_images(prod_html)
    if not gallery:
        result["error"] = "No images found on product page"
        return result
    
    images = []
    for url in gallery[:max_images]:
        if validate:
            data = download_image(url)
            if not data:
                continue
        
        images.append({
            "url": url,
            "index": len(images) + 1,
            "filename": f"{sku}-{len(images) + 1}"
        })
    
    if images:
        result["images"] = images
        result["count"] = len(images)
    else:
        result["error"] = "Failed to download images"
    
    return result
