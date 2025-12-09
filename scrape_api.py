from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter, Retry

app = Flask(__name__)
CORS(app)

session = requests.Session()
retries = Retry(total=2, backoff_factor=0.3, status_forcelist=(429,500,502,503,504))
session.mount("https://", HTTPAdapter(max_retries=retries))
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

TIMEOUT = 5  # Brži timeout jer samo proveravamo URL

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/scrape-boss', methods=['POST'])
def scrape_boss():
    try:
        data = request.json
        sku = data.get('sku')
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        parts = sku.replace("HB", "").strip().split()
        if len(parts) < 2:
            return jsonify({"error": "Invalid SKU format"}), 400
        
        num, color = parts[0], parts[-1]
        
        prefixes = ["hbeu", "hbna"]
        suffixes = ["200","245","300","340","240","210","201","230","220","250"]
        
        img_host = "https://images.hugoboss.com/is/image/boss"
        images = []
        
        for pref in prefixes:
            if len(images) >= max_images:
                break
            for suf in suffixes:
                if len(images) >= max_images:
                    break
                code = f"{pref}{num}_{color}"
                url = f"{img_host}/{code}_{suf}?wid=2000&qlt=90"
                try:
                    # Samo HEAD request - ne downloadujemo sliku!
                    r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
                    if r.status_code == 200:
                        images.append({"url": url, "index": len(images) + 1})
                except:
                    pass
        
        return jsonify({
            "sku": sku,
            "images": images,
            "count": len(images)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/scrape-maje', methods=['POST'])
def scrape_maje():
    try:
        data = request.json
        sku = data.get('sku')
        max_images = data.get('max_images', 5)
        
        if not sku:
            return jsonify({"error": "SKU required"}), 400
        
        # Tvoja logika čišćenja
        base_code = sku.replace("MA", "")
        
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        file_prefix = f"Maje_{base_code}"
        
        images = []
        
        # Model slike (1-4)
        for i in range(1, 5):
            if len(images) >= max_images:
                break
            file_suffix = f"{file_prefix}_F_{i}.jpg"
            url = f"{base_url}images/hi-res/{file_suffix}?sw=1600&sh=2000"
            try:
                r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
                if r.status_code == 200:
                    images.append({"url": url, "type": "model", "index": i})
            except:
                pass
        
        # Packshot (5)
        if len(images) < max_images:
            packshot_suffix = f"{file_prefix}_F_P.jpg"
            url = f"{base_url}images/packshot/{packshot_suffix}?sw=1600&sh=2000"
            try:
                r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
                if r.status_code == 200:
                    images.append({"url": url, "type": "packshot", "index": 5})
            except:
                pass
        
        return jsonify({
            "sku": sku,
            "images": images,
            "count": len(images)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
