# -*- coding: utf-8 -*-
"""
SCOTCH & SODA Scraper Module
Za korišćenje sa Flask API
CDN sa PNG slikama
"""

import re
import hashlib
import requests
from io import BytesIO

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

TIMEOUT = 25
MIN_SIZE = 12000

BASE_CDN = "https://scotch-soda.eu/cdn/shop/files"
IMG_PARAM = "?width=1800"

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125",
    "Referer": "https://scotch-soda.eu/",
})


def convert_sku(code):
    """
    SS181118-401 → ('181118_401', '181118')
    SSU9B00856T-U139 → ('U9B00856T_U139', 'U9B00856T')
    """
    code = code.strip()
    if not code.startswith("SS"):
        return "", ""
    rest = code[2:]
    if "-" in rest:
        base, color = rest.rsplit("-", 1)
        their = f"{base}_{color}"
    else:
        their = rest
        base = rest
    return their, base


def candidate_suffixes():
    """All possible suffixes for Scotch & Soda"""
    return [
        "_R_10_FNT_C.png",
        "_R_10_FNT.png",
        "_R_10_DTL.png",
        "_R_10_BCK_C.png",
        "_FNT.png",
        "_BCK_C.png",
        "_BCK.png",
        "_DTL.png",
        "_DTL2.png",
        "_DTL3.png",
        "_1M.png",
        "_2M.png",
        "_3M.png",
        "_4M.png",
        "_5M.png",
    ]


def candidate_urls(their):
    """Generate all candidate URLs"""
    base = f"{BASE_CDN}/Hires_PNG-{their}"
    return [base + suf + IMG_PARAM for suf in candidate_suffixes()]


def normalize_image(data, ctype):
    """Convert WEBP/AVIF to PNG if needed"""
    if not data or len(data) < MIN_SIZE:
        return None
    
    ctype = (ctype or "").lower()
    
    if "png" in ctype or "jpeg" in ctype or "jpg" in ctype:
        return data
    
    if HAS_PIL and ("webp" in ctype or "avif" in ctype):
        try:
            im = Image.open(BytesIO(data)).convert("RGBA")
            bio = BytesIO()
            im.save(bio, format="PNG")
            return bio.getvalue()
        except:
            return None
    
    return data


def fetch_image(url):
    """Download and normalize image"""
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, None
        
        data = normalize_image(r.content, r.headers.get("Content-Type", ""))
        if data:
            return data, hashlib.md5(data).hexdigest()
        return None, None
    except:
        return None, None


def scrape(sku, max_images=5, validate=True):
    """Main scrape function"""
    result = {
        "sku": sku,
        "formatted_sku": sku,
        "brand_code": "",
        "images": [],
        "count": 0,
        "error": None
    }
    
    their, base_part = convert_sku(sku)
    if not their:
        result["error"] = f"Invalid SKU format: {sku}"
        return result
    
    result["brand_code"] = their
    
    images = []
    seen_hashes = set()
    
    for url in candidate_urls(their):
        if len(images) >= max_images:
            break
        
        if validate:
            data, img_hash = fetch_image(url)
            if not data or img_hash in seen_hashes:
                continue
            seen_hashes.add(img_hash)
        
        images.append({
            "url": url,
            "index": len(images) + 1,
            "filename": f"{sku}-{len(images) + 1}"
        })
    
    if images:
        result["images"] = images
        result["count"] = len(images)
    else:
        result["error"] = "No images found"
    
    return result
