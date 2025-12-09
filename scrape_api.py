from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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
        suffixes = ["200","245","300","340","240","210","201","230","220","250","260","270","280","100"]
        
        img_host = "https://images.hugoboss.com/is/image/boss"
        images = []
        
        # Instant generation - nema provere!
        for pref in prefixes:
            if len(images) >= max_images:
                break
            for suf in suffixes:
                if len(images) >= max_images:
                    break
                code = f"{pref}{num}_{color}"
                url = f"{img_host}/{code}_{suf}?wid=2000&qlt=90"
                images.append({"url": url, "index": len(images) + 1})
        
        return jsonify({"sku": sku, "images": images, "count": len(images)})
    
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
        
        base_code = sku.replace("MA", "")
        base_url = "https://ca.maje.com/dw/image/v2/AAON_PRD/on/demandware.static/-/Sites-maje-master-catalog/default/"
        file_prefix = f"Maje_{base_code}"
        
        images = []
        
        # Model slike (1-4)
        for i in range(1, min(5, max_images + 1)):
            file_suffix = f"{file_prefix}_F_{i}.jpg"
            url = f"{base_url}images/hi-res/{file_suffix}?sw=1600&sh=2000"
            images.append({"url": url, "type": "model", "index": i})
        
        # Packshot (5)
        if len(images) < max_images:
            packshot_suffix = f"{file_prefix}_F_P.jpg"
            url = f"{base_url}images/packshot/{packshot_suffix}?sw=1600&sh=2000"
            images.append({"url": url, "type": "packshot", "index": 5})
        
        return jsonify({"sku": sku, "images": images, "count": len(images)})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**Commit → Deploy (2 min)**

---

### **2. n8n proverava validnost i duplikate**

**Dodaj ove nodove u workflow:**

**A) Posle "Split Images" → HTTP Request node:**
```
Name: Download Image
Method: GET
URL: ={{ $json.url }}
Response Format: File
Options:
  - Timeout: 20000
  - Continue On Fail: TRUE (VAŽNO!)
```

**B) Filter node:**
```
Name: Filter Valid Images
Conditions: error.message does NOT exist
