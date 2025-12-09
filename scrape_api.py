"""
Fashion Scraper API - v5 FINAL
6 Brands: BOSS, MAJE, MANGO, TOMMY HILFIGER, ALL SAINTS, BOGGI MILANO
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter, Retry
import hashlib
import time
import re
from io import BytesIO

app = Flask(__name__)
CORS(app)

# ===================== HTTP SESSION =====================
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504))
session.mount("https://", HTTPAdapter(max_retries=retries))
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
})

# ===================== CONSTANTS =====================
TIMEOUT = 12
MIN_BYTES = 8000
MIN_BYTES_ALLSAINTS = 20000  # AllSaints needs higher threshold

# ===================== HELPERS =====================

def sha1_hash(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()

def validate_image(url: str, min_bytes=MIN_BYTES, custom_headers=None) -> tuple:
    """Returns (is_valid, content, hash)"""
    try:
        headers = session.headers.copy()
        if custom_headers:
            headers.update(custom_headers)
        r = session.get(url, timeout=TIMEOUT, headers=headers)
        if r.status_code == 200 and r.content and len(r.content) > min_bytes:
            content_type = r.headers.get("Content-Type", "").lower()
            # Some CDNs don't return proper content-type, check size
            if "image" in content_type or len(r.content) > min_bytes:
                return True, r.content, sha1_hash(r.content)
        return False, None, None
    except Exception:
        return False, None, None

def validate_image_pil(url: str, min_bytes=MIN_BYTES, custom_headers=None) -> tuple:
    """Validate with PIL (for AllSaints) - Returns (is_valid, content, hash)"""
    try:
        from PIL import Image
        headers = session.headers.copy()
        if custom_headers:
            headers.update(custom_headers)
        r = session.get(url, timeout=TIMEOUT, headers=headers)
        if r.status_code != 200 or not r.content or len(r.content) < min_bytes:
            return False, None, None
        # Verify with PIL
        try:
            Image.open(BytesIO(r.content)).verify()
        except Exception:
            return False, None, None
        return True, r.content, sha1_hash(r.content)
    except Exception:
        return False, None, None

# ===================== ENDPOINTS =====================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "brands": ["BOSS", "MAJE", "MANGO", "TOMMY", "ALLSAINTS", "BOGGI"]
    })

@app.route('/ping', methods=['GET'])
def ping():
    return "pong"


# ===================== BOSS (UNCHANGED) =====================

@app.route('/scrape-boss', methods=['POST'])
def scrape_boss():
    """Hugo Boss scraper"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        parts = sku.replace("HB", "").strip().split()
        if len(parts) < 2:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        num = parts[0]
        color = parts[-1]
        formatted_sku = f"HB{num} {color}"
        
        PREFIXES = ["hbeu", "hbna"]
        SUFFIX_ORDER = [
            "200", "245", "300", "340", "240", "210", "201", "230", "220", "250", "260", "270", "280",
            "100", "110", "120", "130", "140", "150", "350", "360"
        ]
        IMG_HOST = "https://images.hugoboss.com/is/image/boss"
        
        images = []
        seen_hashes = set()
        
        for pref in PREFIXES:
            if len(images) >= max_images:
                break
            for suf in SUFFIX_ORDER:
                if len(images) >= max_images:
                    break
                code = f"{pref}{num}_{color}"
                url = f"{IMG_HOST}/{code}_{suf}?$large$=&fit=crop,1&align=1,1&wid=1600"
                
                if validate:
                    is_valid, content, img_hash = validate_image(url)
                    if is_valid and img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        images.append({"url": url, "index": len(images) + 1, "suffix": suf, "hash": img_hash[:8]})
                else:
                    images.append({"url": url, "index": len(images) + 1, "suffix": suf})
        
        # Reorder: product shots (100s) last
        model_shots = [img for img in images if not img["suffix"].startswith("1")]
        product_shots = [img for img in images if img["suffix"].startswith("1")]
        images = model_shots + product_shots
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "images": images,
            "count": len(images),
            "validated": validate
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MAJE (UNCHANGED) =====================

