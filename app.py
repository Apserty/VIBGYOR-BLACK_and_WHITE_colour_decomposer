import os
import re
import math
import itertools
from difflib import get_close_matches
import colorsys
from functools import reduce
import numpy as np
from flask import Flask, render_template, request, jsonify
from scipy.optimize import nnls, minimize
import requests
from dotenv import load_dotenv
import webcolors
from matplotlib import colors as mcolors

load_dotenv() # Load API keys from .env if present

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.json.sort_keys = False

# 1. DEFINE YOUR CUSTOM 9-COLOR SCALE (Standardized RGB values)
PALETTE = {
    'Violet': np.array([148, 0, 211]),
    'Indigo': np.array([75, 0, 130]),
    'Blue':   np.array([0, 0, 255]),
    'Green':  np.array([0, 255, 0]),
    'Yellow': np.array([255, 255, 0]),
    'Orange': np.array([255, 127, 0]),
    'Red':    np.array([255, 0, 0]),
    'Black':  np.array([0, 0, 0]),
    'White':  np.array([255, 255, 255])
}

# Convert Palette to Matrix for Math Solver
color_names = list(PALETTE.keys())

# Standard base colors map (normalized_name -> (Palette_Name, Hex))
BASE_COLORS = {
    'violet': ('Violet', '#9400D3'),
    'indigo': ('Indigo', '#4B0082'),
    'blue':   ('Blue', '#0000FF'),
    'green':  ('Green', '#00FF00'),
    'yellow': ('Yellow', '#FFFF00'),
    'orange': ('Orange', '#FF7F00'),
    'red':    ('Red', '#FF0000'),
    'black':  ('Black', '#000000'),
    'white':  ('White', '#FFFFFF')
}

# Common everyday color dictionary for accurate mapping
COMMON_COLORS = {
    'parrot green': '#32CD32',
    'lime green': '#32CD32',
    'leaf green': '#4C9A2A',
    'grass green': '#3F9B0B',
    'mint green': '#98FF98',
    'forest green': '#228B22',
    'olive green': '#808000',
    'sea green': '#2E8B57',
    'emerald green': '#50C878',
    'apple green': '#8DB600',
    'bottle green': '#006A4E',
    'neon green': '#39FF14',
    'sky blue': '#87CEEB',
    'navy blue': '#000080',
    'royal blue': '#4169E1',
    'baby blue': '#89CFF0',
    'powder blue': '#B0E0E6',
    'peacock blue': '#005F69',
    'ice blue': '#AFEEEE',
    'ocean blue': '#006994',
    'mustard yellow': '#FFDB58',
    'lemon yellow': '#FFF700',
    'canary yellow': '#FFEF00',
    'golden yellow': '#FFDF00',
    'coral red': '#FF7F50',
    'coral': '#FF7F50',
    'crimson': '#DC143C',
    'maroon': '#800000',
    'burgundy': '#800020',
    'ruby': '#E0115F',
    'blood red': '#660000',
    'scarlet': '#FF2400',
    'magenta': '#FF00FF',
    'fuchsia': '#FF00FF',
    'hot pink': '#FF69B4',
    'pink': '#FFC0CB',
    'rose': '#FF007F',
    'peach': '#FFDAB9',
    'apricot': '#FBCEB1',
    'salmon': '#FA8072',
    'turquoise': '#40E0D0',
    'teal': '#008080',
    'cyan': '#00FFFF',
    'gold': '#FFD700',
    'amber': '#FFBF00',
    'bronze': '#CD7F32',
    'copper': '#B87333',
    'brown': '#8B4513',
    'chocolate': '#7B3F00',
    'coffee': '#6F4E37',
    'beige': '#F5F5DC',
    'ivory': '#FFFFF0',
    'cream': '#FFFDD0',
    'khaki': '#C3B091',
    'charcoal': '#36454F',
    'slate': '#708090',
    'silver': '#C0C0C0',
    'lavender': '#E6E6FA',
    'plum': '#8E4585',
    'periwinkle': '#CCCCFF',
    'mauve': '#E0B0FF',
    'violet red': '#F75394'
}

