"""
Fashion Scraper API - v6 OPTIMIZED
NO VALIDATION - Just generates URLs, n8n downloads and filters
This is FAST because no HTTP requests are made to validate images
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import re

app = Flask(__name__)
CORS(app)

# ===================== ENDPOINTS =====================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "timestamp": time.time(),
        "brands": ["BOSS", "MAJE", "MANGO", "TOMMY", "ALLSAINTS", "BOGGI"],
        "note": "v6 - Fast URL generation, no validation"
    })

@app.route('/ping', methods=['GET'])
def ping():
    return "pong"


# ===================== BOSS =====================

@app.route('/scrape-boss', methods=['POST'])
def scrape_boss():
    """Hugo Boss - generates URLs"""
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        parts = sku.replace("HB", "").strip().split()
        if len(parts) < 2:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        num = parts[0]
        color = parts[-1]
        formatted_sku = f"HB{num} {color}"
        
        PREFIXES = ["hbeu", "hbna"]
        # Model shots first, product shots (100s) last
        SUFFIX_ORDER = [
            "200", "245", "300", "340", "240", "210", "201", "230", "220", "250", "260", "270", "280",
            "100", "110", "120", "130", "140", "150", "350", "360"
        ]
        IMG_HOST = "https://images.hugoboss.com/is/image/boss"
        
        images = []
        for pref in PREFIXES:
            if len(images) >= max_images * 2:  # Generate more, n8n will filter
                break
            for suf in SUFFIX_ORDER:
                if len(images) >= max_images * 2:
                    break
                code = f"{pref}{num}_{color}"
                url = f"{IMG_HOST}/{code}_{suf}?$large$=&fit=crop,1&align=1,1&wid=1600"
                images.append({"url": url, "suffix": suf})
        
        # Reorder: model shots first, product shots last
        model_shots = [img for img in images if not img["suffix"].startswith("1")]
        product_shots = [img for img in images if img["suffix"].startswith("1")]
        images = (model_shots + product_shots)[:max_images * 2]
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "images": images,
            "count": len(images)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MAJE =====================

@app.route('/scrape-maje', methods=['POST'])
def scrape_maje():
    """Maje - generates URLs"""
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
        
        # Model shots 1-4
        for i in range(1, 5):
            file_suffix = f"{file_prefix}_F_{i}.jpg"
            url = f"{base_url}images/hi-res/{file_suffix}?sw=1520&sh=2000"
            images.append({"url": url, "type": "model", "index": len(images) + 1})
        
        # Packshot
        packshot_suffix = f"{file_prefix}_F_P.jpg"
        packshot_url = f"{base_url}images/packshot/{packshot_suffix}?sw=1520&sh=2000"
        images.append({"url": packshot_url, "type": "packshot", "index": len(images) + 1})
        
        formatted_sku = sku
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "images": images[:max_images],
            "count": min(len(images), max_images)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MANGO =====================

@app.route('/scrape-mango', methods=['POST'])
def scrape_mango():
    """
    Mango - EXACT URL patterns from your local code
    Uses T2/fotos path
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse: MNG27011204-TS -> 27011204_TS
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if not m:
            return jsonify({"error": f"Invalid SKU format: {sku}. Expected: MNG27011204-TS"}), 400
        
        number, color = m.group(1), m.group(2)
        their_code = f"{number}_{color}"
        formatted_sku = sku
        
        # EXACT paths from your local code - T2/fotos
        BASE_IMG = "https://shop.mango.com/assets/rcs/pics/static/T2/fotos"
        IMG_PARAM = "?imwidth=2048&imdensity=1"
        
        images = []
        
        # 1. Packshot
        images.append({"url": f"{BASE_IMG}/S/{their_code}.jpg{IMG_PARAM}", "type": "packshot"})
        
        # 2. Outfit shots 01-04
        for i in range(1, 5):
            images.append({"url": f"{BASE_IMG}/outfit/S/{their_code}-99999999_{i:02}.jpg{IMG_PARAM}", "type": "outfit"})
        
        # 3. R and B variants
        images.append({"url": f"{BASE_IMG}/S/{their_code}_R.jpg{IMG_PARAM}", "type": "variant_R"})
        images.append({"url": f"{BASE_IMG}/S/{their_code}_B.jpg{IMG_PARAM}", "type": "variant_B"})
        
        # 4. Detail shots D1-D12
        for d in range(1, 13):
            images.append({"url": f"{BASE_IMG}/S/{their_code}_D{d}.jpg{IMG_PARAM}", "type": f"detail_D{d}"})
        
        # Set indices and filenames
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "their_code": their_code,
            "images": images,  # Return ALL, n8n will filter valid ones
            "count": len(images),
            "note": "n8n will download and filter valid images, then keep max 5"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== TOMMY HILFIGER =====================