@app.route('/scrape-maje', methods=['POST'])
def scrape_maje():
    """Maje scraper"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        base_code = sku.replace("MA", "")
        file_prefix = f"Maje_{base_code}"
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        
        images = []
        seen_hashes = set()
        
        for i in range(1, 5):
            if len(images) >= max_images:
                break
            file_suffix = f"{file_prefix}_F_{i}.jpg"
            url = f"{base_url}images/hi-res/{file_suffix}?sw=1520&sh=2000"
            
            if validate:
                is_valid, content, img_hash = validate_image(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "type": "model", "index": len(images) + 1, "hash": img_hash[:8]})
            else:
                images.append({"url": url, "type": "model", "index": len(images) + 1})
        
        if len(images) < max_images:
            packshot_suffix = f"{file_prefix}_F_P.jpg"
            packshot_url = f"{base_url}images/packshot/{packshot_suffix}?sw=1520&sh=2000"
            if validate:
                is_valid, content, img_hash = validate_image(packshot_url)
                if is_valid and img_hash not in seen_hashes:
                    images.append({"url": packshot_url, "type": "packshot", "index": len(images) + 1, "hash": img_hash[:8]})
            else:
                images.append({"url": packshot_url, "type": "packshot", "index": len(images) + 1})
        
        formatted_sku = sku
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "images": images,
            "count": len(images),
            "validated": validate
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MANGO =====================

@app.route('/scrape-mango', methods=['POST'])
def scrape_mango():
    """
    Mango scraper - EXACT copy of local code logic
    SKU format: MNG27011204-TS or MNG17005812-35
    Uses T2/fotos path (from your latest code)
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse SKU: MNG27011204-TS -> (27011204, TS) -> 27011204_TS
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if not m:
            return jsonify({"error": f"Invalid SKU format: {sku}. Expected: MNG27011204-TS"}), 400
        
        number, color = m.group(1), m.group(2)
        their_code = f"{number}_{color}"
        formatted_sku = sku
        
        # EXACT paths from your code - using T2
        BASE_IMG = "https://shop.mango.com/assets/rcs/pics/static/T2/fotos"
        IMG_PARAM = "?imwidth=2048&imdensity=1"
        
        # Generate candidate URLs in EXACT order from your code
        candidate_urls = []
        
        # 1. Packshot first
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}.jpg{IMG_PARAM}")
        
        # 2. Outfit shots 01-04
        for i in range(1, 5):
            candidate_urls.append(f"{BASE_IMG}/outfit/S/{their_code}-99999999_{i:02}.jpg{IMG_PARAM}")
        
        # 3. R and B variants
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}_R.jpg{IMG_PARAM}")
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}_B.jpg{IMG_PARAM}")
        
        # 4. Detail shots D1-D12
        for d in range(1, 13):
            candidate_urls.append(f"{BASE_IMG}/S/{their_code}_D{d}.jpg{IMG_PARAM}")
        
        images = []
        seen_hashes = set()
        
        custom_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Referer": "https://shop.mango.com/",
            "Connection": "keep-alive"
        }
        
        for url in candidate_urls:
            if len(images) >= max_images:
                break
            
            if validate:
                is_valid, content, img_hash = validate_image(url, min_bytes=9000, custom_headers=custom_headers)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({
                        "url": url,
                        "index": len(images) + 1,
                        "hash": img_hash[:8]
                    })
            else:
                images.append({
                    "url": url,
                    "index": len(images) + 1
                })
        
        # Swap 4th and 5th if we have 5+ images (EXACT same logic as your code)
        if len(images) >= 5:
            images[3], images[4] = images[4], images[3]
        
        # Re-index and set filenames
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "their_code": their_code,
            "images": images,
            "count": len(images),
            "validated": validate
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== TOMMY HILFIGER =====================

