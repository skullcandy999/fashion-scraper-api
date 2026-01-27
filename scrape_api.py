"""
Fashion Scraper API - OPTIMIZED PARALLEL + MANGO BASE64
All brands with parallel validation, MANGO downloads and returns base64
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter, Retry
import hashlib
import time
import re
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import scraper modula
from scrapers import dsquared2


app = Flask(__name__)
CORS(app)

# ===================== CONSTANTS =====================
TIMEOUT = 10
MIN_BYTES = 8000
MAX_VALIDATION_WORKERS = 15  # Parallel workers

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

def validate_single_url(args):
    """Validate a single URL - used by parallel executor"""
    url, metadata, custom_session, min_bytes = args
    s = custom_session or session
    try:
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and r.content and len(r.content) > min_bytes:
            content_type = r.headers.get("Content-Type", "").lower()
            if "image" in content_type or len(r.content) > 20000:
                return (url, True, r.content, sha1_hash(r.content), metadata)
        return (url, False, None, None, metadata)
    except Exception:
        return (url, False, None, None, metadata)

def validate_urls_parallel(url_metadata_list, custom_session=None, min_bytes=MIN_BYTES, max_images=5):
    """
    Validate multiple URLs in parallel.
    url_metadata_list: list of (url, metadata_dict) tuples
    Returns: list of valid image dicts with url and metadata
    """
    if not url_metadata_list:
        return []
    
    args_list = [(url, meta, custom_session, min_bytes) for url, meta in url_metadata_list]
    url_order = {url: idx for idx, (url, _) in enumerate(url_metadata_list)}
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_VALIDATION_WORKERS) as executor:
        futures = [executor.submit(validate_single_url, args) for args in args_list]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result[1]:  # is_valid
                    results.append(result)
            except:
                pass
    
    # Sort by original order
    results.sort(key=lambda x: url_order.get(x[0], 999))
    
    # Build final list with deduplication
    images = []
    seen_hashes = set()
    
    for url, is_valid, content, img_hash, metadata in results:
        if len(images) >= max_images:
            break
        if img_hash and img_hash not in seen_hashes:
            seen_hashes.add(img_hash)
            img = {"url": url}
            img.update(metadata)
            images.append(img)
    
    return images

# ===================== ENDPOINTS =====================
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "version": "optimized-parallel-v3"})

@app.route('/ping', methods=['GET'])
def ping():
    return "pong"


# ===================== BOSS / HUGO (PARALLEL) =====================
@app.route('/scrape-boss', methods=['POST'])
@app.route('/scrape-hugo', methods=['POST'])
def scrape_boss():
    """BOSS / HUGO - isti scraper, 21 pozicija × 2 prefiksa - PARALLEL"""
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
        
        # Build all URLs
        url_list = []
        for pref in PREFIXES:
            for suf in SUFFIX_ORDER:
                url = f"{IMG_HOST}/{pref}{num}_{color}_{suf}?$large$=&fit=crop,1&align=1,1&wid=1600"
                url_list.append((url, {"suffix": suf, "prefix": pref}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images + 5)
        
        # Reorder: model shots first, product shots (100s) last
        model_shots = [img for img in images if not img.get("suffix", "").startswith("1")]
        product_shots = [img for img in images if img.get("suffix", "").startswith("1")]
        images = (model_shots + product_shots)[:max_images]
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "formatted_sku": formatted_sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MAJE (PARALLEL) =====================
@app.route('/scrape-maje', methods=['POST'])
def scrape_maje():
    """MAJE - PARALLEL validation"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        base_code = sku.replace("MA", "")
        file_prefix = f"Maje_{base_code}"
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        
        # Build all URLs
        url_list = []
        for i in range(1, 6):
            url = f"{base_url}images/hi-res/{file_prefix}_F_{i}.jpg?sw=1520&sh=2000"
            url_list.append((url, {"type": "model", "position": i}))
        
        # Packshot
        url = f"{base_url}images/packshot/{file_prefix}_F_P.jpg?sw=1520&sh=2000"
        url_list.append((url, {"type": "packshot", "position": 6}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "formatted_sku": sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MANGO (BASE64 + PARALLEL) =====================
@app.route('/scrape-mango', methods=['POST'])
def scrape_mango():
    """MANGO - Downloads images and returns BASE64 (site blocks direct access)"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if not m:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        number, color = m.group(1), m.group(2)
        their_code = f"{number}_{color}"
        
        BASE_IMG = "https://shop.mango.com/assets/rcs/pics/static/T2/fotos"
        IMG_PARAM = "?imwidth=2048&imdensity=1"
        
        # Build candidate URLs
        # Order: Main, Outfit, R, D1 (detail), B (packshot as 5th)
        candidate_urls = []
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}.jpg{IMG_PARAM}")           # 1. Main
        for i in range(1, 5):
            candidate_urls.append(f"{BASE_IMG}/outfit/S/{their_code}-99999999_{i:02}.jpg{IMG_PARAM}")  # 2. Outfit
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}_R.jpg{IMG_PARAM}")         # 3. R (rear)
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}_D1.jpg{IMG_PARAM}")        # 4. D1 (detail)
        candidate_urls.append(f"{BASE_IMG}/S/{their_code}_B.jpg{IMG_PARAM}")         # 5. B (packshot)
        # Additional details if needed
        for d in range(2, 13):
            candidate_urls.append(f"{BASE_IMG}/S/{their_code}_D{d}.jpg{IMG_PARAM}")
        
        # Create session with Mango headers
        # IMPORTANT: Request JPEG format, not AVIF (Modal can't process AVIF)
        mango_session = make_session({
            "Accept": "image/jpeg,image/*;q=0.8",
            "Referer": "https://shop.mango.com/",
            "Accept-Language": "en-US,en;q=0.9"
        })
        
        # Download and validate images in parallel, return base64
        def download_mango_image(args):
            url, idx = args
            try:
                r = mango_session.get(url, timeout=TIMEOUT)
                if r.status_code == 200 and r.content and len(r.content) > MIN_BYTES:
                    content_type = r.headers.get("Content-Type", "").lower()
                    if "image" in content_type:
                        img_hash = sha1_hash(r.content)
                        b64 = base64.b64encode(r.content).decode('utf-8')
                        return (url, True, b64, img_hash, idx)
            except:
                pass
            return (url, False, None, None, idx)
        
        # Parallel download
        images = []
        seen_hashes = set()
        
        args_list = [(url, idx) for idx, url in enumerate(candidate_urls)]
        
        with ThreadPoolExecutor(max_workers=MAX_VALIDATION_WORKERS) as executor:
            futures = [executor.submit(download_mango_image, args) for args in args_list]
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result[1]:  # is_valid
                        results.append(result)
                except:
                    pass
        
        # Sort by original order
        results.sort(key=lambda x: x[4])
        
        # Build final list
        for url, is_valid, b64_data, img_hash, idx in results:
            if len(images) >= max_images:
                break
            if img_hash and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({
                    "url": url,
                    "base64": b64_data,
                    "index": len(images) + 1,
                    "filename": f"{sku}-{len(images) + 1}"
                })
        
        return jsonify({
            "sku": sku,
            "formatted_sku": sku,
            "their_code": their_code,
            "images": images,
            "count": len(images),
            "note": "Images returned as base64"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== TOMMY HILFIGER (PARALLEL) =====================
@app.route('/scrape-tommy', methods=['POST'])
def scrape_tommy():
    """TOMMY HILFIGER - PARALLEL validation"""
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
        
        # Build all URLs
        url_list = [(f"{base_url}/{formatted_code}_{suffix}{params}", {"suffix": suffix}) for suffix in suffixes]
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "formatted_sku": formatted_sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ALL SAINTS (PARALLEL) =====================
@app.route('/scrape-allsaints', methods=['POST'])
def scrape_allsaints():
    """ALL SAINTS - PARALLEL validation"""
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
            "Accept": "image/jpeg,image/*;q=0.8",
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
        
        # Build all URLs
        url_list = []
        for pos in range(1, 11):
            for variant in (1, 2):
                url = make_url(their_code, pos, variant)
                url_list.append((url, {"position": pos, "variant": variant}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, custom_session=as_session, min_bytes=MIN_AS, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "formatted_sku": sku, "their_code": their_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== BOGGI MILANO (NO VALIDATION - fast) =====================
@app.route('/scrape-boggi', methods=['POST'])
def scrape_boggi():
    """BOGGI MILANO - NO VALIDATION (n8n filters)"""
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

        return jsonify({
            "sku": sku,
            "formatted_sku": sku,
            "model_code": model_code,
            "color_code": color_code,
            "landing_page": "empty",
            "images": images,
            "count": len(images),
            "note": "No validation – n8n filters invalid images"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== DSQUARED2 =====================
@app.route('/scrape-dsquared2', methods=['POST'])
def scrape_dsquared2_endpoint():
    """DSQUARED2 - uses scrapers/dsquared2.py module"""
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


# ===================== CALVIN KLEIN (PARALLEL) =====================
@app.route('/scrape-calvin-klein', methods=['POST'])
def scrape_calvin_klein():
    """CALVIN KLEIN - 5 pozicija - PARALLEL"""
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
        
        # Build all URLs
        url_list = [(f"{BASE}{formatted_code}_{suffix}?wid=1600&fmt=jpeg&qlt=95", {"suffix": suffix}) for suffix in SUFFIXES]
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": formatted_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== COACH =====================
@app.route('/scrape-coach', methods=['POST'])
def scrape_coach_endpoint():
    """COACH - uses scrapers/scrape_coach.py module"""
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


# ===================== KURT GEIGER (PARALLEL) =====================
@app.route('/scrape-kurt-geiger', methods=['POST'])
def scrape_kurt_geiger():
    """KURT GEIGER - 9 frames - PARALLEL"""
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
        
        # Build all URLs
        url_list = [(f"https://media.global.kurtgeiger.com/product/{prod_id}/{frame}/{prod_id}?w=1920", {"frame": frame}) for frame in FRAMES]
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, min_bytes=4000, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": prod_id, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== KATE SPADE (PARALLEL) =====================
@app.route('/scrape-kate-spade', methods=['POST'])
def scrape_kate_spade():
    """KATE SPADE - multi-color support - PARALLEL"""
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
        
        # Build all URLs for all color variants
        url_list = []
        for clr in color_candidates:
            for suffix in SUFFIXES:
                url = f"{BASE}/{model}_{clr}{suffix}?$desktopProductZoom$"
                url_list.append((url, {"color": clr, "suffix": suffix}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, min_bytes=15000, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        working_color = images[0].get("color", "") if images else ""
        return jsonify({"sku": sku, "brand_code": f"{model}_{working_color}", "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== PAUL TAYLOR (PARALLEL) =====================
@app.route('/scrape-paul-taylor', methods=['POST'])
def scrape_paul_taylor():
    """PAUL TAYLOR - 2 sezone × 10 brojeva - PARALLEL"""
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
        
        # Build all URLs
        url_list = []
        for season in SEASONS:
            for n in NUMS:
                url = f"{BASE}/{their_base}_{season}_{n}.jpg"
                url_list.append((url, {"season": season, "num": n}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, min_bytes=12000, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": their_base, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MOOSE KNUCKLES (PARALLEL) =====================
@app.route('/scrape-moose-knuckles', methods=['POST'])
def scrape_moose_knuckles():
    """MOOSE KNUCKLES - 17 sufiksa - PARALLEL"""
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
        
        # Build all URLs
        url_list = [(f"{BASE}/{site_code}_{suf}.jpg", {"suffix": suf}) for suf in SUFFIX_ORDER]
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, min_bytes=20000, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": site_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== SCOTCH & SODA (PARALLEL) =====================
@app.route('/scrape-scotch-soda', methods=['POST'])
def scrape_scotch_soda():
    """SCOTCH & SODA - 18+ sufiksa - PARALLEL"""
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
        
        # Build all URLs
        url_list = [(f"{BASE_CDN}/Hires_PNG-{their}{suf}?width=1800", {"suffix": suf}) for suf in SUFFIXES]
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, min_bytes=12000, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": their, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ETRO (PARALLEL) =====================
@app.route('/scrape-etro', methods=['POST'])
def scrape_etro():
    """ETRO - 5 sufiksa - PARALLEL"""
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
        
        # Build all URLs
        url_list = [(f"https://content.etro.com/Adaptations/900/{etro_code}_{suffix}_01.jpg", {"suffix": suffix}) for suffix in SUFFIXES]
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku.replace(' ', '_')}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": etro_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== GUESS (PARALLEL) =====================
@app.route('/scrape-guess', methods=['POST'])
def scrape_guess():
    """GUESS - 6 sufiksa - PARALLEL"""
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
        
        # Build all URLs
        url_list = [(f"{BASE}{guess_code}{suffix}", {"suffix": suffix}) for suffix in SUFFIXES]
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku.replace(' ', '_')}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": guess_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== EMPORIO ARMANI (PARALLEL) =====================
@app.route('/scrape-emporio-armani', methods=['POST'])
def scrape_emporio_armani():
    """EMPORIO ARMANI - 4 sezone × 3 sufiksa - PARALLEL"""
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
        
        # Build all URLs
        url_list = []
        for season in SEASONS:
            for suf in SUFFIXES:
                url = f"https://assets-cf.armani.com/image/upload/f_auto,q_auto:best,ar_4:5,w_1350,c_fill/{armani_code}_{suf}_{season}.jpg"
                url_list.append((url, {"season": season, "suffix": suf}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": armani_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ARMANI EXCHANGE (PARALLEL) =====================
@app.route('/scrape-armani-exchange', methods=['POST'])
def scrape_armani_exchange():
    """ARMANI EXCHANGE - 3 sezone × 5 sufiksa - PARALLEL"""
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
        
        # Build all URLs
        url_list = []
        for season in SEASONS:
            for suf in SUFFIXES:
                url = f"https://assets.armani.com/image/upload/f_auto,q_auto:best,ar_4:5,w_1350,c_fill/{ax_code}_{suf}_{season}.jpg"
                url_list.append((url, {"season": season, "suffix": suf}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku.replace('-', '_')}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": ax_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MICHAEL KORS (PARALLEL) =====================
@app.route('/scrape-michael-kors', methods=['POST'])
def scrape_michael_kors():
    """MICHAEL KORS - 2 varijante boje × 8 pozicija - PARALLEL"""
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
        
        # Build all URLs
        url_list = []
        for clr in color_variants:
            for i in range(1, 9):
                url = f"https://michaelkors.scene7.com/is/image/MichaelKors/{product}-{clr}_{i}?wid=1200&hei=1500&fmt=jpg"
                url_list.append((url, {"color": clr, "position": i}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku.replace('-', '_')}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": f"{product}-{color}", "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== PATRIZIA PEPE (PARALLEL) =====================
@app.route('/scrape-patrizia-pepe', methods=['POST'])
def scrape_patrizia_pepe():
    """PATRIZIA PEPE - 5 sezona × 8 pozicija - PARALLEL"""
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
        
        # Build all URLs
        url_list = []
        for season in SEASONS:
            for i in range(1, 9):
                url = f"https://cdn.patriziapepe.com/image/upload/w_1200/q_auto:good/f_auto/CHALCO/SFCC/{product_fabric}/{color}/{season}/{full_code}_{i}.jpg"
                url_list.append((url, {"season": season, "position": i}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku.replace(' ', '_')}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": full_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== SANDRO (PARALLEL) =====================
@app.route('/scrape-sandro', methods=['POST'])
def scrape_sandro():
    """SANDRO - 6 sufiksa - PARALLEL"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        code = sku[2:] if sku.startswith('SA') else sku
        
        BASE = "https://eu.sandro-paris.com/dw/image/v2/BCMW_PRD/on/demandware.static/-/Sites-master-catalog/default/images/hi-res/"
        SUFFIXES = ["F_1", "F_2", "F_3", "F_4", "F_5"]
        
        # Build all URLs
        url_list = [(f"{BASE}Sandro_{code}_{suffix}.jpg?sw=2000&sh=2000", {"suffix": suffix, "type": "model"}) for suffix in SUFFIXES]
        # Packshot
        url_list.append((f"https://eu.sandro-paris.com/dw/image/v2/BCMW_PRD/on/demandware.static/-/Sites-master-catalog/default/images/packshot/Sandro_{code}_F_P.jpg?sw=2000&sh=2000", {"suffix": "F_P", "type": "packshot"}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku.replace('-', '_')}-{idx + 1}"
        
        return jsonify({"sku": sku, "brand_code": code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ANTONY MORATO (PARALLEL) =====================
@app.route('/scrape-morato', methods=['POST'])
def scrape_morato():
    """ANTONY MORATO - kompleksna konverzija + 6 pozicija - PARALLEL"""
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
        
        # Build all URLs
        url_list = []
        for their in their_codes:
            fn = re.sub(r"\s+", "-", their.strip()).upper()
            d1, d2 = fn[0], fn[1]
            for i in range(1, 7):
                url = f"https://cdn.antonymorato.com.filoblu.com/rx/960x,ofmt_webp/media/catalog/product/{d1}/{d2}/{fn}_0{i}.jpg"
                url_list.append((url, {"code": their, "position": i}))
        
        # Validate in parallel
        images = validate_urls_parallel(url_list, max_images=max_images)
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{sku}-{idx + 1}"
        
        working_code = images[0].get("code", their_codes[0]) if images else their_codes[0]
        return jsonify({"sku": sku, "brand_code": working_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== REPLAY (PARALLEL with watermark filter) =====================
@app.route('/scrape-replay', methods=['POST'])
def scrape_replay():
    """REPLAY - multi-region, filtrira watermark - PARALLEL"""
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
        
        cdn_code, model = parse_replay_sku(sku)
        if not cdn_code:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        CDN_BASE = "https://replayjeans.kleecks-cdn.com"
        REGIONS = ["gr", "it", "de", "fr", "es", "eu", "uk"]
        IMG_PARAMS = "?optimize=low&bg-color=255,255,255&fit=bounds&height=1200&width=900&canvas=900:1200"
        
        d1 = cdn_code[0]
        d2 = cdn_code[1]
        
        # Build all URLs for all regions
        url_list = []
        for region in REGIONS:
            for pos in range(1, 11):
                url = f"{CDN_BASE}/{region}/media/catalog/product/{d1}/{d2}/{cdn_code}_{pos}.jpg{IMG_PARAMS}"
                url_list.append((url, {"region": region, "position": pos}))
        
        # Custom parallel validation with watermark filter
        def validate_replay_url(args):
            url, metadata, _, min_bytes = args
            try:
                r = session.get(url, timeout=12)
                if r.status_code == 200 and len(r.content) >= 8000:
                    ctype = r.headers.get("Content-Type", "").lower()
                    if "image" in ctype:
                        if len(r.content) == WATERMARK_SIZE:
                            return (url, False, None, None, metadata)
                        img_hash = hashlib.md5(r.content).hexdigest()
                        if img_hash in WATERMARK_HASHES:
                            return (url, False, None, None, metadata)
                        return (url, True, r.content, img_hash, metadata)
            except:
                pass
            return (url, False, None, None, metadata)
        
        # Validate in parallel
        args_list = [(url, meta, None, 8000) for url, meta in url_list]
        url_order = {url: idx for idx, (url, _) in enumerate(url_list)}
        results = []
        
        with ThreadPoolExecutor(max_workers=MAX_VALIDATION_WORKERS) as executor:
            futures = [executor.submit(validate_replay_url, args) for args in args_list]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result[1]:
                        results.append(result)
                except:
                    pass
        
        results.sort(key=lambda x: url_order.get(x[0], 999))
        
        images = []
        seen_hashes = set()
        for url, is_valid, content, img_hash, metadata in results:
            if len(images) >= max_images:
                break
            if img_hash and img_hash not in seen_hashes:
                seen_hashes.add(img_hash)
                images.append({"url": url, "region": metadata["region"], "position": metadata["position"]})
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{re.sub(r'[{}]', '', sku).replace(' ', '_')}-{idx + 1}"
        
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


# ===================== LEVI'S =====================
@app.route('/scrape-levis', methods=['POST'])
def scrape_levis_endpoint():
    """LEVI'S - uses scrapers/scrape_levis.py module"""
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


# ===================== GOLDEN GOOSE =====================
@app.route('/scrape-golden-goose', methods=['POST'])
def scrape_golden_goose_endpoint():
    """GOLDEN GOOSE - uses scrapers/scrape_golden_goose.py module"""
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


# ===================== LIU JO =====================
@app.route('/scrape-liujo', methods=['POST'])
def scrape_liujo_endpoint():
    """LIU JO - uses scrapers/liujo.py module"""
    try:
        from scrapers import liujo
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', False)
        if not sku:
            return jsonify({"error": "SKU required", "sku": sku, "images": []}), 400
        result = liujo.scrape(sku, max_images, validate)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "sku": "", "images": []}), 500


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
        "LEVI'S": scrape_levis_endpoint, 'LEVIS': scrape_levis_endpoint,
        'GOLDEN GOOSE': scrape_golden_goose_endpoint, 'GG': scrape_golden_goose_endpoint,
        'COACH': scrape_coach_endpoint,
        'LIU JO': scrape_liujo_endpoint, 'LIUJO': scrape_liujo_endpoint, 'LJ': scrape_liujo_endpoint,
    }
    
    if brand in routes:
        return routes[brand]()
    
    return jsonify({
        "error": f"Unknown brand: {brand}",
        "available_brands": sorted(list(set(routes.keys())))
    }), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
