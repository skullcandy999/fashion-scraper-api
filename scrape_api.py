"""
Fashion Scraper API - v7 FINAL
Returns EXACTLY max_images URLs per SKU (default 5)
NO validation = instant response
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import re

app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "version": "v7", "brands": ["BOSS", "MAJE", "MANGO", "TOMMY", "ALLSAINTS", "BOGGI"]})

@app.route('/ping', methods=['GET'])
def ping():
    return "pong"


# ===================== BOSS =====================

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
        
        # Model shots first, then product shots
        SUFFIX_ORDER = ["200", "300", "340", "240", "210", "100"]
        IMG_HOST = "https://images.hugoboss.com/is/image/boss"
        
        images = []
        for suf in SUFFIX_ORDER:
            if len(images) >= max_images:
                break
            # Try EU first
            url = f"{IMG_HOST}/hbeu{num}_{color}_{suf}?$large$=&fit=crop,1&align=1,1&wid=1600"
            images.append({"url": url, "index": len(images) + 1, "filename": f"{formatted_sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "formatted_sku": formatted_sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MAJE =====================

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
        
        # Model shots 1-4
        for i in range(1, 5):
            if len(images) >= max_images:
                break
            url = f"{base_url}images/hi-res/{file_prefix}_F_{i}.jpg?sw=1520&sh=2000"
            images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        # Packshot
        if len(images) < max_images:
            url = f"{base_url}images/packshot/{file_prefix}_F_P.jpg?sw=1520&sh=2000"
            images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "formatted_sku": sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== MANGO =====================

@app.route('/scrape-mango', methods=['POST'])
def scrape_mango():
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
        
        # Generate exactly max_images URLs in priority order
        candidate_urls = [
            f"{BASE_IMG}/S/{their_code}.jpg{IMG_PARAM}",  # Packshot
            f"{BASE_IMG}/outfit/S/{their_code}-99999999_01.jpg{IMG_PARAM}",
            f"{BASE_IMG}/outfit/S/{their_code}-99999999_02.jpg{IMG_PARAM}",
            f"{BASE_IMG}/outfit/S/{their_code}-99999999_03.jpg{IMG_PARAM}",
            f"{BASE_IMG}/outfit/S/{their_code}-99999999_04.jpg{IMG_PARAM}",
            f"{BASE_IMG}/S/{their_code}_R.jpg{IMG_PARAM}",
            f"{BASE_IMG}/S/{their_code}_B.jpg{IMG_PARAM}",
        ]
        
        images = []
        for url in candidate_urls[:max_images]:
            images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "formatted_sku": sku, "their_code": their_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== TOMMY HILFIGER =====================

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
        params = "?wid=781&fmt=jpeg&qlt=95%2C1&op_sharpen=0&resMode=sharp2&op_usm=1.5%2C.5%2C0%2C0"
        
        suffixes = ["main", "alternate1", "alternate2", "alternate3", "alternate4"]
        
        images = []
        for suffix in suffixes[:max_images]:
            url = f"{base_url}/{formatted_code}_{suffix}{params}"
            images.append({"url": url, "index": len(images) + 1, "filename": f"{formatted_sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "formatted_sku": formatted_sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== ALL SAINTS =====================

@app.route('/scrape-allsaints', methods=['POST'])
def scrape_allsaints():
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # ASM002PC-162 -> M002PC-162
        if sku.startswith("AS"):
            their_code = sku[2:]
        else:
            their_code = sku
        their_code = re.sub(r"\s+", "-", their_code.strip())
        
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
        
        # Generate exactly max_images URLs (positions 1-5, variant 1)
        images = []
        for pos in range(1, max_images + 1):
            url = make_url(their_code, pos, 1)
            images.append({"url": url, "position": pos, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "formatted_sku": sku, "their_code": their_code, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== BOGGI MILANO =====================

@app.route('/scrape-boggi', methods=['POST'])
def scrape_boggi():
    try:
        data = request.json
        sku = data.get('sku', '').strip()
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        if "-" not in sku:
            return jsonify({"error": f"Invalid SKU format: {sku}"}), 400
        
        osnovna = sku.rsplit("-", 1)[0]
        
        BASE = "https://ecdn.speedsize.com/90526ea8-ead7-46cf-ba09-f3be94be750a/www.boggi.com/dw/image/v2/BBBS_PRD/on/demandware.static/-/Sites-BoggiCatalog/default/images/hi-res/"
        
        images = []
        for i in range(max_images):
            if i == 0:
                url = f"{BASE}{osnovna}.jpeg"
            else:
                url = f"{BASE}{osnovna}_{i}.jpeg"
            images.append({"url": url, "index": len(images) + 1, "filename": f"{sku}-{len(images) + 1}"})
        
        return jsonify({"sku": sku, "formatted_sku": sku, "images": images, "count": len(images)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===================== GENERIC =====================

@app.route('/scrape', methods=['POST'])
def scrape_generic():
    data = request.json
    brand = data.get('brand', '').upper().strip()
    routes = {
        'BOSS': scrape_boss, 'HUGO BOSS': scrape_boss,
        'MAJE': scrape_maje,
        'MANGO': scrape_mango,
        'TOMMY': scrape_tommy, 'TOMMY HILFIGER': scrape_tommy,
        'ALLSAINTS': scrape_allsaints, 'ALL SAINTS': scrape_allsaints,
        'BOGGI': scrape_boggi, 'BOGGI MILANO': scrape_boggi
    }
    if brand in routes:
        return routes[brand]()
    return jsonify({"error": f"Unknown brand: {brand}"}), 400


@app.route('/debug-sku', methods=['POST'])
def debug_sku():
    data = request.json
    return jsonify({"sku": data.get('sku'), "brand": data.get('brand')})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
