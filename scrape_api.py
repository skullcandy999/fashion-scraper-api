"""
Fashion Scraper API - v3
MATCHES LOCAL CODE EXACTLY
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter, Retry
import hashlib
import time

app = Flask(__name__)
CORS(app)

# ===================== HTTP SESSION WITH RETRIES =====================
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=(429, 500, 502, 503, 504)
)
session.mount("https://", HTTPAdapter(max_retries=retries))
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
})

# ===================== CONSTANTS =====================
TIMEOUT = 12  # Same as local
MIN_BYTES = 8000  # Same as local

# ===================== HELPER FUNCTIONS =====================

def sha1_hash(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def validate_image(url: str) -> tuple:
    """Check if URL returns valid image. Returns (is_valid, content, hash)"""
    try:
        r = session.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and r.content and len(r.content) > MIN_BYTES:
            content_type = r.headers.get("Content-Type", "").lower()
            if "image" in content_type:
                return True, r.content, sha1_hash(r.content)
        return False, None, None
    except Exception:
        return False, None, None


# ===================== ENDPOINTS =====================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": time.time()})


@app.route('/ping', methods=['GET'])
def ping():
    return "pong"


# ===================== BOSS SCRAPER =====================
# EXACTLY MATCHES YOUR LOCAL CODE

@app.route('/scrape-boss', methods=['POST'])
def scrape_boss():
    """
    Scrape Hugo Boss - IDENTICAL to local Python code
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse SKU - same as local code
        parts = sku.replace("HB", "").strip().split()
        if len(parts) < 2:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        num = parts[0]
        color = parts[-1]
        
        # EXACT SAME AS LOCAL CODE
        PREFIXES = ["hbeu", "hbna"]
        SUFFIX_ORDER = [
            "200", "245", "300", "340", "240", "210", "201", "230", "220", "250", "260", "270", "280",
            "100", "110", "120", "130", "140", "150", "350", "360"
        ]
        IMG_HOST = "https://images.hugoboss.com/is/image/boss"
        
        # Format for filename: "HB50468239 202"
        formatted_sku = f"HB{num} {color}"
        
        images = []
        seen_hashes = set()
        
        for pref in PREFIXES:
            if len(images) >= max_images:
                break
            for suf in SUFFIX_ORDER:
                if len(images) >= max_images:
                    break
                
                code = f"{pref}{num}_{color}"
                # EXACT SAME URL FORMAT AS LOCAL CODE
                url = f"{IMG_HOST}/{code}_{suf}?$large$=&fit=crop,1&align=1,1&wid=1600"
                
                if validate:
                    is_valid, content, img_hash = validate_image(url)
                    if is_valid and img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        images.append({
                            "url": url,
                            "index": len(images) + 1,
                            "suffix": suf,
                            "hash": img_hash[:8]
                        })
                else:
                    # No validation - just return URL
                    images.append({
                        "url": url,
                        "index": len(images) + 1,
                        "suffix": suf,
                        "validated": False
                    })
        
        # Reorder: product shots (100, 110, etc.) should be LAST
        # First: model shots (200+), Last: product shots (100s)
        model_shots = [img for img in images if not img["suffix"].startswith("1")]
        product_shots = [img for img in images if img["suffix"].startswith("1")]
        images = model_shots + product_shots
        
        # Update indices after reordering
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "parsed": {"number": num, "color": color},
            "images": images,
            "count": len(images),
            "validated": validate,
            "note": "Product shots (100s) moved to end"
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


# ===================== MAJE SCRAPER =====================
# EXACTLY MATCHES YOUR LOCAL CODE

@app.route('/scrape-maje', methods=['POST'])
def scrape_maje():
    """
    Scrape Maje - IDENTICAL to local Python code
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse - same as local
        base_code = sku.replace("MA", "")
        file_prefix = f"Maje_{base_code}"
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        
        images = []
        seen_hashes = set()
        
        # Model shots 1-4
        for i in range(1, 5):
            if len(images) >= max_images:
                break
            
            file_suffix = f"{file_prefix}_F_{i}.jpg"
            url = f"{base_url}images/hi-res/{file_suffix}?sw=1520&sh=2000"  # Same as local!
            
            if validate:
                is_valid, content, img_hash = validate_image(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({
                        "url": url,
                        "type": "model",
                        "index": len(images) + 1,
                        "hash": img_hash[:8],
                        "filename": f"{sku}-{len(images) + 1}"
                    })
            else:
                images.append({
                    "url": url,
                    "type": "model",
                    "index": len(images) + 1,
                    "filename": f"{sku}-{len(images) + 1}"
                })
        
        # Packshot (5th image)
        if len(images) < max_images:
            packshot_suffix = f"{file_prefix}_F_P.jpg"
            packshot_url = f"{base_url}images/packshot/{packshot_suffix}?sw=1520&sh=2000"
            
            if validate:
                is_valid, content, img_hash = validate_image(packshot_url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({
                        "url": packshot_url,
                        "type": "packshot",
                        "index": len(images) + 1,
                        "hash": img_hash[:8],
                        "filename": f"{sku}-{len(images) + 1}"
                    })
            else:
                images.append({
                    "url": packshot_url,
                    "type": "packshot",
                    "index": len(images) + 1,
                    "filename": f"{sku}-{len(images) + 1}"
                })
        
        return jsonify({
            "sku": sku,
            "parsed": {"base_code": base_code, "file_prefix": file_prefix},
            "images": images,
            "count": len(images),
            "validated": validate
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


# ===================== DEBUG =====================

@app.route('/debug-sku', methods=['POST'])
def debug_sku():
    data = request.json
    sku = data.get('sku', '')
    brand = data.get('brand', 'BOSS').upper()
    
    if brand == 'BOSS':
        parts = sku.replace("HB", "").strip().split()
        num = parts[0] if parts else None
        color = parts[-1] if len(parts) >= 2 else None
        return jsonify({
            "sku": sku,
            "parsed": {"number": num, "color": color},
            "formatted_sku": f"HB{num} {color}" if num and color else None,
            "sample_url": f"https://images.hugoboss.com/is/image/boss/hbeu{num}_{color}_200?$large$=&fit=crop,1&align=1,1&wid=1600" if num and color else None
        })
    else:
        base_code = sku.replace("MA", "")
        return jsonify({
            "sku": sku,
            "parsed": {"base_code": base_code},
            "sample_url": f"https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/images/hi-res/Maje_{base_code}_F_1.jpg?sw=1520&sh=2000"
        })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
