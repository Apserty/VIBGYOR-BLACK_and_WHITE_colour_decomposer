# VIBGYOR-BLACK_and_WHITE_colour_decomposer
VIBGYOR Color Decomposer is a Flask-powered web application that takes any color (by everyday name, modifier, or hex code) and solves a convex optimization problem (SLSQP) to determine the exact mixing ratio of 9 base pigments (VIBGYOR + Black &amp; White) needed to recreate the target shade.


# VIBGYOR Color Decomposer

A Flask-based web application that breaks down any given color (by name or hex code) into a mixing ratio of 9 base palette colors (Violet, Indigo, Blue, Green, Yellow, Orange, Red, Black, and White).

It solves a constrained mathematical optimization problem to figure out which base pigments to mix and in what proportions to recreate the target shade.

---

## Features

- **Multiple Input Types**: Accepts everyday color names (e.g., `parrot green`, `navy blue`, `crimson`), modifier combinations (e.g., `dark red`, `light blue`), raw hex codes (`#32CD32`), or selections from an HTML5 color picker.
- **Lexicon & Fallback Matching**:
  - Direct exact matching against standard CSS / web colors.
  - Large expanded color dictionary combining curated everyday names, matplotlib CSS4 palettes, and XKCD colors.
  - Modifier parsing for lightness and saturation adjustments (`dark`, `light`, `pale`, `bright`, `vivid`, `deep`, `soft`).
  - Fuzzy string matching for typo tolerance.
  - External Color Pizza API fallback for uncommon names.
- **Mathematical Optimization (SLSQP)**: Uses `scipy.optimize.minimize` with Sequential Least Squares Programming to find the best convex combination of 1, 2, or 3 pigments that minimizes squared RGB error while keeping recipes simple.
- **Clean Visual Output**: Displays target color preview, computed integer ratio parts, percentage breakdown, and a segmented visual proportion bar.

---

## How It Works

1. **Input Parsing & Hex Resolution (`resolve_color_hex`)**:
   When you enter a string like `parrot green` or `#ff5733`:
   - If it's a hex code, it extracts and sanitizes it.
   - If it's a base color name, it directly maps to that base color.
   - For other names, it checks the built-in dictionary, parses modifiers, performs fuzzy matching, or queries the color API as a fallback.

2. **RGB Conversion**:
   The resolved hex code is split into standard red, green, and blue integer channels ($0-255$).

3. **Convex Mixture Optimization (`calculate_ratio`)**:
   The 9 base palette colors are represented as 3D RGB vectors:
   - Violet: `(148, 0, 211)`
   - Indigo: `(75, 0, 130)`
   - Blue: `(0, 0, 255)`
   - Green: `(0, 255, 0)`
   - Yellow: `(255, 255, 0)`
   - Orange: `(255, 127, 0)`
   - Red: `(255, 0, 0)`
   - Black: `(0, 0, 0)`
   - White: `(255, 255, 255)`

   The engine iterates through all 1, 2, and 3-color combinations from the palette. For each combination, it solves:
   $$\min_{w} \sum (C_{mix} - C_{target})^2 \quad \text{subject to} \quad \sum w_i = 1, \; w_i \ge 0$$
   A penalty term for higher pigment counts is applied so that simpler mixtures are favored when accuracy is comparable.

4. **Ratio Simplification**:
   Weights are converted into integer percentages that sum to 100%, and simplified into integer parts using the Greatest Common Divisor (GCD).

---

## Project Structure

```text
Color/
├── app.py              # Main Flask backend and optimization logic
├── requirement.txt     # Python dependencies
├── templates/
│   └── index.html      # Frontend user interface
├── .env                # Environment variables (optional)
└── README.md           # Project documentation
```

---

## Setup & Installation

### 1. Prerequisites
Make sure you have Python 3.8 or higher installed on your system.

### 2. Set Up Virtual Environment (Recommended)
Open your terminal inside the `day3-color` directory:

```bash
# On Windows (PowerShell / Command Prompt)
python -m venv .venv
.venv\Scripts\activate

# On macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
Install all required libraries from `requirement.txt`:

```bash
pip install -r requirement.txt
```

*(Key packages installed: `Flask`, `numpy`, `scipy`, `requests`, `python-dotenv`, `webcolors`, `matplotlib`)*

---

## How to Run

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

3. Enter a color name (e.g., `sky blue`, `forest green`, `charcoal`), type a hex code (e.g., `#E0115F`), or pick a color using the color box.
4. Click **Analyze** to view the breakdown and mixing ratio.

---

## API Reference

### `POST /analyze`

Accepts a JSON payload with a color string and returns the resolved hex, parts ratio, and percentages.

**Request:**
```json
{
  "color": "parrot green"
}
```

**Response:**
```json
{
  "input": "parrot green",
  "hex": "#32CD32",
  "ratio": {
    "Green": 4,
    "Yellow": 1
  },
  "ratio_info": {
    "parts": {
      "Green": 4,
      "Yellow": 1
    },
    "parts_str": "Green: 4, Yellow: 1",
    "pct_str": "Green: 80%, Yellow: 20%"
  }
}
```
