"""
Fashion Scraper API - FINAL MERGED
Existing brands (unchanged) + All new brands
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
    return jsonify({"status": "ok", "version": "final-merged"})

@app.route('/ping', methods=['GET'])
def ping():
    return "pong"


# ===================== BOSS / HUGO (UPDATED - isti scraper) =====================
@app.route('/scrape-boss', methods=['POST'])
@app.route('/scrape-hugo', methods=['POST'])
def scrape_boss():
    """BOSS / HUGO - isti scraper, 21 pozicija × 2 prefiksa"""
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


# ===================== MAJE (EXISTING - unchanged) =====================
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


# ===================== MANGO (EXISTING - unchanged) =====================
@app.route('/scrape-mango', methods=['POST'])
def scrape_mango():
    """MANGO - NO VALIDATION"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 10)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if not m:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        number, color = m.group(1), m.group(2)
        their_code = f"{number}_{color}"
        
        BASE_IMG = "https://shop.mango.com/assets/rcs/pics/static/T2/fotos"
        IMG_PARAM = "?imwidth=2048&imdensity=1"
        
        candidate_urls = []
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}.jpg{IMG_PARAM}")
        for i in range(1, 5):
            candidate_urls.append(f"{BASE_IMG}/outfit/S/{their_code}-99999999_{i:02}.jpg{IMG_PARAM}")
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}_R.jpg{IMG_PARAM}")
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}_B.jpg{IMG_PARAM}")
        for d in range(1, 13):
            candidate_urls.append(f"{BASE_IMG}/S/{their_code}_D{d}.jpg{IMG_PARAM}")
        
        images = []
        for i, url in enumerate(candidate_urls[:max_images]):
            images.append({"url": url, "index": i + 1, "filename": f"{sku}-{i + 1}"})
        
        return jsonify({"sku": sku, "formatted_sku": sku, "their_code": their_code, "images": images, "count": len(images), "note": "No validation - n8n filters and renumbers"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== TOMMY HILFIGER (EXISTING - unchanged) =====================
@app.route('/scrape-tommy', methods=['POST'])
def scrape_tommy():
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        base_code = sku.replace("TH", "")
        formatted_code = base_code.replace("-", "_")
        formatted_sku = f"TH{base_code}"
        
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


# ===================== ALL SAINTS (EXISTING - unchanged) =====================
@app.route('/scrape-allsaints', methods=['POST'])
def scrape_allsaints():
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        if sku.startswith("ASM") or sku.startswith("ASW"):
            their_code = sku[2:]
        else:
            their_code = sku
        their_code = re.sub(r"\s+", "-", their_code.strip())
        
        as_session = make_session({
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.allsaints.com/"
        })
        
        MIN_AS = 20000
        
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
        
        for pos in range(1, 11):
            if len(images) >= max_images:
                break
            for variant in (1, 2):
                url = make_url(their_code, pos, variant)
                is_valid, content, img_hash = validate_image(url, as_session, MIN_AS)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "position": pos, "index": len(images)+1, "filename": f"{sku}-{len(images)+1}"})
                    break
        
        return jsonify({"sku": sku, "formatted_sku": sku, "their_code": their_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== BOGGI MILANO (EXISTING - unchanged) =====================
@app.route('/scrape-boggi', methods=['POST'])
def scrape_boggi():
    try:
        data = request.json
        sku = data.get("sku", "").strip()
        max_images = data.get("max_images", 5)

        if not sku:
            return jsonify({"error": "SKU required"}), 400

        if "-" not in sku:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400

        model_code, color_code = sku.split("-", 1)

        BASE_IMG = (
            "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/"
            "www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/"
            "Sites-BoggiCatalog/default/images/hi-res/"
        )

        images = []

        for i in range(0, max_images):
            if i == 0:
                file_part = f"{model_code}.jpeg"
            else:
                file_part = f"{model_code}_{i}.jpeg"
            url = BASE_IMG + file_part
            images.append({"url": url, "index": i + 1, "filename": f"{sku}-{i + 1}"})

        return jsonify({"sku": sku, "formatted_sku": sku, "model_code": model_code, "color_code": color_code, "landing_page": "empty", "images": images, "count": len(images), "note": "No validation – n8n filters invalid images"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== DSQUARED2 (EXISTING - unchanged) =====================
@app.route('/scrape-dsquared2', methods=['POST'])
def scrape_dsquared2_endpoint():
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


# =====================================================================
# NEW BRANDS - ADDED
# =====================================================================

# ===================== CALVIN KLEIN =====================
@app.route('/scrape-calvin-klein', methods=['POST'])
def scrape_calvin_klein():
    """CALVIN KLEIN - 5 pozicija: main + alternate1-4"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        base_code = sku.replace("CK", "")
        formatted_code = base_code.replace("-", "_")
        
        BASE = "https://calvinklein-eu.scene7.com/is/image/CalvinKleinEU/"
        SUFFIXES = ["main", "alternate1", "alternate2", "alternate3", "alternate4"]
        
        images = []
        seen_hashes = set()
        
        for suffix in SUFFIXES:
            if len(images) >= max_images:
                break
            url = f"{BASE}{formatted_code}_{suffix}?wid=1600&fmt=jpeg&qlt=95"
            is_valid, content, img_hash = validate_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": formatted_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== COACH (PARALLEL - LARGE IMAGES) =====================
@app.route('/scrape-coach', methods=['POST'])
def scrape_coach_endpoint():
    try:
        from scrapers.scrape_coach import scrape_coach
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        result = scrape_coach(sku, max_images)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== DIESEL =====================
from scrapers import diesel

@app.route('/scrape-diesel', methods=['POST'])
def scrape_diesel():
    """DIESEL - uses scrapers/diesel.py module"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        result = diesel.scrape(sku, max_images=max_images)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== KURT GEIGER =====================
@app.route('/scrape-kurt-geiger', methods=['POST'])
def scrape_kurt_geiger():
    """KURT GEIGER - 9 frames"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        nums = re.findall(r"\d+", sku)
        if not nums:
            return jsonify({"error": f"Cannot extract product ID from: {sku}"}), 400
        
        prod_id = max(nums, key=len)
        
        FRAMES = [20, 25, 21, 22, 23, 24, 26, 27, 28]
        
        images = []
        seen_hashes = set()
        
        for frame in FRAMES:
            if len(images) >= max_images:
                break
            url = f"https://media.global.kurtgeiger.com/product/{prod_id}/{frame}/{prod_id}?w=1920"
            is_valid, content, img_hash = validate_image(url, min_bytes=4000)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": prod_id, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== KATE SPADE =====================
@app.route('/scrape-kate-spade', methods=['POST'])
def scrape_kate_spade():
    """KATE SPADE - multi-color support"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        core = sku[2:] if sku.upper().startswith("KS") else sku
        if "-" in core:
            model, my_color = core.split("-", 1)
        else:
            model, my_color = core, ""
        
        COLOR_MAP = {
            "500": ["020", "500", "000"],
            "001": ["001", "000", "020"],
            "200": ["200", "020", "000"],
        }
        FALLBACK_COLORS = ["020", "001", "000", "200", "500"]
        
        color_candidates = COLOR_MAP.get(my_color, []) + [c for c in FALLBACK_COLORS if c not in COLOR_MAP.get(my_color, [])]
        
        BASE = "https://katespade.scene7.com/is/image/KateSpade"
        SUFFIXES = ["", "_1", "_2", "_3", "_4"]
        
        images = []
        seen_hashes = set()
        working_color = None
        
        for clr in color_candidates:
            url = f"{BASE}/{model}_{clr}?$desktopProductZoom$"
            is_valid, content, img_hash = validate_image(url, min_bytes=15000)
            if is_valid:
                working_color = clr
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": 1, "filename": f"{sku}-1"})
                break
        
        if not working_color:
            return jsonify({"sku": sku, "brand_code": model, "images": [], "count": 0, "error": "No images found"})
        
        for suffix in SUFFIXES[1:]:
            if len(images) >= max_images:
                break
            url = f"{BASE}/{model}_{working_color}{suffix}?$desktopProductZoom$"
            is_valid, content, img_hash = validate_image(url, min_bytes=15000)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": f"{model}_{working_color}", "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== PAUL TAYLOR =====================
@app.route('/scrape-paul-taylor', methods=['POST'])
def scrape_paul_taylor():
    """PAUL TAYLOR - 2 sezone × 10 brojeva"""
    try:
        data = request.json
        sku = data.get('sku', '').strip().upper()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        their_base = None
        
        m = re.match(r"^PT7([A-Z]{2})([A-Z])(\d{3})-(\d{3})$", sku)
        if m:
            two, last, num, color = m.groups()
            their_base = f"PT7{two}_{last}{num}_{color}"
        
        if not their_base:
            m = re.match(r"^PT7(\d{2})(\d{4})-(\d{3})$", sku)
            if m:
                two, four, color = m.groups()
                their_base = f"PT7{two}_{four}_{color}"
        
        if not their_base:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        BASE = "https://paultaylor.it/cdn/shop/files"
        SEASONS = ["W25", "W24"]
        NUMS = ["1", "2", "3", "4", "5", "01", "02", "03", "04", "05"]
        
        images = []
        seen_hashes = set()
        
        for season in SEASONS:
            if len(images) >= max_images:
                break
            for n in NUMS:
                if len(images) >= max_images:
                    break
                url = f"{BASE}/{their_base}_{season}_{n}.jpg"
                is_valid, content, img_hash = validate_image(url, min_bytes=12000)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": their_base, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MOOSE KNUCKLES =====================
@app.route('/scrape-moose-knuckles', methods=['POST'])
def scrape_moose_knuckles():
    """MOOSE KNUCKLES - 17 sufiksa"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        site_code = sku.lower().replace("-", "_")
        
        BASE = "https://www.mooseknucklescanada.com/cdn/shop/files"
        SUFFIX_ORDER = [
            "front", "front_category", "front_flat",
            "back", "side", "left", "right",
            "detail1", "detail_1", "detail2", "detail_2", "detail3",
            "onmodel1", "onmodel2", "look1", "look2", "gm"
        ]
        
        images = []
        seen_hashes = set()
        
        for suf in SUFFIX_ORDER:
            if len(images) >= max_images:
                break
            url = f"{BASE}/{site_code}_{suf}.jpg"
            is_valid, content, img_hash = validate_image(url, min_bytes=20000)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": site_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== SCOTCH & SODA =====================
@app.route('/scrape-scotch-soda', methods=['POST'])
def scrape_scotch_soda():
    """SCOTCH & SODA - 18+ sufiksa"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        if not sku.startswith("SS"):
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        rest = sku[2:]
        if "-" in rest:
            base, color = rest.rsplit("-", 1)
            their = f"{base}_{color}"
        else:
            their = rest
        
        BASE_CDN = "https://scotch-soda.eu/cdn/shop/files"
        SUFFIXES = [
            "_R_10_FNT_C.png", "_R_10_FNT.png", "_R_10_DTL.png", "_R_10_BCK_C.png",
            "_FNT.png", "_BCK_C.png", "_BCK.png", "_DTL.png",
            "_DTL2.png", "-DTL2.png", "_DTL3.png", "-DTL3.png",
            "_1M.png", "_1M-P.png", "_2M.png", "_3M.png", "_4M.png", "_5M.png", "_6M.png",
        ]
        
        images = []
        seen_hashes = set()
        
        for suf in SUFFIXES:
            if len(images) >= max_images:
                break
            url = f"{BASE_CDN}/Hires_PNG-{their}{suf}?width=1800"
            is_valid, content, img_hash = validate_image(url, min_bytes=12000)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": their, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ETRO =====================
@app.route('/scrape-etro', methods=['POST'])
def scrape_etro():
    """ETRO - 5 sufiksa: SF, SB, ST, SS, D"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        clean = sku[1:] if sku.startswith('E') else sku
        parts = clean.split()
        if len(parts) != 3:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        etro_code = f"{parts[0]}A{parts[1]}{parts[2]}"
        
        SUFFIXES = ["SF", "SB", "ST", "SS", "D"]
        
        images = []
        seen_hashes = set()
        
        for suffix in SUFFIXES:
            if len(images) >= max_images:
                break
            url = f"https://content.etro.com/Adaptations/900/{etro_code}_{suffix}_01.jpg"
            is_valid, content, img_hash = validate_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku.replace(' ', '_')}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": etro_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== GUESS =====================
@app.route('/scrape-guess', methods=['POST'])
def scrape_guess():
    """GUESS - 6 sufiksa"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        parts = sku.split()
        if len(parts) != 3:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        part1 = parts[0][1:] if parts[0].startswith('G') else parts[0]
        guess_code = f"{part1}{parts[1]}-{parts[2]}"
        
        BASE = "https://img.guess.com/image/upload/f_auto,q_auto,fl_strip_profile,e_sharpen:50,w_1920,c_scale/v1/EU/Style/ECOMM/"
        SUFFIXES = ["", "-ALT1", "-ALT2", "-ALT3", "-ALT4", "-ALTGHOST"]
        
        images = []
        seen_hashes = set()
        
        for suffix in SUFFIXES:
            if len(images) >= max_images:
                break
            url = f"{BASE}{guess_code}{suffix}"
            is_valid, content, img_hash = validate_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku.replace(' ', '_')}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": guess_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== EMPORIO ARMANI =====================
@app.route('/scrape-emporio-armani', methods=['POST'])
def scrape_emporio_armani():
    """EMPORIO ARMANI - 4 sezone × 3 sufiksa"""
    try:
        data = request.json
        sku = data.get('sku', '').strip().replace(" ", "")
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        if not sku.startswith(("EAEM", "EAEW")):
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        code = sku[2:]
        if len(code) < 16:
            return jsonify({"error": f"SKU too short: {sku}"}), 400
        
        brand = code[:2]
        model = code[2:8]
        fabric = code[8:13]
        color = code[13:]
        armani_code = f"{brand}{model}_AF{fabric}_{color}"
        
        SEASONS = ['FW2025', 'SS2025', 'FW2024', 'SS2024']
        SUFFIXES = ['F', 'D', 'R']
        
        images = []
        seen_hashes = set()
        
        for season in SEASONS:
            if len(images) >= max_images:
                break
            for suf in SUFFIXES:
                if len(images) >= max_images:
                    break
                url = f"https://assets-cf.armani.com/image/upload/f_auto,q_auto:best,ar_4:5,w_1350,c_fill/{armani_code}_{suf}_{season}.jpg"
                is_valid, content, img_hash = validate_image(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": armani_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ARMANI EXCHANGE =====================
@app.route('/scrape-armani-exchange', methods=['POST'])
def scrape_armani_exchange():
    """ARMANI EXCHANGE - 3 sezone × 5 sufiksa"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        base = sku.replace("AR", "")
        parts = base.split("-")
        if len(parts) != 3:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        ax_code = f"XM{parts[0]}_AF{parts[1]}_{parts[2]}"
        
        SEASONS = ['FW2025', 'SS2025', 'FW2024']
        SUFFIXES = ["F", "D", "R", "E", "A"]
        
        images = []
        seen_hashes = set()
        
        for season in SEASONS:
            if len(images) >= max_images:
                break
            for suf in SUFFIXES:
                if len(images) >= max_images:
                    break
                url = f"https://assets.armani.com/image/upload/f_auto,q_auto:best,ar_4:5,w_1350,c_fill/{ax_code}_{suf}_{season}.jpg"
                is_valid, content, img_hash = validate_image(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "index": len(images) + 1, "filename": f"{sku.replace('-', '_')}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": ax_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MICHAEL KORS =====================
@app.route('/scrape-michael-kors', methods=['POST'])
def scrape_michael_kors():
    """MICHAEL KORS - 2 varijante boje × 8 pozicija"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        parts = sku.split('-')
        if len(parts) != 2:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        code_part = parts[0]
        color = parts[1].zfill(4)
        
        if code_part.startswith('MCC'):
            product = code_part[2:]
        elif code_part.startswith('MC'):
            product = code_part[2:]
        else:
            product = code_part
        
        color_variants = [color, color.lstrip('0') or '0']
        
        images = []
        seen_hashes = set()
        
        for clr in color_variants:
            if len(images) >= max_images:
                break
            for i in range(1, 9):
                if len(images) >= max_images:
                    break
                url = f"https://michaelkors.scene7.com/is/image/MichaelKors/{product}-{clr}_{i}?wid=1200&hei=1500&fmt=jpg"
                is_valid, content, img_hash = validate_image(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "index": len(images) + 1, "filename": f"{sku.replace('-', '_')}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": f"{product}-{color}", "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== PATRIZIA PEPE =====================
@app.route('/scrape-patrizia-pepe', methods=['POST'])
def scrape_patrizia_pepe():
    """PATRIZIA PEPE - 5 sezona × 8 pozicija"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        parts = sku.split()
        if len(parts) != 3:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        part1 = parts[0][2:] if parts[0].startswith('PP') else parts[0]
        product_fabric = f"{part1}_{parts[1]}"
        color = parts[2]
        full_code = f"{part1}_{parts[1]}_{parts[2]}"
        
        SEASONS = ["2026-1", "2025-2", "2025-1", "2024-2", "2024-1"]
        
        images = []
        seen_hashes = set()
        
        for season in SEASONS:
            if len(images) >= max_images:
                break
            for i in range(1, 9):
                if len(images) >= max_images:
                    break
                url = f"https://cdn.patriziapepe.com/image/upload/w_1200/q_auto:good/f_auto/CHALCO/SFCC/{product_fabric}/{color}/{season}/{full_code}_{i}.jpg"
                is_valid, content, img_hash = validate_image(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({"url": url, "index": len(images) + 1, "filename": f"{sku.replace(' ', '_')}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": full_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== SANDRO =====================
@app.route('/scrape-sandro', methods=['POST'])
def scrape_sandro():
    """SANDRO - 6 sufiksa (5 + packshot)"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        code = sku[2:] if sku.startswith('SA') else sku
        
        BASE = "https://eu.sandro-paris.com/dw/image/v2/BCMW_PRD/on/demandware.static/-/Sites-master-catalog/default/images/hi-res/"
        SUFFIXES = ["F_1", "F_2", "F_3", "F_4", "F_5"]
        
        images = []
        seen_hashes = set()
        
        for suffix in SUFFIXES:
            if len(images) >= max_images:
                break
            url = f"{BASE}Sandro_{code}_{suffix}.jpg?sw=2000&sh=2000"
            is_valid, content, img_hash = validate_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku.replace('-', '_')}-{len(images) + 1}"})
        
        if len(images) < max_images:
            url = f"https://eu.sandro-paris.com/dw/image/v2/BCMW_PRD/on/demandware.static/-/Sites-master-catalog/default/images/packshot/Sandro_{code}_F_P.jpg?sw=2000&sh=2000"
            is_valid, content, img_hash = validate_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{sku.replace('-', '_')}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ANTONY MORATO =====================
@app.route('/scrape-morato', methods=['POST'])
def scrape_morato():
    """ANTONY MORATO - kompleksna konverzija + 6 pozicija"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        def get_prefix(cat):
            if cat in ['BE', 'FW']: return ['LE', 'FA']
            if cat == 'SW': return ['YA', 'FA']
            return ['FA', 'LE', 'YA']
        
        their_codes = []
        if len(sku) == 20 and sku[2:4] == 'DT':
            cat, mod, fab, wash = sku[2:4], sku[4:9], sku[9:15], sku[15:20]
            colors = ['7010', '9000', '7086', '2102']
            for p in get_prefix(cat):
                for c in colors:
                    their_codes.append(f"MM{cat}{mod} {p}{fab} {c}-1-W{wash}")
        elif len(sku) == 19:
            cat, mod, fab, col = sku[2:4], sku[4:9], sku[9:15], sku[15:19]
            for p in get_prefix(cat):
                their_codes.append(f"MM{cat}{mod} {p}{fab} {col}")
        
        if not their_codes:
            return jsonify({"error": f"Cannot convert SKU: {sku}"}), 400
        
        images = []
        seen_hashes = set()
        working_code = ""
        
        for their in their_codes:
            if len(images) >= max_images:
                break
            fn = re.sub(r"\s+", "-", their.strip()).upper()
            d1, d2 = fn[0], fn[1]
            for i in range(1, 7):
                if len(images) >= max_images:
                    break
                url = f"https://cdn.antonymorato.com.filoblu.com/rx/960x,ofmt_webp/media/catalog/product/{d1}/{d2}/{fn}_0{i}.jpg"
                is_valid, content, img_hash = validate_image(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    if not working_code:
                        working_code = their
                    images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": working_code or their_codes[0], "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== REPLAY =====================
@app.route('/scrape-replay', methods=['POST'])
def scrape_replay():
    """REPLAY - multi-region, filtrira watermark"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        WATERMARK_HASHES = {"b7b532cb2ea2ae3c91decf2bc87b1c01"}
        WATERMARK_SIZE = 26238
        
        def parse_replay_sku(s):
            s = s.strip()
            if s.startswith('R'):
                s = s[1:]
            
            match = re.match(r'^([A-Z0-9]+)\s*\{([^}]+)\}(.+)$', s)
            if match:
                model = match.group(1)
                fabric = match.group(2).replace(' ', '-')
                color = match.group(3)
                return f"{model}_000_{fabric}_{color}", model
            
            match2 = re.match(r'^([A-Z]+\d+[A-Z]?)([A-Z]\d+[A-Z]?\d*)(\d{3,4})$', s)
            if match2:
                model = match2.group(1)
                fabric = match2.group(2)
                color = match2.group(3)
                return f"{model}_000_{fabric}_{color}", model
            
            return None, None
        
        def validate_replay_image(url):
            try:
                r = session.get(url, timeout=12)
                if r.status_code == 200 and len(r.content) >= 8000:
                    ctype = r.headers.get("Content-Type", "").lower()
                    if "image" in ctype:
                        if len(r.content) == WATERMARK_SIZE:
                            return False, None, None
                        img_hash = hashlib.md5(r.content).hexdigest()
                        if img_hash in WATERMARK_HASHES:
                            return False, None, None
                        return True, r.content, img_hash
            except:
                pass
            return False, None, None
        
        cdn_code, model = parse_replay_sku(sku)
        if not cdn_code:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        CDN_BASE = "https://replayjeans.kleecks-cdn.com"
        REGIONS = ["gr", "it", "de", "fr", "es", "eu", "uk"]
        IMG_PARAMS = "?optimize=low&bg-color=255,255,255&fit=bounds&height=1200&width=900&canvas=900:1200"
        
        d1 = cdn_code[0]
        d2 = cdn_code[1]
        
        images = []
        seen_hashes = set()
        working_region = None
        
        for region in REGIONS:
            url = f"{CDN_BASE}/{region}/media/catalog/product/{d1}/{d2}/{cdn_code}_1.jpg{IMG_PARAMS}"
            is_valid, content, img_hash = validate_replay_image(url)
            if is_valid:
                working_region = region
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": 1, "filename": f"{re.sub(r'[{}]', '', sku).replace(' ', '_')}-1"})
                break
        
        if not working_region:
            return jsonify({"sku": sku, "brand_code": cdn_code, "images": [], "count": 0, "error": "No images found"})
        
        for pos in range(2, 11):
            if len(images) >= max_images:
                break
            url = f"{CDN_BASE}/{working_region}/media/catalog/product/{d1}/{d2}/{cdn_code}_{pos}.jpg{IMG_PARAMS}"
            is_valid, content, img_hash = validate_replay_image(url)
            if is_valid and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "index": len(images) + 1, "filename": f"{re.sub(r'[{}]', '', sku).replace(' ', '_')}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "brand_code": cdn_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== JOOP =====================
@app.route('/scrape-joop', methods=['POST'])
def scrape_joop():
    """JOOP - zahteva website scraping"""
    try:
        from scrapers import joop
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        result = joop.scrape(sku, max_images)
        return jsonify(result)
    except ImportError:
        return jsonify({"error": "JOOP scraper module not found. Add scrapers/joop.py"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== STRELLSON =====================
@app.route('/scrape-strellson', methods=['POST'])
def scrape_strellson():
    """STRELLSON - zahteva website scraping"""
    try:
        from scrapers import strellson
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        result = strellson.scrape(sku, max_images)
        return jsonify(result)
    except ImportError:
        return jsonify({"error": "Strellson scraper module not found. Add scrapers/strellson.py"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== WOOLRICH =====================
@app.route('/scrape-woolrich', methods=['POST'])
def scrape_woolrich():
    """WOOLRICH - zahteva website scraping"""
    try:
        from scrapers import woolrich
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        result = woolrich.scrape(sku, max_images)
        return jsonify(result)
    except ImportError:
        return jsonify({"error": "Woolrich scraper module not found. Add scrapers/woolrich.py"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== FALKE =====================
@app.route('/scrape-falke', methods=['POST'])
def scrape_falke():
    """FALKE - zahteva website scraping"""
    try:
        from scrapers import falke
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        result = falke.scrape(sku, max_images)
        return jsonify(result)
    except ImportError:
        return jsonify({"error": "Falke scraper module not found. Add scrapers/falke.py"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ENTERPRISE JAPAN =====================
@app.route('/scrape-enterprise-japan', methods=['POST'])
def scrape_enterprise_japan():
    """ENTERPRISE JAPAN - CDN + PDP scraping"""
    try:
        from scrapers import enterprise_japan
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        result = enterprise_japan.scrape(sku, max_images)
        return jsonify(result)
    except ImportError:
        return jsonify({"error": "Enterprise Japan scraper module not found. Add scrapers/enterprise_japan.py"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===================== LEVI'S (PARALLEL) =====================
@app.route('/scrape-levis', methods=['POST'])
def scrape_levis_endpoint():
    try:
        from scrapers.scrape_levis import scrape_levis
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        result = scrape_levis(sku, max_images)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===================== GOLDEN GOOSE (PARALLEL) =====================
@app.route('/scrape-golden-goose', methods=['POST'])
def scrape_golden_goose_endpoint():
    try:
        from scrapers.scrape_golden_goose import scrape_golden_goose
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        result = scrape_golden_goose(sku, max_images)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== GENERIC ENDPOINT =====================
@app.route('/scrape', methods=['POST'])
def scrape_generic():
    brand = request.json.get('brand', '').upper().strip()
    routes = {
        # EXISTING
        'BOSS': scrape_boss, 'HUGO BOSS': scrape_boss, 'HUGO': scrape_boss,
        'MAJE': scrape_maje,
        'MANGO': scrape_mango,
        'TOMMY': scrape_tommy, 'TOMMY HILFIGER': scrape_tommy,
        'ALLSAINTS': scrape_allsaints, 'ALL SAINTS': scrape_allsaints,
        'BOGGI': scrape_boggi, 'BOGGI MILANO': scrape_boggi,
        'DSQUARED2': scrape_dsquared2_endpoint, 'DSQ': scrape_dsquared2_endpoint,
        
        # NEW CDN BRANDS
        'CALVIN KLEIN': scrape_calvin_klein, 'CK': scrape_calvin_klein,
        'COACH': scrape_coach,
        'DIESEL': scrape_diesel,
        'KURT GEIGER': scrape_kurt_geiger, 'KG': scrape_kurt_geiger,
        'KATE SPADE': scrape_kate_spade, 'KS': scrape_kate_spade,
        'PAUL TAYLOR': scrape_paul_taylor, 'PT': scrape_paul_taylor,
        'MOOSE KNUCKLES': scrape_moose_knuckles, 'MOOSE': scrape_moose_knuckles,
        'SCOTCH SODA': scrape_scotch_soda, 'SCOTCH & SODA': scrape_scotch_soda,
        'ETRO': scrape_etro,
        'GUESS': scrape_guess,
        'EMPORIO ARMANI': scrape_emporio_armani, 'EA': scrape_emporio_armani,
        'ARMANI EXCHANGE': scrape_armani_exchange, 'AX': scrape_armani_exchange,
        'MICHAEL KORS': scrape_michael_kors, 'MK': scrape_michael_kors,
        'PATRIZIA PEPE': scrape_patrizia_pepe, 'PP': scrape_patrizia_pepe,
        'SANDRO': scrape_sandro,
        'ANTONY MORATO': scrape_morato, 'MORATO': scrape_morato,
        'REPLAY': scrape_replay,
        
        # SCRAPER BRANDS (require scrapers/ modules)
        'JOOP': scrape_joop,
        'STRELLSON': scrape_strellson,
        'WOOLRICH': scrape_woolrich,
        'FALKE': scrape_falke,
        'ENTERPRISE JAPAN': scrape_enterprise_japan, 'EJ': scrape_enterprise_japan,
        'LEVI'S': scrape_levis_endpoint, 'LEVIS': scrape_levis_endpoint,
        'GOLDEN GOOSE': scrape_golden_goose_endpoint, 'GG': scrape_golden_goose_endpoint,
    }
    
    if brand in routes:
        return routes[brand]()
    
    return jsonify({
        "error": f"Unknown brand: {brand}",
        "available_brands": sorted(list(set(routes.keys())))
    }), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
