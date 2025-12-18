"""
Fashion Scraper API - FINAL with VALIDATION
Based on working v3 code + all brands from user's Python scripts
Returns ONLY validated images (images that actually exist)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter, Retry
import hashlib
import time
import re

# Import scraper modula
from scrapers import dsquared2

app = Flask(__name__)
CORS(app)

# ===================== HTTP SESSION =====================
def make_session(headers=None):
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    }
    if headers:
        default_headers.update(headers)
    s.headers.update(default_headers)
    return s

# Default session
session = make_session()

# ===================== CONSTANTS =====================
TIMEOUT = 10
MIN_BYTES = 8000

# ===================== HELPERS =====================
def sha1_hash(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()

def validate_image(url: str, custom_session=None, min_bytes=MIN_BYTES) -> tuple:
    """Check if URL returns valid image. Returns (is_valid, content, hash)"""
    s = custom_session or session
    try:
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and r.content and len(r.content) > min_bytes:
            content_type = r.headers.get("Content-Type", "").lower()
            if "image" in content_type or len(r.content) > 20000:
                return True, r.content, sha1_hash(r.content)
        return False, None, None
    except Exception:
        return False, None, None

# ===================== ENDPOINTS =====================
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "version": "final-validated"})

@app.route('/ping', methods=['GET'])
def ping():
    return "pong"


# ===================== BOSS (from v3 - working) =====================
@app.route('/scrape-boss', methods=['POST'])
def scrape_boss():
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        parts = sku.replace("HB", "").strip().split()
        if len(parts) < 2:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        num, color = parts[0], parts[-1]
        formatted_sku = f"HB{num} {color}"
        
        PREFIXES = ["hbeu", "hbna"]
        SUFFIX_ORDER = ["200", "245", "300", "340", "240", "210", "201", "230", "220", "250", "260", "270", "280",
                        "100", "110", "120", "130", "140", "150", "350", "360"]
        IMG_HOST = "https://images.hugoboss.com/is/image/boss"
        
        images = []
        seen_hashes = set()
        
        for pref in PREFIXES:
            if len(images) >= max_images:
                break
            for suf in SUFFIX_ORDER:
                if len(images) >= max_images:
                    break
                
                url = f"{IMG_HOST}/{pref}{num}_{color}_{suf}?$large$=&fit=crop,1&align=1,1&wid=1600"
                is_valid, content, img_hash = validate_image(url)
                
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "index": len(images)+1, "suffix": suf})
        
        # Reorder: model shots first, product shots (100s) last
        model_shots = [img for img in images if not img["suffix"].startswith("1")]
        product_shots = [img for img in images if img["suffix"].startswith("1")]
        images = (model_shots + product_shots)[:max_images]
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "formatted_sku": formatted_sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MAJE (from v3 - working) =====================
@app.route('/scrape-maje', methods=['POST'])
def scrape_maje():
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        base_code = sku.replace("MA", "")
        file_prefix = f"Maje_{base_code}"
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        
        images = []
        seen_hashes = set()
        
        # Model shots 1-4
        for i in range(1, 5):
            if len(images) >= max_images:
                break
            url = f"{base_url}images/hi-res/{file_prefix}_F_{i}.jpg?sw=1520&sh=2000"
            is_valid, content, img_hash = validate_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "type": "model", "index": len(images)+1, "filename": f"{sku}-{len(images)+1}"})
        
        # Packshot
        if len(images) < max_images:
            url = f"{base_url}images/packshot/{file_prefix}_F_P.jpg?sw=1520&sh=2000"
            is_valid, content, img_hash = validate_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "type": "packshot", "index": len(images)+1, "filename": f"{sku}-{len(images)+1}"})
        
        return jsonify({"sku": sku, "formatted_sku": sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MANGO (from mango.py) =====================
@app.route('/scrape-mango', methods=['POST'])
def scrape_mango():
    """
    MANGO - NO VALIDATION
    Returns 10+ candidate URLs in priority order (same as local Python)
    n8n downloads all, filters valid, takes first 5, renumbers to -1,-2,-3,-4,-5
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 10)  # Return MORE so n8n can filter
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if not m:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        number, color = m.group(1), m.group(2)
        their_code = f"{number}_{color}"
        
        BASE_IMG = "https://shop.mango.com/assets/rcs/pics/static/T2/fotos"
        IMG_PARAM = "?imwidth=2048&imdensity=1"
        
        # EXACT order from your mango.py candidate_image_urls()
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
        
        # Return up to max_images URLs - n8n will filter non-existent
        images = []
        for i, url in enumerate(candidate_urls[:max_images]):
            images.append({
                "url": url,
                "index": i + 1,
                "filename": f"{sku}-{i + 1}"  # Temporary, n8n will renumber after filtering
            })
        
        return jsonify({
            "sku": sku, 
            "formatted_sku": sku, 
            "their_code": their_code, 
            "images": images, 
            "count": len(images),
            "note": "No validation - n8n filters and renumbers"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== TOMMY HILFIGER (from tommy.py) =====================
@app.route('/scrape-tommy', methods=['POST'])
def scrape_tommy():
    """EXACT logic from user's tommy.py"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # From tommy.py: base_code = code.replace("TH", "")
        base_code = sku.replace("TH", "")
        formatted_code = base_code.replace("-", "_")
        formatted_sku = f"TH{base_code}"
        
        # EXACT URL from tommy.py
        base_url = "https://tommy-europe.scene7.com/is/image/TommyEurope"
        params = "?wid=781&fmt=jpeg&qlt=95%2C1&op_sharpen=0&resMode=sharp2&op_usm=1.5%2C.5%2C0%2C0&iccEmbed=0&printRes=72"
        
        suffixes = ["main", "alternate1", "alternate2", "alternate3", "alternate4"]
        
        images = []
        seen_hashes = set()
        
        for suffix in suffixes:
            if len(images) >= max_images:
                break
            url = f"{base_url}/{formatted_code}_{suffix}{params}"
            is_valid, content, img_hash = validate_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images)+1, "filename": f"{formatted_sku}-{len(images)+1}"})
        
        return jsonify({"sku": sku, "formatted_sku": formatted_sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ALL SAINTS (from allsaints.py) =====================
@app.route('/scrape-allsaints', methods=['POST'])
def scrape_allsaints():
    """EXACT logic from user's allsaints.py"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # EXACT from allsaints.py moja_u_njihova()
        if sku.startswith("ASM") or sku.startswith("ASW"):
            their_code = sku[2:]
        else:
            their_code = sku
        their_code = re.sub(r"\s+", "-", their_code.strip())
        
        # Session with proper headers from allsaints.py
        as_session = make_session({
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.allsaints.com/"
        })
        
        MIN_AS = 20000  # from allsaints.py
        
        # EXACT URL function from allsaints.py
        def make_url(code, pos, variant):
            if variant == 1:
                filt = ("fn_select:jq:first%28.%5B%5D%7Cif%20has%28%22metadata%22%29%20then%20"
                        "select%28any%28.metadata%5B%5D%3B%20.external_id%20%3D%3D%20"
                        f"%22sfcc-gallery-position%22%20and%20.value%20%3D%3D%20{pos}%29%29%20else%20empty%20end%29")
            else:
                filt = ("fn_select:jq:first%28.%5B%5D%7Cif%20has%28%22metadata%22%29%20then%20"
                        "select%28any%28.metadata%5B%5D%3B%20.external_id%20%3D%3D%20"
                        f"%22sfcc_pdp_gallery_position_prod%22%20and%20.value%20%3D%3D%20{pos}%29%29%20else%20empty%20end%29")
            return f"https://media.i.allsaints.com/image/list/{filt}/f_auto,q_auto,dpr_auto,w_1674,h_2092,c_fit/{code}.json?_i=AG"
        
        images = []
        seen_hashes = set()
        
        # EXACT logic from allsaints.py: try positions 1-10, variant 1 first then 2
        for pos in range(1, 11):
            if len(images) >= max_images:
                break
            
            for variant in (1, 2):
                url = make_url(their_code, pos, variant)
                is_valid, content, img_hash = validate_image(url, as_session, MIN_AS)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "position": pos, "index": len(images)+1, "filename": f"{sku}-{len(images)+1}"})
                    break  # Got image for this position, move to next
        
        return jsonify({"sku": sku, "formatted_sku": sku, "their_code": their_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ===================== BOGGI MILANO =====================
@app.route('/scrape-boggi', methods=['POST'])
def scrape_boggi():
    """Boggi Milano scraper"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku or "-" not in sku:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        osnovna, boja = sku.rsplit("-", 1)
        
        BASE = "https://www.boggi.com/on/demandware.static/-/Sites-BoggiCatalog/default/images/hi-res/"
        MIN_BOGGI = 20000
        
        images = []
        seen_hashes = set()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.boggi.com/"
        }
        
        for i in range(max_images):
            if i == 0:
                file_part = f"{osnovna}.jpeg"
            else:
                file_part = f"{osnovna}_{i}.jpeg"
            
            url = BASE + file_part
            
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200 and len(resp.content) > MIN_BOGGI:
                    img_hash = hashlib.md5(resp.content).hexdigest()
                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        images.append({
                            "url": url,
                            "index": len(images)+1,
                            "filename": f"{sku}-{len(images)+1}"
                        })
                else:
                    break
            except:
                break
        
        return jsonify({"sku": sku, "formatted_sku": sku, "images": images, "count": len(images)})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== DSQUARED2 =====================
@app.route('/scrape-dsquared2', methods=['POST'])
def scrape_dsquared2_endpoint():
    """DSQUARED2 - koristi search-based pristup sa filterom po boji"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', False)
        
        if not sku:
            return jsonify({"error": "SKU required", "sku": sku, "images": []}), 400
        
        result = dsquared2.scrape(sku, max_images, validate)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e), "sku": "", "images": []}), 500


# ===================== GENERIC =====================
@app.route('/scrape', methods=['POST'])
def scrape_generic():
    brand = request.json.get('brand', '').upper().strip()
    routes = {
        'BOSS': scrape_boss, 'HUGO BOSS': scrape_boss,
        'MAJE': scrape_maje,
        'MANGO': scrape_mango,
        'TOMMY': scrape_tommy, 'TOMMY HILFIGER': scrape_tommy,
        'ALLSAINTS': scrape_allsaints, 'ALL SAINTS': scrape_allsaints,
        'BOGGI': scrape_boggi, 'BOGGI MILANO': scrape_boggi,
        'DSQUARED2': scrape_dsquared2_endpoint, 'DSQ': scrape_dsquared2_endpoint
    }
    if brand in routes:
        return routes[brand]()
    return jsonify({"error": f"Unknown brand: {brand}"}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
