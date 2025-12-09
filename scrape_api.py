"""
Fashion Scraper API - v2
- BOSS: suffix 100 is LAST (product photo without model)
- Proper image ordering
- Better validation
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
TIMEOUT = 10
MIN_BYTES = 8000  # Minimum image size to be valid

# ===================== HELPER FUNCTIONS =====================

def sha1_hash(content: bytes) -> str:
    """Calculate SHA1 hash of content for deduplication"""
    return hashlib.sha1(content).hexdigest()


def validate_image_url(url: str) -> tuple:
    """
    Check if URL returns a valid image
    Returns: (is_valid, content, content_hash)
    """
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "").lower()
            if "image" in content_type and len(response.content) > MIN_BYTES:
                img_hash = sha1_hash(response.content)
                return True, response.content, img_hash
        return False, None, None
    except Exception as e:
        print(f"Error validating {url}: {e}")
        return False, None, None


# ===================== HEALTH CHECK =====================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": time.time()})


@app.route('/ping', methods=['GET'])
def ping():
    """Keep-alive endpoint to prevent Render cold starts"""
    return "pong"


# ===================== BOSS SCRAPER =====================

@app.route('/scrape-boss', methods=['POST'])
def scrape_boss():
    """
    Scrape Hugo Boss images with validation
    Expected SKU format: "HB50549829 001" or "50549829 001"
    
    IMPORTANT: suffix 100 (product photo) goes LAST
    Model photos (200, 300, etc.) come first
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = min(data.get('max_images', 5), 10)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse SKU - keep original format for naming
        original_sku = sku
        clean_sku = sku.replace("HB", "").strip()
        parts = clean_sku.split()
        
        if len(parts) < 2:
            return jsonify({"error": f"Invalid SKU format: {sku}. Expected: 'HB50549829 001' or '50549829 001'"}), 400
        
        num = parts[0]
        color = parts[-1]
        
        # Format SKU for file naming: "HB50468239 202" (with space before color)
        formatted_sku = f"HB{num} {color}"
        
        # Configuration
        prefixes = ["hbeu", "hbna"]
        
        # IMPORTANT: Model shots FIRST, product shot (100) LAST
        model_suffixes = ["200", "300", "340", "240", "210", "201", "230", "220", "250", "260", "270", "280"]
        product_suffixes = ["100", "110", "120", "130", "140", "150"]  # Product shots - go last
        
        img_host = "https://images.hugoboss.com/is/image/boss"
        
        images = []
        seen_hashes = set()
        
        def try_url(pref, suf):
            """Try to get image from URL, return image data if valid"""
            code = f"{pref}{num}_{color}"
            url = f"{img_host}/{code}_{suf}?$large$=&fit=crop,1&align=1,1&bgcolor=ebebeb&wid=1600"
            
            if validate:
                is_valid, content, img_hash = validate_image_url(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    return {"url": url, "suffix": suf, "hash": img_hash[:8]}
            else:
                return {"url": url, "suffix": suf, "validated": False}
            return None
        
        # First: try model shots (200, 300, etc.)
        for pref in prefixes:
            if len(images) >= max_images - 1:  # Leave room for product shot
                break
            for suf in model_suffixes:
                if len(images) >= max_images - 1:
                    break
                result = try_url(pref, suf)
                if result:
                    images.append(result)
        
        # Last: try product shot (100) - always try to add this as last image
        for pref in prefixes:
            if len(images) >= max_images:
                break
            for suf in product_suffixes:
                if len(images) >= max_images:
                    break
                result = try_url(pref, suf)
                if result:
                    images.append(result)
                    break  # Only need one product shot
            if len(images) >= max_images:
                break
        
        # Add index numbers for naming
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": original_sku,
            "formatted_sku": formatted_sku,
            "parsed": {"number": num, "color": color},
            "images": images,
            "count": len(images),
            "validated": validate
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


# ===================== MAJE SCRAPER =====================

@app.route('/scrape-maje', methods=['POST'])
def scrape_maje():
    """
    Scrape Maje images with validation
    Expected SKU format: "MAMFACH00824-0067"
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = min(data.get('max_images', 5), 10)
        validate = data.get('validate', True)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse SKU - remove MA prefix
        original_sku = sku
        base_code = sku.replace("MA", "")
        file_prefix = f"Maje_{base_code}"
        
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        
        images = []
        seen_hashes = set()
        
        # Model shots (1-4)
        for i in range(1, 5):
            if len(images) >= max_images:
                break
                
            file_suffix = f"{file_prefix}_F_{i}.jpg"
            url = f"{base_url}images/hi-res/{file_suffix}?sw=1600&sh=2000"
            
            if validate:
                is_valid, content, img_hash = validate_image_url(url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({
                        "url": url,
                        "type": "model",
                        "index": len(images) + 1,
                        "hash": img_hash[:8],
                        "filename": f"{original_sku}-{len(images) + 1}"
                    })
            else:
                images.append({
                    "url": url,
                    "type": "model",
                    "index": len(images) + 1,
                    "validated": False,
                    "filename": f"{original_sku}-{len(images) + 1}"
                })
        
        # Packshot (product photo) - goes last
        if len(images) < max_images:
            packshot_suffix = f"{file_prefix}_F_P.jpg"
            packshot_url = f"{base_url}images/packshot/{packshot_suffix}?sw=1600&sh=2000"
            
            if validate:
                is_valid, content, img_hash = validate_image_url(packshot_url)
                if is_valid and img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    images.append({
                        "url": packshot_url,
                        "type": "packshot",
                        "index": len(images) + 1,
                        "hash": img_hash[:8],
                        "filename": f"{original_sku}-{len(images) + 1}"
                    })
            else:
                images.append({
                    "url": packshot_url,
                    "type": "packshot",
                    "index": len(images) + 1,
                    "validated": False,
                    "filename": f"{original_sku}-{len(images) + 1}"
                })
        
        return jsonify({
            "sku": original_sku,
            "parsed": {"base_code": base_code, "file_prefix": file_prefix},
            "images": images,
            "count": len(images),
            "validated": validate
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


# ===================== DEBUG ENDPOINT =====================

@app.route('/debug-sku', methods=['POST'])
def debug_sku():
    """Debug endpoint to see how SKU is parsed"""
    data = request.json
    sku = data.get('sku', '')
    brand = data.get('brand', 'BOSS').upper()
    
    result = {"original_sku": sku, "brand": brand}
    
    if brand == 'BOSS':
        clean_sku = sku.replace("HB", "").strip()
        parts = clean_sku.split()
        num = parts[0] if parts else None
        color = parts[-1] if len(parts) >= 2 else None
        formatted_sku = f"HB{num} {color}" if num and color else None
        
        result["parsed"] = {
            "clean_sku": clean_sku,
            "parts": parts,
            "number": num,
            "color": color,
            "formatted_sku": formatted_sku
        }
        
        if num and color:
            result["sample_urls"] = {
                "model_shot": f"https://images.hugoboss.com/is/image/boss/hbeu{num}_{color}_200?$large$=&fit=crop,1&align=1,1&bgcolor=ebebeb&wid=1600",
                "product_shot": f"https://images.hugoboss.com/is/image/boss/hbeu{num}_{color}_100?$large$=&fit=crop,1&align=1,1&bgcolor=ebebeb&wid=1600"
            }
            result["filename_example"] = f"{formatted_sku}-1"
    
    elif brand == 'MAJE':
        base_code = sku.replace("MA", "")
        file_prefix = f"Maje_{base_code}"
        result["parsed"] = {
            "base_code": base_code,
            "file_prefix": file_prefix
        }
        result["sample_urls"] = {
            "model_shot": f"https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/images/hi-res/{file_prefix}_F_1.jpg?sw=1600&sh=2000",
            "packshot": f"https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/images/packshot/{file_prefix}_F_P.jpg?sw=1600&sh=2000"
        }
        result["filename_example"] = f"{sku}-1"
    
    return jsonify(result)


# ===================== MAIN =====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