def normalize_name(value):
    """Converts a name into a comparison-safe form: lowercase alphanumeric only."""
    return re.sub(r'[^a-z0-9]+', '', value.lower().strip())


def extract_hex(value):
    """Extracts a 6-digit hex string from arbitrary text/value."""
    if not isinstance(value, str):
        return None
    match = re.search(r'#?[0-9a-fA-F]{6}', value)
    if not match:
        return None
    candidate = match.group(0)
    return candidate if candidate.startswith('#') else f"#{candidate}"


def build_color_lexicon():
    """Creates a large color-name lexicon from common dictionary + matplotlib dictionaries."""
    lexicon = {}

    for name, hex_value in COMMON_COLORS.items():
        lexicon[normalize_name(name)] = hex_value.upper()

    for name, hex_value in mcolors.CSS4_COLORS.items():
        lexicon[normalize_name(name)] = hex_value.upper()

    for key, hex_value in mcolors.XKCD_COLORS.items():
        plain_name = key.replace("xkcd:", "")
        lexicon[normalize_name(plain_name)] = hex_value.upper()

    return lexicon


COLOR_LEXICON = build_color_lexicon()

COLOR_MODIFIERS = {
    "dark": {"lightness": -0.25, "saturation": 0.0},
    "deep": {"lightness": -0.20, "saturation": 0.05},
    "light": {"lightness": 0.20, "saturation": 0.0},
    "pale": {"lightness": 0.22, "saturation": -0.20},
    "bright": {"lightness": 0.10, "saturation": 0.18},
    "vivid": {"lightness": 0.05, "saturation": 0.22},
    "soft": {"lightness": 0.08, "saturation": -0.18}
}


def resolve_from_lexicon(name, cutoff=0.80):
    """Resolves a color name from lexicon by exact normalized match or fuzzy match."""
    normalized = normalize_name(name)
    if normalized in COLOR_LEXICON:
        return COLOR_LEXICON[normalized]

    close = get_close_matches(normalized, COLOR_LEXICON.keys(), n=1, cutoff=cutoff)
    if close:
        return COLOR_LEXICON[close[0]]
    return None


def apply_modifier(base_hex, modifier):
    """Applies lightness/saturation modifier to a resolved base color."""
    if modifier not in COLOR_MODIFIERS:
        return base_hex

    modifier_delta = COLOR_MODIFIERS[modifier]
    r = int(base_hex[1:3], 16) / 255.0
    g = int(base_hex[3:5], 16) / 255.0
    b = int(base_hex[5:7], 16) / 255.0

    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = min(1.0, max(0.0, l + modifier_delta["lightness"]))
    s = min(1.0, max(0.0, s + modifier_delta["saturation"]))

    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(round(nr * 255)):02X}{int(round(ng * 255)):02X}{int(round(nb * 255)):02X}"


def resolve_color_hex(query):
    """Resolves any user-entered color label to hex via layered fallbacks."""
    clean_query = query.strip()
    lower_query = clean_query.lower()
    normalized_query = normalize_name(clean_query)

    # 0. Direct hex input support.
    direct_hex = extract_hex(clean_query)
    if direct_hex:
        return direct_hex.upper()

    # 1. Base color exact match (VIBGYOR, Black, White).
    if normalized_query in BASE_COLORS:
        return BASE_COLORS[normalized_query][1]

    # 2. Direct standard CSS names.
    try:
        return webcolors.name_to_hex(lower_query).upper()
    except ValueError:
        pass

    # 3. Resolve from expanded lexicon (Common + CSS4 + XKCD).
    matched_hex = resolve_from_lexicon(clean_query, cutoff=0.85)
    if matched_hex:
        return matched_hex

    # 4. Modifier-based parsing: "dark red", "light blue", "pale green".
    tokens = [t for t in re.split(r'\s+', lower_query) if t]
    if len(tokens) >= 2 and tokens[0] in COLOR_MODIFIERS:
        modifier_key = tokens[0]
        base_hex = resolve_from_lexicon(" ".join(tokens[1:]), cutoff=0.72)
        if base_hex:
            return apply_modifier(base_hex, modifier_key)

    # 5. General typo-tolerant match from expanded lexicon.
    matched_hex = resolve_from_lexicon(clean_query, cutoff=0.65)
    if matched_hex:
        return matched_hex

    # 6. Guarded API fallback: accept only if returned name is semantically close.
    try:
        resp = requests.get(
            "https://api.color.pizza/v1/",
            params={"name": clean_query},
            timeout=5
        )
        if resp.ok:
            payload = resp.json()
            colors = payload.get("colors", [])
            if colors:
                candidate_name = normalize_name(str(colors[0].get("name", "")))
                if candidate_name and (
                    candidate_name == normalized_query or
                    candidate_name in normalized_query or
                    normalized_query in candidate_name
                ):
                    raw_hex = colors[0].get("hex")
                    if isinstance(raw_hex, dict):
                        raw_hex = raw_hex.get("value")
                    parsed_hex = extract_hex(raw_hex)
                    if parsed_hex:
                        return parsed_hex.upper()
    except requests.RequestException:
        pass

    # 7. Guaranteed final fallback: neutral gray.
    return "#808080"