@app.route('/scrape-tommy', methods=['POST'])
def scrape_tommy():
    """
    Tommy Hilfiger - EXACT URL patterns from your local code
    Output naming: TH{code}-1.jpg (your code uses HT but I assume TH for Tommy Hilfiger)
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Remove TH prefix if present
        base_code = sku.replace("TH", "")
        formatted_code = base_code.replace("-", "_")
        
        # Your code saves as "HT{code}" - keeping that
        formatted_sku = f"TH{base_code}"
        
        # EXACT URL pattern from your code
        base_url = "https://tommy-europe.scene7.com/is/image/TommyEurope"
        params = "?wid=781&fmt=jpeg&qlt=95%2C1&op_sharpen=0&resMode=sharp2&op_usm=1.5%2C.5%2C0%2C0&iccEmbed=0&printRes=72"
        
        # URL suffixes in order
        url_suffixes = ["main", "alternate1", "alternate2", "alternate3", "alternate4"]
        
        images = []
        for suffix in url_suffixes:
            url = f"{base_url}/{formatted_code}_{suffix}{params}"
            images.append({"url": url, "type": suffix})
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "formatted_code": formatted_code,
            "images": images[:max_images],
            "count": min(len(images), max_images)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ALL SAINTS =====================

@app.route('/scrape-allsaints', methods=['POST'])
def scrape_allsaints():
    """
    All Saints - EXACT URL patterns from your local code
    Generates URLs for positions 1-10, both variants
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Convert SKU - EXACT logic from your code
        # ASM002PC-162 -> M002PC-162
        # ASW006DC DUSTY BLUE -> W006DC-DUSTY-BLUE
        if sku.startswith("ASM") or sku.startswith("ASW"):
            their_code = sku[2:]  # Remove 'AS'
        else:
            their_code = sku
        their_code = re.sub(r"\s+", "-", their_code.strip())
        
        formatted_sku = sku
        
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
        
        # Generate URLs for positions 1-10, variant 1 first (more reliable)
        for pos in range(1, 11):
            # Variant 1 first
            images.append({
                "url": allsaints_url(their_code, pos, 1),
                "position": pos,
                "variant": 1
            })
            # Variant 2 as backup
            images.append({
                "url": allsaints_url(their_code, pos, 2),
                "position": pos,
                "variant": 2
            })
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{((idx // 2) + 1)}"  # Group by position
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
            "their_code": their_code,
            "images": images,
            "count": len(images),
            "note": "Contains both variants for each position. n8n should try variant 1 first, then variant 2."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== BOGGI MILANO =====================

@app.route('/scrape-boggi', methods=['POST'])
def scrape_boggi():
    """
    Boggi Milano - EXACT URL patterns from your local code
    Sequential: osnovna.jpeg, osnovna_1.jpeg, osnovna_2.jpeg...
    """
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Parse: BO25A014901-NAVY -> osnovna=BO25A014901
        if "-" not in sku:
            return jsonify({"error": f"Invalid SKU format: {sku}. Expected: BO25A014901-NAVY"}), 400
        
        parts = sku.rsplit("-", 1)
        osnovna = parts[0]
        boja = parts[1] if len(parts) > 1 else ""
        
        formatted_sku = sku
        
        # EXACT base URL from your code
        BASE = "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/Sites-BoggiCatalog/default/images/hi-res/"
        
        images = []
        
        # EXACT pattern from your code
        for i in range(max_images):
            if i == 0:
                file_part = f"{osnovna}.jpeg"
            else:
                file_part = f"{osnovna}_{i}.jpeg"
            
            url = BASE + file_part
            images.append({"url": url, "index": i + 1})
        
        for idx, img in enumerate(images):
            img["index"] = idx + 1
            img["filename"] = f"{formatted_sku}-{idx + 1}"
        
        return jsonify({
            "sku": sku,
            "formatted_sku": formatted_sku,
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
    """Debug endpoint"""
    data = request.json
    sku = data.get('sku', '')
    brand = data.get('brand', '').upper()
    
    result = {"original_sku": sku, "brand": brand}
    
    if brand in ('BOSS', 'HUGO BOSS'):
        parts = sku.replace("HB", "").strip().split()
        result["formatted_sku"] = f"HB{parts[0]} {parts[-1]}" if len(parts) >= 2 else None
    elif brand == 'MAJE':
        result["formatted_sku"] = sku
    elif brand == 'MANGO':
        m = re.match(r"MNG(\d+)-([A-Z0-9]+)$", sku, re.I)
        if m:
            result["their_code"] = f"{m.group(1)}_{m.group(2)}"
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
        parts = sku.rsplit("-", 1)
        result["osnovna"] = parts[0]
        result["formatted_sku"] = sku
    
    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
