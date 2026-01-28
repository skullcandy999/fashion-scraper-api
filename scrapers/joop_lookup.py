# -*- coding: utf-8 -*-
"""
JOOP SKU Lookup Table
Maps our SKU format to JOOP website code

Format:
- Our SKU: JP{MODEL}-{MIDDLE}-{COLOR}
- JOOP code: {PREFIX}{MIDDLE}-{MODEL}-{COLOR}

Note: PREFIX varies (300, 301, 304, etc.) - cannot be predicted algorithmically
"""

# Lookup table: our_sku -> joop_code
JOOP_LOOKUP = {
    "JP10007096-00162-01": "30100162-10007096-01",
    "JP10011739-00042-108": "30100042-10011739-108",
    "JP10012876-30063-108": "30030063-10012876-108",
    "JP10017038-49367-100": "30049367-10017038-100",
    "JP10017375-44769-255": "30044769-10017375-255",
    "JP10017888-00426-01": "30100426-10017888-01",
    "JP10017888-01902-01": "30101902-10017888-01",
    "JP10017927-00030-01": "30100030-10017927-01",
    "JP10017927-44066-01": "30044066-10017927-01",
    "JP10018228-00822-100": "30100822-10018228-100",
    "JP10018884-00111-108": "30100111-10018884-108",
    "JP10018929-00499-405": "30100499-10018929-405",
    "JP10018933-00487-283": "30100487-10018933-283",
    "JP10018972-00882-401": "30100882-10018972-401",
    "JP10019307-45539-100": "30045539-10019307-100",
    "JP10019307-45539-340": "30045539-10019307-340",
    "JP10020526-00415-108": "30100415-10020526-108",
    "JP10020526-00423-108": "30100423-10020526-108",
    "JP10020680-01626-415": "30101626-10020680-415",
    "JP10100011-00095-283": "30100095-10100011-283",
    "JP10100011-00464-283": "30100464-10100011-283",
    "JP10100015-00113-01": "30100113-10100015-01",
    "JP10100019-00168-01": "30100168-10100019-01",
    "JP10100030-00015-242": "30100015-10100030-242",
    "JP10100032-00010-402": "30100010-10100032-402",
    "JP10100051-00256-129": "30100256-10100051-129",
    "JP10100056-00493-242": "30100493-10100056-242",
    "JP10100056-00501-102": "30100501-10100056-102",
    "JP10100056-00501-340": "30100501-10100056-340",
    "JP10100058-00497-242": "30100497-10100058-242",
    "JP10100059-00508-242": "30100508-10100059-242",
    "JP10100059-00510-242": "30100510-10100059-242",
    "JP10100063-00492-102": "30100492-10100063-102",
    "JP10100063-00496-405": "30100496-10100063-405",
    "JP10100075-00089-469": "30100089-10100075-469",
    "JP10100075-00849-469": "30100849-10100075-469",
    "JP10100151-01684-402": "30101684-10100151-402",
    "JP10100209-00048-01": "30100048-10100209-01",
    "JP10100209-00057-01": "30100057-10100209-01",
    "JP10100216-01519-420": "30101519-10100216-420",
    "JP10100223-01700-402": "30101700-10100223-402",
    "JP10100229-01730-242": "30101730-10100229-242",
    "JP10100289-01525-10": "30101525-10100289-10",
    "JP10100293-01527-425": "30101527-10100293-425",
    "JP10100354-01638-415": "30101638-10100354-415",
    "JP10100355-01640-421": "30101640-10100355-421",
    "JP10101390-01918-240": "30101918-10101390-240",
}


def get_joop_code(our_sku: str) -> str:
    """
    Convert our SKU to JOOP code.

    Args:
        our_sku: Our format (e.g., "JP10017927-00030-01")

    Returns:
        JOOP code (e.g., "30100030-10017927-01") or None if not in lookup
    """
    our_sku = our_sku.strip().upper()
    if not our_sku.startswith('JP'):
        our_sku = 'JP' + our_sku

    # Direct lookup
    if our_sku in JOOP_LOOKUP:
        return JOOP_LOOKUP[our_sku]

    # Try with different color formats (001 vs 01 vs 1)
    parts = our_sku.split('-')
    if len(parts) == 3:
        model, middle, color = parts
        color_stripped = color.lstrip('0') or '0'

        # Try variations
        variations = [
            f"{model}-{middle}-{color}",
            f"{model}-{middle}-{color_stripped}",
            f"{model}-{middle}-0{color_stripped}",
            f"{model}-{middle}-00{color_stripped}",
        ]

        for var in variations:
            if var in JOOP_LOOKUP:
                return JOOP_LOOKUP[var]

    return None


def normalize_our_sku(sku: str) -> str:
    """
    Normalize our SKU format.
    """
    sku = sku.strip().upper()
    if not sku.startswith('JP'):
        sku = 'JP' + sku
    return sku


# Quick stats
if __name__ == "__main__":
    print(f"JOOP Lookup Table: {len(JOOP_LOOKUP)} SKUs")

    # Count by prefix
    prefixes = {}
    for joop_code in JOOP_LOOKUP.values():
        prefix = joop_code[:3]
        prefixes[prefix] = prefixes.get(prefix, 0) + 1

    print("\nBy prefix:")
    for p, count in sorted(prefixes.items()):
        print(f"  {p}: {count}")

    print("\nSample entries:")
    for i, (sku, code) in enumerate(list(JOOP_LOOKUP.items())[:5]):
        print(f"  {sku} -> {code}")
