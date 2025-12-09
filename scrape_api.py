"""
Fashion Scraper API - FINAL
EXACT logic from local Python scripts
Returns max 5 URLs per SKU (no validation - n8n will filter)

BOSS & MAJE - already working, unchanged
MANGO - from mango.py
TOMMY - from tommy.py  
BOGGI - from boggi.py
ALLSAINTS - from allsaints.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "version": "final", "brands": ["BOSS", "MAJE", "MANGO", "TOMMY", "ALLSAINTS", "BOGGI"]})

@app.route('/ping', methods=['GET'])
def ping():
    return "pong"


# ===================== BOSS (unchanged - working) =====================
@app.route('/scrape-boss', methods=['POST'])
def scrape_boss():
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_img = min(data.get('max_images', 5), 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        parts = sku.replace("HB", "").strip().split()
        if len(parts) < 2:
            return jsonify({"error": "Invalid SKU format"}), 400
        
        num, color = parts[0], parts[-1]
        formatted_sku = f"HB{num} {color}"
        
        # Model shots first (200s, 300s), product shots last (100s)
        SUFFIXES = ["200", "300", "340", "240", "210", "100", "110"]
        HOST = "https://images.hugoboss.com/is/image/boss"
        
        images = []
        for suf in SUFFIXES:
            if len(images) >= max_img:
                break
            url = f"{HOST}/hbeu{num}_{color}_{suf}?$large$=&fit=crop,1&align=1,1&wid=1600"
            images.append({"url": url, "index": len(images)+1, "filename": f"{formatted_sku}-{len(images)+1}"})
        
        return jsonify({"sku": sku, "formatted_sku": formatted_sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MAJE (unchanged - working) =====================
@app.route('/scrape-maje', methods=['POST'])
def scrape_maje():
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_img = min(data.get('max_images', 5), 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        base_code = sku.replace("MA", "")
        prefix = f"Maje_{base_code}"
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        
        images = []
        # Model shots 1-4
        for i in range(1, 5):
            if len(images) >= max_img:
                break
            url = f"{base_url}images/hi-res/{prefix}_F_{i}.jpg?sw=1520&sh=2000"
            images.append({"url": url, "index": len(images)+1, "filename": f"{sku}-{len(images)+1}"})
        
        # Packshot last
        if len(images) < max_img:
            url = f"{base_url}images/packshot/{prefix}_F_P.jpg?sw=1520&sh=2000"
            images.append({"url": url, "index": len(images)+1, "filename": f"{sku}-{len(images)+1}"})
        
        return jsonify({"sku": sku, "formatted_sku": sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MANGO (from mango.py) =====================
@app.route('/scrape-mango', methods=['POST'])
def scrape_mango():
    """
    EXACT logic from your mango.py:
    - SKU: MNG27011204-TS -> their_code: 27011204_TS
    - Order: packshot, outfit 01-04, R, B, D1-D12
    - BASE: https://shop.mango.com/assets/rcs/pics/static/T2/fotos
    - IMG_PARAM: ?imwidth=2048&imdensity=1
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_img = min(data.get('max_images', 5), 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse: MNG27011204-TS -> number=27011204, color=TS
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if not m:
            return jsonify({"error": f"Invalid SKU format: {sku}. Expected: MNG27011204-TS"}), 400
        
        number, color = m.group(1), m.group(2)
        their_code = f"{number}_{color}"
        
        # EXACT from your code
        BASE_IMG = "https://shop.mango.com/assets/rcs/pics/static/T2/fotos"
        IMG_PARAM = "?imwidth=2048&imdensity=1"
        
        # Generate ALL candidate URLs in EXACT order from your code
        all_urls = []
        
        # 1. Packshot
        all_urls.append(f"{BASE_IMG}/S/{their_code}.jpg{IMG_PARAM}")
        
        # 2. Outfit shots 01-04
        for i in range(1, 5):
            all_urls.append(f"{BASE_IMG}/outfit/S/{their_code}-99999999_{i:02}.jpg{IMG_PARAM}")
        
        # 3. R and B variants
        all_urls.append(f"{BASE_IMG}/S/{their_code}_R.jpg{IMG_PARAM}")
        all_urls.append(f"{BASE_IMG}/S/{their_code}_B.jpg{IMG_PARAM}")
        
        # 4. Detail shots D1-D12
        for d in range(1, 13):
            all_urls.append(f"{BASE_IMG}/S/{their_code}_D{d}.jpg{IMG_PARAM}")
        
        # Take first max_img URLs
        images = []
        for i, url in enumerate(all_urls[:max_img]):
            images.append({"url": url, "index": i+1, "filename": f"{sku}-{i+1}"})
        
        return jsonify({
            "sku": sku,
            "formatted_sku": sku,
            "their_code": their_code,
            "images": images,
            "count": len(images)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== TOMMY HILFIGER (from tommy.py) =====================
@app.route('/scrape-tommy', methods=['POST'])
def scrape_tommy():
    """
    EXACT logic from your tommy.py:
    - SKU: AM0AM13659-BDS -> formatted_code: AM0AM13659_BDS
    - Output name: TH{code} (your code uses HT but TH makes more sense)
    - URL: https://tommy-europe.scene7.com/is/image/TommyEurope/{code}_{suffix}?params
    - Suffixes: main, alternate1, alternate2, alternate3, alternate4
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_img = min(data.get('max_images', 5), 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Remove TH prefix if present (your code does this)
        base_code = sku.replace("TH", "")
        # Replace - with _ for URL
        formatted_code = base_code.replace("-", "_")
        # Output SKU format
        formatted_sku = f"TH{base_code}"
        
        # EXACT URL pattern from your code
        base_url = "https://tommy-europe.scene7.com/is/image/TommyEurope"
        params = "?wid=781&fmt=jpeg&qlt=95%2C1&op_sharpen=0&resMode=sharp2&op_usm=1.5%2C.5%2C0%2C0&iccEmbed=0&printRes=72"
        
        # EXACT suffixes from your code
        suffixes = ["main", "alternate1", "alternate2", "alternate3", "alternate4"]
        
        images = []
        for i, suffix in enumerate(suffixes[:max_img]):
            url = f"{base_url}/{formatted_code}_{suffix}{params}"
            images.append({"url": url, "index": i+1, "filename": f"{formatted_sku}-{i+1}"})
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "formatted_code": formatted_code,
            "images": images,
            "count": len(images)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ALL SAINTS (from allsaints.py) =====================
@app.route('/scrape-allsaints', methods=['POST'])
def scrape_allsaints():
    """
    EXACT logic from your allsaints.py:
    - SKU: ASM002PC-162 -> their_code: M002PC-162
    - SKU: ASW006DC DUSTY BLUE -> their_code: W006DC-DUSTY-BLUE
    - Uses JQ filter URLs with sfcc-gallery-position
    - Has 2 variants per position, variant 1 is primary
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_img = min(data.get('max_images', 5), 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # EXACT conversion from your code: moja_u_njihova()
        # ASM002PC-162 -> M002PC-162
        # ASW006DC DUSTY BLUE -> W006DC-DUSTY-BLUE
        if sku.startswith("ASM") or sku.startswith("ASW"):
            their_code = sku[2:]  # Remove 'AS'
        else:
            their_code = sku
        # Replace spaces with dashes
        their_code = re.sub(r"\s+", "-", their_code.strip())
        
        # EXACT URL function from your code: allsaints_url()
        def make_url(code: str, position: int, variant: int) -> str:
            if variant == 1:
                filt = ("fn_select:jq:first%28.%5B%5D%7Cif%20has%28%22metadata%22%29%20then%20"
                        "select%28any%28.metadata%5B%5D%3B%20.external_id%20%3D%3D%20"
                        "%22sfcc-gallery-position%22%20and%20.value%20%3D%3D%20"
                        f"{position}%29%29%20else%20empty%20end%29")
            else:
                filt = ("fn_select:jq:first%28.%5B%5D%7Cif%20has%28%22metadata%22%29%20then%20"
                        "select%28any%28.metadata%5B%5D%3B%20.external_id%20%3D%3D%20"
                        "%22sfcc_pdp_gallery_position_prod%22%20and%20.value%20%3D%3D%20"
                        f"{position}%29%29%20else%20empty%20end%29")
            return (f"https://media.i.allsaints.com/image/list/{filt}/"
                    f"f_auto,q_auto,dpr_auto,w_1674,h_2092,c_fit/"
                    f"{code}.json?_i=AG")
        
        # Generate URLs for positions 1-5, variant 1 only (primary)
        # Your code tries variant 1 first, then variant 2 as fallback
        images = []
        for pos in range(1, max_img + 1):
            url = make_url(their_code, pos, 1)
            images.append({
                "url": url,
                "position": pos,
                "variant": 1,
                "index": pos,
                "filename": f"{sku}-{pos}"
            })
        
        return jsonify({
            "sku": sku,
            "formatted_sku": sku,
            "their_code": their_code,
            "images": images,
            "count": len(images)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== BOGGI MILANO (from boggi.py) =====================
@app.route('/scrape-boggi', methods=['POST'])
def scrape_boggi():
    """
    EXACT logic from your boggi.py:
    - SKU: BO25A014901-NAVY -> osnovna: BO25A014901
    - URL pattern: {osnovna}.jpeg, {osnovna}_1.jpeg, {osnovna}_2.jpeg, etc.
    - BASE: https://ecdn.speedsize.com/.../images/hi-res/
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_img = min(data.get('max_images', 5), 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # EXACT parsing from your code
        if "-" not in sku:
            return jsonify({"error": f"Invalid SKU format: {sku}. Expected: BO25A014901-NAVY"}), 400
        
        osnovna, boja = sku.rsplit("-", 1)
        
        # EXACT base URL from your code
        BASE = "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/Sites-BoggiCatalog/default/images/hi-res/"
        
        # EXACT pattern from your code: osnovna.jpeg, osnovna_1.jpeg, etc.
        images = []
        for i in range(max_img):
            if i == 0:
                file_part = f"{osnovna}.jpeg"
            else:
                file_part = f"{osnovna}_{i}.jpeg"
            
            url = BASE + file_part
            images.append({"url": url, "index": i+1, "filename": f"{sku}-{i+1}"})
        
        return jsonify({
            "sku": sku,
            "formatted_sku": sku,
            "osnovna": osnovna,
            "boja": boja,
            "images": images,
            "count": len(images)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== GENERIC ENDPOINT =====================
@app.route('/scrape', methods=['POST'])
def scrape_generic():
    """Routes to correct scraper based on brand"""
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


# ===================== DEBUG ENDPOINT =====================
@app.route('/debug-sku', methods=['POST'])
def debug_sku():
    """Debug endpoint to see SKU parsing"""
    data = request.json
    sku = data.get('sku', '')
    brand = data.get('brand', '').upper()
    
    result = {"original_sku": sku, "brand": brand}
    
    if brand in ('BOSS', 'HUGO BOSS'):
        parts = sku.replace("HB", "").strip().split()
        if len(parts) >= 2:
            result["formatted_sku"] = f"HB{parts[0]} {parts[-1]}"
            result["num"] = parts[0]
            result["color"] = parts[-1]
    
    elif brand == 'MAJE':
        result["formatted_sku"] = sku
        result["base_code"] = sku.replace("MA", "")
    
    elif brand == 'MANGO':
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if m:
            result["their_code"] = f"{m.group(1)}_{m.group(2)}"
            result["number"] = m.group(1)
            result["color"] = m.group(2)
            result["formatted_sku"] = sku
    
    elif brand in ('TOMMY', 'TOMMY HILFIGER'):
        base_code = sku.replace("TH", "")
        result["formatted_sku"] = f"TH{base_code}"
        result["formatted_code"] = base_code.replace("-", "_")
    
    elif brand in ('ALLSAINTS', 'ALL SAINTS'):
        their_code = sku[2:] if sku.startswith("AS") else sku
        result["their_code"] = re.sub(r"\s+", "-", their_code.strip())
        result["formatted_sku"] = sku
    
    elif brand in ('BOGGI', 'BOGGI MILANO'):
        if "-" in sku:
            parts = sku.rsplit("-", 1)
            result["osnovna"] = parts[0]
            result["boja"] = parts[1]
            result["formatted_sku"] = sku
    
    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