@app.route('/scrape-tommy', methods=['POST'])
def scrape_tommy():
    """
    Tommy Hilfiger scraper - EXACT copy of local code logic
    SKU format: AM0AM13659-BDS (or with TH prefix: THAM0AM13659-BDS)
    Output naming: TH{code}-1.jpg
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Remove TH prefix if present for URL generation
        base_code = sku.replace("TH", "")
        formatted_code = base_code.replace("-", "_")
        
        # Output naming uses TH prefix (from your code: HT{code})
        # Your code uses "HT" but I assume you want "TH" for Tommy Hilfiger
        if sku.startswith("TH"):
            formatted_sku = sku
        else:
            formatted_sku = f"TH{sku}"
        
        # EXACT URL pattern from your code
        base_url = "https://tommy-europe.scene7.com/is/image/TommyEurope"
        params = "?wid=781&fmt=jpeg&qlt=95%2C1&op_sharpen=0&resMode=sharp2&op_usm=1.5%2C.5%2C0%2C0&iccEmbed=0&printRes=72"
        
        # URL suffixes in order
        url_suffixes = ["main", "alternate1", "alternate2", "alternate3", "alternate4"]
        
        images = []
        seen_hashes = set()
        
        for suffix in url_suffixes:
            if len(images) >= max_images:
                break
            
            url = f"{base_url}/{formatted_code}_{suffix}{params}"
            
            if validate:
                is_valid, content, img_hash = validate_image(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({
                        "url": url,
                        "type": suffix,
                        "index": len(images) + 1,
                        "hash": img_hash[:8]
                    })
            else:
                images.append({
                    "url": url,
                    "type": suffix,
                    "index": len(images) + 1
                })
        
        # Set filenames
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "formatted_code": formatted_code,
            "images": images,
            "count": len(images),
            "validated": validate
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ALL SAINTS =====================

@app.route('/scrape-allsaints', methods=['POST'])
def scrape_allsaints():
    """
    All Saints scraper - EXACT copy of local code logic
    SKU format: ASM002PC-162 or ASW006DC DUSTY BLUE
    Uses PIL validation, MIN_BYTES=20000
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Convert our SKU to their format - EXACT logic from your code
        # ASM002PC-162 -> M002PC-162
        # ASW006DC DUSTY BLUE -> W006DC-DUSTY-BLUE
        if sku.startswith("ASM") or sku.startswith("ASW"):
            their_code = sku[2:]  # Remove 'AS'
        else:
            their_code = sku
        their_code = re.sub(r"\s+", "-", their_code.strip())
        
        formatted_sku = sku  # Keep original for naming
        
        def allsaints_url(code: str, position: int, variant: int) -> str:
            """EXACT URL function from your code"""
            filter1 = ("fn_select:jq:first%28.%5B%5D%7Cif%20has%28%22metadata%22%29%20then%20"
                       "select%28any%28.metadata%5B%5D%3B%20.external_id%20%3D%3D%20"
                       "%22sfcc-gallery-position%22%20and%20.value%20%3D%3D%20"
                       f"{position}%29%29%20else%20empty%20end%29")
            filter2 = ("fn_select:jq:first%28.%5B%5D%7Cif%20has%28%22metadata%22%29%20then%20"
                       "select%28any%28.metadata%5B%5D%3B%20.external_id%20%3D%3D%20"
                       "%22sfcc_pdp_gallery_position_prod%22%20and%20.value%20%3D%3D%20"
                       f"{position}%29%29%20else%20empty%20end%29")
            filt = filter1 if variant == 1 else filter2
            return (f"https://media.i.allsaints.com/image/list/{filt}/"
                    f"f_auto,q_auto,dpr_auto,w_1674,h_2092,c_fit/"
                    f"{code}.json?_i=AG")
        
        images = []
        seen_hashes = set()
        
        custom_headers = {
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.allsaints.com/"
        }
        
        # EXACT logic: try positions 1-10, max 5 images
        for pos in range(1, 11):
            if len(images) >= max_images:
                break
            
            # Try both variants for each position
            for variant in (1, 2):
                if len(images) >= max_images:
                    break
                    
                url = allsaints_url(their_code, pos, variant)
                
                if validate:
                    # Use PIL validation with higher MIN_BYTES (20000)
                    is_valid, content, img_hash = validate_image_pil(url, min_bytes=MIN_BYTES_ALLSAINTS, custom_headers=custom_headers)
                    if is_valid and img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        images.append({
                            "url": url,
                            "position": pos,
                            "variant": variant,
                            "index": len(images) + 1,
                            "hash": img_hash[:8]
                        })
                        break  # Found for this position, move to next
                else:
                    images.append({
                        "url": url,
                        "position": pos,
                        "variant": variant,
                        "index": len(images) + 1
                    })
                    break
        
        # Set filenames
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "their_code": their_code,
            "images": images,
            "count": len(images),
            "validated": validate
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== BOGGI MILANO =====================

