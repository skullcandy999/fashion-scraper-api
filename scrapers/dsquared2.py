# ============================================
# DODAJ OVO NA KRAJ POSTOJEĆEG scrape_api.py
# ============================================

# 1. DODAJ OVAJ IMPORT NA VRHU FAJLA (posle ostalih importa)
# from scrapers import dsquared2

# 2. DODAJ OVAJ ENDPOINT NA KRAJ FAJLA (pre if __name__ == '__main__')

@app.route('/scrape-dsquared2', methods=['POST'])
def scrape_dsquared2_endpoint():
    """
    Scrape DSQUARED2 product images.
    """
    try:
        from scrapers import dsquared2  # Ili importuj na vrhu fajla
        
        data = request.get_json()
        sku = data.get('sku', '')
        max_images = data.get('max_images', 5)
        validate = data.get('validate', False)
        
        if not sku:
            return jsonify({
                "error": "SKU is required",
                "sku": sku,
                "images": []
            }), 400
        
        result = dsquared2.scrape(sku, max_images, validate)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "sku": data.get('sku', '') if 'data' in dir() else '',
            "images": []
        }), 500
