import json
import os
import re
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# ─────────────────────────────────────────────
# PATHS - CHANGE THESE IF NEEDED
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROJECT_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project\Project Directory"

# Auto-detect which directory has the JSON files
def detect_data_dir():
    if os.path.exists(DATA_DIR) and any(f.endswith('.json') for f in os.listdir(DATA_DIR)):
        return DATA_DIR
    if os.path.exists(PROJECT_DIR) and any(f.endswith('.json') for f in os.listdir(PROJECT_DIR)):
        return PROJECT_DIR
    return PROJECT_DIR  # default

WORK_DIR = detect_data_dir()
print(f"📁 Working directory: {WORK_DIR}")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def read_json(path):
    """Read and parse a JSON file"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Try to recover broken JSON
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        data = []
        for line in content.split('\n'):
            line = line.strip().rstrip(',')
            if line.startswith('{') and line.endswith('}'):
                try:
                    data.append(json.loads(line))
                except:
                    pass
        return data if data else None
    except:
        return None

def process_data(raw_data):
    """Average metric values by strategy"""
    if not raw_data: return {}
    agg = {}
    for entry in raw_data:
        m = entry.get('metric', '')
        s = entry.get('strategy', '')
        v = entry.get('value', 0)
        if not m or not s: continue
        try: v = float(v)
        except: continue
        agg.setdefault(m, {}).setdefault(s, []).append(v)
    
    result = {}
    for metric, strategies in agg.items():
        result[metric] = {}
        for strategy, values in strategies.items():
            if values:
                result[metric][strategy] = sum(values) / len(values)
    return result

def find_file(filename):
    """Search for a file in multiple locations"""
    paths = [
        os.path.join(WORK_DIR, filename),
        os.path.join(DATA_DIR, filename),
        os.path.join(PROJECT_DIR, filename),
        os.path.join(BASE_DIR, filename),
        os.path.join(BASE_DIR, "data", filename),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test1')
def test1(): return render_template('test1.html')

@app.route('/test2')
def test2(): return render_template('test2.html')

@app.route('/test3')
def test3(): return render_template('test3.html')

@app.route('/test5')
def test5(): return render_template('test5.html')

@app.route('/summary')
def summary(): return render_template('summary.html')

@app.route('/health')
def health():
    files_found = {}
    for name in ['T1Rs.json', 'T2Rs.json', 'T3Rs.json', 'T5Rs.json',
                 'T2_drop_analysis_dualstack.json', 'T2_drop_analysis_dslite.json', 'T2_drop_analysis_nat64.json']:
        path = find_file(name)
        files_found[name] = {"found": path is not None, "path": path}
    
    return jsonify({
        "status": "healthy",
        "work_dir": WORK_DIR,
        "files": files_found
    })

# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────

@app.route('/api/test1')
def api_test1():
    path = find_file("T1Rs.json")
    if not path: return jsonify({"error": "T1Rs.json not found"}), 404
    data = process_data(read_json(path))
    return jsonify(data)

@app.route('/api/test2')
def api_test2():
    path = find_file("T2Rs.json")
    if not path: return jsonify({"error": "T2Rs.json not found"}), 404
    data = process_data(read_json(path))
    return jsonify(data)

@app.route('/api/test3')
def api_test3():
    path = find_file("T3Rs.json")
    if not path: return jsonify({"error": "T3Rs.json not found"}), 404
    data = process_data(read_json(path))
    return jsonify(data)

@app.route('/api/test5')
def api_test5():
    path = find_file("T5Rs.json")
    if not path: return jsonify({"error": "T5Rs.json not found"}), 404
    data = process_data(read_json(path))
    return jsonify(data)

@app.route('/api/drop-analysis/<strategy>')
def api_drop_analysis(strategy):
    filename = f"T2_drop_analysis_{strategy}.json"
    path = find_file(filename)
    if not path:
        return jsonify({"error": f"{filename} not found", "searched_in": WORK_DIR}), 404
    data = read_json(path)
    if data is None:
        return jsonify({"error": f"Could not read {filename}"}), 500
    return jsonify(data)

# ─────────────────────────────────────────────
# START
# ─────────────────────────────────────────────

if __name__ == '__main__':
    # Ensure templates folder exists
    templates_dir = os.path.join(BASE_DIR, 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print("📁 Created templates folder")

    print("=" * 60)
    print("🚀 IPv6 Migration Dashboard")
    print("=" * 60)
    print(f"📁 Data: {WORK_DIR}")
    
    # Show found files
    for name in ['T1Rs.json', 'T2Rs.json', 'T3Rs.json', 'T5Rs.json']:
        path = find_file(name)
        status = "✅" if path else "❌"
        print(f"   {status} {name}: {path or 'NOT FOUND'}")

    port = int(os.environ.get('PORT', 5000))
    print(f"\n🌐 http://0.0.0.0:{port}")
    print(f"💚 http://0.0.0.0:{port}/health")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=False)