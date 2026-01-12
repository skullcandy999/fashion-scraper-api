# -*- coding: utf-8 -*-
"""
ENTERPRISE JAPAN Scraper Module
Za korišćenje sa Flask API
Zahteva PDP scraping
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

TIMEOUT = 20
MIN_SIZE = 10000
MAX_WORKERS = 8

BASE = "https://www.enterprise-japan.com"
FILES = f"{BASE}/cdn/shop/files"
PDP = f"{BASE}/en/products"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124",
    "Accept-Language": "en-US,en;q=0.8",
})


def convert_sku(code):
    """
    EJBG5001-PX704-S3752 → ['bg5001px704s3752']
    EJBG5013-PX758-04370 → ['bg5013px75804370', 'bg5013px758s04370']
    EJMBG5017-PX65001040 → ['bg5017px65001040']
    """
    s = code.strip().upper().replace(" ", "")
    m = re.match(r"^EJ(M)?BG(\d+)-PX([A-Z0-9]+)(?:-([A-Z0-9]+))?$", s)
    if not m:
        return []
    _, digits, px, tail = m.groups()
    base = f"bg{digits.lower()}px{px.lower()}"
    if not tail:
        return [base]
    tail_l = tail.lower()
    if tail_l.startswith("s"):
        return [base + tail_l]
    else:
        return [base + tail_l, base + "s" + tail_l]


def try_cdn_guess(handle):
    """Pogađa direktno CDN fajlove"""
    names = [handle.upper(), handle.lower()]
    suffixes = [""] + [f"_{i}" for i in range(1, 11)]
    exts = ["jpg", "jpeg", "webp", "png"]
    
    ok = []
    for nm in names:
        for suf in suffixes:
            for ext in exts:
                url = f"{FILES}/{nm}{suf}.{ext}"
                try:
                    r = SESSION.head(url, timeout=TIMEOUT, allow_redirects=True)
                    ctype = r.headers.get("Content-Type", "").lower()
                    if r.status_code == 200 and "image" in ctype:
                        ok.append(url)
                except:
                    pass
    
    seen, uniq = set(), []
    for u in ok:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def fetch_image(url):
    """Download image and return bytes"""
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type", "").lower():
            if len(r.content) > MIN_SIZE:
                return r.content
    except:
        pass
    return None


def from_pdp(handle):
    """Scrape product page for images"""
    purl = f"{PDP}/{handle}"
    try:
        r = SESSION.get(purl, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None, []
    except:
        return None, []
    
    soup = BeautifulSoup(r.text, "html.parser")
    cand = []
    
    for img in soup.select("img[src], img[data-src]"):
        for attr in ("src", "data-src"):
            u = img.get(attr)
            if u and "/cdn/shop/" in u:
                cand.append(urljoin(purl, u))
    
    for s in soup.select("source[srcset]"):
        for part in (s.get("srcset") or "").split(","):
            u = part.strip().split(" ")[0]
            if u and "/cdn/shop/" in u:
                cand.append(urljoin(purl, u))
    
    cand += re.findall(r"https://[^\"']+/cdn/shop/[^\"']+\.(?:jpg|jpeg|png|webp)", r.text, flags=re.I)
    
    cleaned = [u.split("?")[0] for u in cand]
    seen, uniq = set(), []
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    
    return r.url, uniq


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
    
    handles = convert_sku(sku)
    if not handles:
        result["error"] = f"Invalid SKU format: {sku}"
        return result
    
    images = []
    tried_urls = set()
    product_url = ""
    
    # 1) Try CDN guess first
    for h in handles:
        guesses = try_cdn_guess(h)
        for url in guesses:
            if url in tried_urls or len(images) >= max_images:
                continue
            tried_urls.add(url)
            
            if validate:
                data = fetch_image(url)
                if not data:
                    continue
            
            images.append({
                "url": url,
                "index": len(images) + 1,
                "filename": f"{sku}-{len(images) + 1}"
            })
            
            if not product_url:
                product_url = f"{PDP}/{h}"
    
    # 2) Try PDP scrape if not enough
    if len(images) < max_images:
        for h in handles:
            purl, gallery = from_pdp(h)
            if not purl:
                continue
            
            if not product_url:
                product_url = purl
            
            for url in gallery:
                if url in tried_urls or len(images) >= max_images:
                    continue
                tried_urls.add(url)
                
                if validate:
                    data = fetch_image(url)
                    if not data:
                        continue
                
                images.append({
                    "url": url,
                    "index": len(images) + 1,
                    "filename": f"{sku}-{len(images) + 1}"
                })
    
    if images:
        result["brand_code"] = handles[0]
        result["product_url"] = product_url
        result["images"] = images
        result["count"] = len(images)
    else:
        result["error"] = "No images found"
    
    return result