def compute_practical_parts(weights_dict, max_total_parts=12):
    """
    Finds practical small-integer parts (total parts <= max_total_parts)
    that closely match true mixture proportions for real-world paint mixing.
    """
    active_colors = [c for c, w in weights_dict.items() if w > 0.005]
    k = len(active_colors)
    if k == 0:
        return {}
    if k == 1:
        return {active_colors[0]: 1}

    weights = np.array([weights_dict[c] for c in active_colors], dtype=float)
    weights = weights / np.sum(weights)

    best_parts = None
    best_error = float('inf')

    # Search for optimal small total parts (e.g., between k and max_total_parts)
    candidate_totals = [t for t in range(k, max_total_parts + 1)]
    # Also include standard convenient paint totals if not already present
    for extra in [10, 12, 15]:
        if extra not in candidate_totals and extra >= k:
            candidate_totals.append(extra)
    candidate_totals.sort()

    for total in candidate_totals:
        raw_p = weights * total
        p = np.maximum(1, np.round(raw_p)).astype(int)

        diff = total - np.sum(p)
        while diff != 0:
            if diff > 0:
                residuals = raw_p - p
                idx = int(np.argmax(residuals))
                p[idx] += 1
                diff -= 1
            else:
                valid_indices = [i for i in range(k) if p[i] > 1]
                if not valid_indices:
                    break
                residuals = [p[i] - raw_p[i] for i in valid_indices]
                idx = valid_indices[int(np.argmax(residuals))]
                p[idx] -= 1
                diff += 1

        if np.sum(p) == total:
            proportions = p / total
            mse = float(np.mean((proportions - weights) ** 2))
            # Mild penalty for higher total parts to prefer simpler ratios
            score = mse + (total * 0.0004)
            if score < best_error:
                best_error = score
                best_parts = p.copy()

    if best_parts is None:
        best_parts = np.ones(k, dtype=int)

    # Simplify by GCD if any common divisor exists
    part_list = best_parts.tolist()
    gcd_val = reduce(math.gcd, part_list) if len(part_list) > 1 else 1
    simplified = [int(x // gcd_val) for x in best_parts]

    return {c: simplified[i] for i, c in enumerate(active_colors)}


def calculate_ratio(target_rgb):
    """Finds optimal convex mixture weights and returns practical integer ratio + percentage info."""
    target = np.array(target_rgb, dtype=int)

    # 1. Check exact base color match
    for name, rgb in PALETTE.items():
        if np.array_equal(target, rgb):
            ratio_dict = {name: 1}
            pct_dict = {name: 100}
            ratio_info = {
                'parts': ratio_dict,
                'parts_str': f'{name}: 1 part',
                'pct_str': f'{name}: 100%',
                'percentages': pct_dict,
                'total_parts': 1,
                'recipe': f'1 part {name}'
            }
            return ratio_dict, ratio_info, pct_dict

    # 2. Convex mixture optimization over 1, 2, or 3 pigments
    target_float = target.astype(float)
    best_weights = None
    best_names = None
    best_cost = float('inf')

    for k in [1, 2, 3]:
        for sub in itertools.combinations(color_names, k):
            sub_vecs = np.array([PALETTE[n] for n in sub], dtype=float).T

            def obj(w):
                diff = sub_vecs @ w - target_float
                return np.sum(diff**2)

            bounds = [(0.0, 1.0)] * k
            cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
            x0 = np.full(k, 1.0 / k)
            res = minimize(obj, x0, method='SLSQP', bounds=bounds, constraints=cons)

            if res.success:
                err = res.fun
                cost = err + (k * 0.25)
                if cost < best_cost:
                    best_cost = cost
                    best_weights = res.x
                    best_names = sub

    if best_weights is None:
        best_names = ('Green',)
        best_weights = np.array([1.0])

    # Compute clean integer percentages totaling 100%
    raw_pcts = [float(w * 100) for w in best_weights]
    int_pcts = [int(round(p)) for p in raw_pcts]
    diff = 100 - sum(int_pcts)
    if diff != 0:
        max_i = int(np.argmax(raw_pcts))
        int_pcts[max_i] += diff

    pct_dict = {name: pct for name, pct in zip(best_names, int_pcts) if pct > 0}
    weights_dict = {name: float(w) for name, w in zip(best_names, best_weights)}

    # Compute practical small integer parts (e.g. 1 : 3 : 6 for total 10 parts)
    practical_parts = compute_practical_parts(weights_dict, max_total_parts=12)
    total_parts = sum(practical_parts.values())

    # Build human-friendly recipe string
    recipe_parts = [f"{v} part{'s' if v > 1 else ''} {k}" for k, v in practical_parts.items()]
    recipe_str = " + ".join(recipe_parts)
    parts_str = ", ".join([f"{k}: {v}" for k, v in practical_parts.items()])
    pct_str = ", ".join([f"{k}: {v}%" for k, v in pct_dict.items()])

    # Compute normalized base-1 ratio (e.g. 1 : 2.5 : 5.5)
    min_part = min(practical_parts.values()) if practical_parts else 1
    normalized_parts = {k: round(v / min_part, 1) for k, v in practical_parts.items()}

    ratio_info = {
        'parts': practical_parts,
        'parts_str': parts_str,
        'pct_str': pct_str,
        'percentages': pct_dict,
        'total_parts': total_parts,
        'recipe': recipe_str,
        'normalized_parts': normalized_parts
    }
    return practical_parts, ratio_info, pct_dict


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json or {}
    user_input = data.get('color', '').strip()

    if not user_input:
        return jsonify({"error": "No color input provided."}), 400

    hex_code = user_input

    # If input is not a hex code (e.g. "black" or "parrot green"), resolve name to Hex.
    if not user_input.startswith('#'):
        found_hex = resolve_color_hex(user_input)
        if found_hex:
            hex_code = found_hex
        else:
            return jsonify({"error": f"Could not map color name '{user_input}' to a Hex code."}), 400

    # Convert Hex to RGB
    clean_hex = hex_code.lstrip('#')
    try:
        target_rgb = np.array([int(clean_hex[i:i+2], 16) for i in (0, 2, 4)])

        # If user explicitly entered a base color name, return only that base color.
        norm_input = normalize_name(user_input)
        if norm_input in BASE_COLORS:
            base_name = BASE_COLORS[norm_input][0]
            ratio_dict = {base_name: 1}
            pct_dict = {base_name: 100}
            ratio_info = {
                'parts': ratio_dict,
                'parts_str': f'{base_name}: 1 part',
                'pct_str': f'{base_name}: 100%',
                'percentages': pct_dict,
                'total_parts': 1,
                'recipe': f'1 part {base_name}',
                'normalized_parts': {base_name: 1.0}
            }
        else:
            ratio_dict, ratio_info, pct_dict = calculate_ratio(target_rgb)

        return jsonify({
            "input": user_input,
            "hex": f"#{clean_hex}",
            "rgb": [int(target_rgb[0]), int(target_rgb[1]), int(target_rgb[2])],
            "ratio": ratio_dict,
            "percentages": pct_dict,
            "ratio_info": ratio_info
        }), 200
    except Exception as e:
        return jsonify({"error": f"Processing error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)

