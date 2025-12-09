"""
Fashion Scraper API - Improved Version
Validates images actually exist before returning URLs
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter, Retry
import hashlib
import concurrent.futures
from functools import lru_cache
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


def validate_image_url(url: str) -> tuple[bool, bytes | None]:
    """
    Check if URL returns a valid image
    Returns: (is_valid, content)
    """
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "").lower()
            if "image" in content_type and len(response.content) > MIN_BYTES:
                return True, response.content
        return False, None
    except Exception:
        return False, None


def validate_image_url_head(url: str) -> bool:
    """
    Quick HEAD request to check if image exists
    Faster than full GET, but less reliable
    """
    try:
        response = session.head(url, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "").lower()
            content_length = int(response.headers.get("Content-Length", 0))
            return "image" in content_type and content_length > MIN_BYTES
        return False
    except Exception:
        return False


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
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = min(data.get('max_images', 5), 10)  # Cap at 10
        validate = data.get('validate', True)  # Option to skip validation
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse SKU
        clean_sku = sku.replace("HB", "").strip()
        parts = clean_sku.split()
        
        if len(parts) < 2:
            return jsonify({"error": f"Invalid SKU format: {sku}. Expected: 'HB50549829 001' or '50549829 001'"}), 400
        
        num = parts[0]
        color = parts[-1]
        
        # Configuration
        prefixes = ["hbeu", "hbna"]
        suffixes = [
            "200", "245", "300", "340", "240", "210", "201", 
            "230", "220", "250", "260", "270", "280",
            "100", "110", "120", "130", "140", "150"
        ]
        img_host = "https://images.hugoboss.com/is/image/boss"
        
        # Generate all possible URLs
        candidate_urls = []
        for pref in prefixes:
            for suf in suffixes:
                code = f"{pref}{num}_{color}"
                url = f"{img_host}/{code}_{suf}?wid=2000&qlt=90"
                candidate_urls.append(url)
        
        images = []
        seen_hashes = set()
        
        if validate:
            # Validate URLs in parallel for speed
            def check_url(url):
                is_valid, content = validate_image_url(url)
                if is_valid and content:
                    img_hash = sha1_hash(content)
                    return url, img_hash
                return None, None
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(check_url, url): url for url in candidate_urls}
                
                for future in concurrent.futures.as_completed(futures):
                    if len(images) >= max_images:
                        break
                    
                    url, img_hash = future.result()
                    if url and img_hash and img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        images.append({
                            "url": url,
                            "index": len(images) + 1,
                            "hash": img_hash[:8]  # Short hash for reference
                        })
        else:
            # No validation - just return generated URLs (faster but less reliable)
            for url in candidate_urls[:max_images]:
                images.append({
                    "url": url,
                    "index": len(images) + 1,
                    "validated": False
                })
        
        return jsonify({
            "sku": sku,
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
        base_code = sku.replace("MA", "")
        file_prefix = f"Maje_{base_code}"
        
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        
        # Generate candidate URLs
        candidate_urls = []
        
        # Model shots (1-4)
        for i in range(1, 5):
            file_suffix = f"{file_prefix}_F_{i}.jpg"
            url = f"{base_url}images/hi-res/{file_suffix}?sw=1600&sh=2000"
            candidate_urls.append({"url": url, "type": "model", "index": i})
        
        # Packshot
        packshot_suffix = f"{file_prefix}_F_P.jpg"
        packshot_url = f"{base_url}images/packshot/{packshot_suffix}?sw=1600&sh=2000"
        candidate_urls.append({"url": packshot_url, "type": "packshot", "index": 5})
        
        # Additional variants (V1, V2, etc.)
        for v in range(1, 4):
            variant_suffix = f"{file_prefix}_V{v}.jpg"
            variant_url = f"{base_url}images/hi-res/{variant_suffix}?sw=1600&sh=2000"
            candidate_urls.append({"url": variant_url, "type": "variant", "index": 5 + v})
        
        images = []
        seen_hashes = set()
        
        if validate:
            for item in candidate_urls:
                if len(images) >= max_images:
                    break
                
                is_valid, content = validate_image_url(item["url"])
                if is_valid and content:
                    img_hash = sha1_hash(content)
                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        images.append({
                            "url": item["url"],
                            "type": item["type"],
                            "index": len(images) + 1,
                            "hash": img_hash[:8]
                        })
        else:
            # No validation
            for item in candidate_urls[:max_images]:
                images.append({
                    "url": item["url"],
                    "type": item["type"],
                    "index": len(images) + 1,
                    "validated": False
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


# ===================== GENERIC SCRAPER (for future brands) =====================

@app.route('/scrape', methods=['POST'])
def scrape_generic():
    """
    Generic endpoint - routes to correct scraper based on brand
    """
    try:
        data = request.json
        brand = data.get('brand', '').upper()
        
        if brand == 'BOSS':
            return scrape_boss()
        elif brand == 'MAJE':
            return scrape_maje()
        else:
            return jsonify({"error": f"Unknown brand: {brand}. Supported: BOSS, MAJE"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== DEBUG ENDPOINT =====================

@app.route('/debug-sku', methods=['POST'])
def debug_sku():
    """
    Debug endpoint to see how SKU is parsed without making requests
    """
    data = request.json
    sku = data.get('sku', '')
    brand = data.get('brand', 'BOSS').upper()
    
    result = {"original_sku": sku, "brand": brand}
    
    if brand == 'BOSS':
        clean_sku = sku.replace("HB", "").strip()
        parts = clean_sku.split()
        result["parsed"] = {
            "clean_sku": clean_sku,
            "parts": parts,
            "number": parts[0] if parts else None,
            "color": parts[-1] if len(parts) >= 2 else None
        }
        
        if len(parts) >= 2:
            num, color = parts[0], parts[-1]
            result["sample_urls"] = [
                f"https://images.hugoboss.com/is/image/boss/hbeu{num}_{color}_200?wid=2000&qlt=90",
                f"https://images.hugoboss.com/is/image/boss/hbna{num}_{color}_200?wid=2000&qlt=90"
            ]
    
    elif brand == 'MAJE':
        base_code = sku.replace("MA", "")
        file_prefix = f"Maje_{base_code}"
        result["parsed"] = {
            "base_code": base_code,
            "file_prefix": file_prefix
        }
        result["sample_urls"] = [
            f"https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/images/hi-res/{file_prefix}_F_1.jpg?sw=1600&sh=2000"
        ]
    
    return jsonify(result)


# ===================== MAIN =====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