@app.route('/scrape-boggi', methods=['POST'])
def scrape_boggi():
    """
    Boggi Milano scraper - EXACT copy of local code logic
    SKU format: BO25A014901-NAVY
    Sequential download - breaks if image not found
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse SKU: BO25A014901-NAVY -> osnovna=BO25A014901, boja=NAVY
        if "-" not in sku:
            return jsonify({"error": f"Invalid SKU format: {sku}. Expected: BO25A014901-NAVY"}), 400
        
        parts = sku.rsplit("-", 1)
        osnovna = parts[0]
        boja = parts[1] if len(parts) > 1 else ""
        
        formatted_sku = sku
        
        # EXACT base URL from your code
        BASE = "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/Sites-BoggiCatalog/default/images/hi-res/"
        
        images = []
        seen_hashes = set()
        
        # EXACT logic: sequential download, break if not found
        for i in range(max_images):
            if i == 0:
                file_part = f"{osnovna}.jpeg"
            else:
                file_part = f"{osnovna}_{i}.jpeg"
            
            url = BASE + file_part
            
            if validate:
                # Your code uses 20000 min bytes
                is_valid, content, img_hash = validate_image(url, min_bytes=20000)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({
                        "url": url,
                        "index": len(images) + 1,
                        "hash": img_hash[:8]
                    })
                else:
                    # EXACT logic: break if image not found
                    break
            else:
                images.append({
                    "url": url,
                    "index": len(images) + 1
                })
        
        # Set filenames
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "osnovna": osnovna,
            "boja": boja,
            "images": images,
            "count": len(images),
            "validated": validate
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== GENERIC ENDPOINT =====================

@app.route('/scrape', methods=['POST'])
def scrape_generic():
    """Generic endpoint - routes to correct scraper based on brand"""
    data = request.json
    brand = data.get('brand', '').upper().strip()
    
    routes = {
        'BOSS': scrape_boss,
        'HUGO BOSS': scrape_boss,
        'MAJE': scrape_maje,
        'MANGO': scrape_mango,
        'TOMMY': scrape_tommy,
        'TOMMY HILFIGER': scrape_tommy,
        'ALLSAINTS': scrape_allsaints,
        'ALL SAINTS': scrape_allsaints,
        'BOGGI': scrape_boggi,
        'BOGGI MILANO': scrape_boggi
    }
    
    if brand in routes:
        return routes[brand]()
    return jsonify({
        "error": f"Unknown brand: {brand}",
        "supported": ["BOSS", "MAJE", "MANGO", "TOMMY HILFIGER", "ALL SAINTS", "BOGGI MILANO"]
    }), 400


# ===================== DEBUG =====================

@app.route('/debug-sku', methods=['POST'])
def debug_sku():
    """Debug endpoint to see how SKU is parsed for each brand"""
    data = request.json
    sku = data.get('sku', '')
    brand = data.get('brand', '').upper().strip()
    
    result = {"original_sku": sku, "brand": brand}
    
    if brand in ('BOSS', 'HUGO BOSS'):
        parts = sku.replace("HB", "").strip().split()
        num = parts[0] if parts else None
        color = parts[-1] if len(parts) >= 2 else None
        result["formatted_sku"] = f"HB{num} {color}" if num and color else None
        result["filename_example"] = f"HB{num} {color}-1.jpg" if num and color else None
        
    elif brand == 'MAJE':
        base_code = sku.replace("MA", "")
        result["formatted_sku"] = sku
        result["file_prefix"] = f"Maje_{base_code}"
        result["filename_example"] = f"{sku}-1.jpg"
        
    elif brand == 'MANGO':
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if m:
            result["formatted_sku"] = sku
            result["their_code"] = f"{m.group(1)}_{m.group(2)}"
            result["filename_example"] = f"{sku}-1.jpg"
            
    elif brand in ('TOMMY', 'TOMMY HILFIGER'):
        base_code = sku.replace("TH", "")
        formatted_code = base_code.replace("-", "_")
        formatted_sku = f"TH{base_code}" if not sku.startswith("TH") else sku
        result["formatted_sku"] = formatted_sku
        result["formatted_code"] = formatted_code
        result["filename_example"] = f"{formatted_sku}-1.jpg"
        
    elif brand in ('ALLSAINTS', 'ALL SAINTS'):
        if sku.startswith("AS"):
            their_code = sku[2:]
        else:
            their_code = sku
        their_code = re.sub(r"\s+", "-", their_code.strip())
        result["formatted_sku"] = sku
        result["their_code"] = their_code
        result["filename_example"] = f"{sku}-1.jpg"
        
    elif brand in ('BOGGI', 'BOGGI MILANO'):
        parts = sku.rsplit("-", 1)
        result["formatted_sku"] = sku
        result["osnovna"] = parts[0]
        result["boja"] = parts[1] if len(parts) > 1 else ""
        result["filename_example"] = f"{sku}-1.jpg"
    
    return jsonify(result)


# ===================== MAIN =====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
