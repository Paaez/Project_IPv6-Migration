import json
import os
import re
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROJECT_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project\Project Directory"

def detect_data_dir():
    if os.path.exists(DATA_DIR) and any(f.endswith('.json') for f in os.listdir(DATA_DIR)):
        return DATA_DIR
    if os.path.exists(PROJECT_DIR) and any(f.endswith('.json') for f in os.listdir(PROJECT_DIR)):
        return PROJECT_DIR
    return PROJECT_DIR

WORK_DIR = detect_data_dir()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def read_json(path):
    """Read and parse a JSON file with recovery for broken files"""
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        try:
            data = json.loads(content)
            print(f"✅ Loaded {len(data)} entries from {os.path.basename(path)}")
            return data
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON error at line {e.lineno}, attempting recovery...")
            data = []
            lines = content.split('\n')
            current_obj = ""
            brace_count = 0
            in_object = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('{'):
                    if not in_object:
                        in_object = True
                        brace_count = 0
                        current_obj = ""
                if in_object:
                    current_obj += line + '\n'
                    brace_count += stripped.count('{') - stripped.count('}')
                    if brace_count == 0 and current_obj.strip():
                        try:
                            obj = json.loads(current_obj.strip().rstrip(','))
                            data.append(obj)
                        except json.JSONDecodeError:
                            pass
                        current_obj = ""
                        in_object = False
            print(f"✅ Recovered {len(data)} entries from {os.path.basename(path)}")
            return data if data else None
    except Exception as e:
        print(f"❌ Error loading {path}: {e}")
        return None

def process_data(raw_data):
    """Average metric values by strategy"""
    if not raw_data: return {}
    agg = {}
    for entry in raw_data:
        try:
            m = entry.get('metric', '')
            s = entry.get('strategy', '')
            v = entry.get('value', 0)
            if not m or not s: continue
            v = float(v) if not isinstance(v, (int, float)) else v
            agg.setdefault(m, {}).setdefault(s, []).append(v)
        except (ValueError, TypeError):
            continue
    
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
# PAGE ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/overview')
def overview_page(): return render_template('overview.html')

@app.route('/test1')
def test1_page(): return render_template('test1.html')

@app.route('/test2')
def test2_page(): return render_template('test2.html')

@app.route('/test3')
def test3_page(): return render_template('test3.html')

@app.route('/test5')
def test5_page(): return render_template('test5.html')

@app.route('/summary')
def summary_page(): return render_template('summary.html')

@app.route('/analysis')
def analysis_page(): return render_template('analysis.html')

# ─────────────────────────────────────────────
# API ROUTES - Averaged Data
# ─────────────────────────────────────────────

@app.route('/api/test1')
def api_test1():
    path = find_file("T1Rs.json")
    if not path: return jsonify({"error": "T1Rs.json not found"}), 404
    data = process_data(read_json(path))
    return jsonify(data) if data else (jsonify({"error": "No data"}), 404)

@app.route('/api/test2')
def api_test2():
    path = find_file("T2Rs.json")
    if not path: return jsonify({"error": "T2Rs.json not found"}), 404
    data = process_data(read_json(path))
    return jsonify(data) if data else (jsonify({"error": "No data"}), 404)

@app.route('/api/test3')
def api_test3():
    path = find_file("T3Rs.json")
    if not path: return jsonify({"error": "T3Rs.json not found"}), 404
    data = process_data(read_json(path))
    return jsonify(data) if data else (jsonify({"error": "No data"}), 404)

@app.route('/api/test5')
def api_test5():
    path = find_file("T5Rs.json")
    if not path: return jsonify({"error": "T5Rs.json not found"}), 404
    data = process_data(read_json(path))
    return jsonify(data) if data else (jsonify({"error": "No data"}), 404)

# ─────────────────────────────────────────────
# API ROUTES - Raw Data (preserves runs)
# ─────────────────────────────────────────────

@app.route('/api/test1-raw')
def api_test1_raw():
    path = find_file("T1Rs.json")
    if not path: return jsonify({"error": "T1Rs.json not found"}), 404
    data = read_json(path)
    return jsonify(data) if data else (jsonify({"error": "No data"}), 404)

@app.route('/api/test2-raw')
def api_test2_raw():
    path = find_file("T2Rs.json")
    if not path: return jsonify({"error": "T2Rs.json not found"}), 404
    data = read_json(path)
    return jsonify(data) if data else (jsonify({"error": "No data"}), 404)

@app.route('/api/test3-raw')
def api_test3_raw():
    path = find_file("T3Rs.json")
    if not path: return jsonify({"error": "T3Rs.json not found"}), 404
    data = read_json(path)
    return jsonify(data) if data else (jsonify({"error": "No data"}), 404)

@app.route('/api/test5-raw')
def api_test5_raw():
    path = find_file("T5Rs.json")
    if not path: return jsonify({"error": "T5Rs.json not found"}), 404
    data = read_json(path)
    return jsonify(data) if data else (jsonify({"error": "No data"}), 404)

# ─────────────────────────────────────────────
# Drop Analysis API
# ─────────────────────────────────────────────

@app.route('/api/drop-analysis/<strategy>')
def api_drop_analysis(strategy):
    filename = f"T2_drop_analysis_{strategy}.json"
    path = find_file(filename)
    if not path:
        return jsonify({"error": f"{filename} not found"}), 404
    data = read_json(path)
    if data is None:
        return jsonify({"error": f"Could not read {filename}"}), 500
    return jsonify(data)

# ─────────────────────────────────────────────
# DEBUG & HEALTH
# ─────────────────────────────────────────────

@app.route('/debug5')
def debug5():
    raw_data = read_json(find_file("T5Rs.json"))
    if not raw_data: return jsonify({"error": "No data found"}), 404
    
    p1_sizes = set()
    p2_sizes = set()
    p1_strategies = {}
    p2_strategies = {}
    
    for entry in raw_data:
        metric = entry.get('metric', '')
        strategy = entry.get('strategy', '?')
        if 'T5_P1_Frag_' in metric:
            match = re.search(r'T5_P1_Frag_(\d+)B_', metric)
            if match: p1_sizes.add(int(match.group(1)))
            p1_strategies[strategy] = p1_strategies.get(strategy, 0) + 1
        elif 'T5_P2_Frag_' in metric:
            match = re.search(r'T5_P2_Frag_(\d+)B_', metric)
            if match: p2_sizes.add(int(match.group(1)))
            p2_strategies[strategy] = p2_strategies.get(strategy, 0) + 1
    
    return jsonify({
        "total_entries": len(raw_data),
        "phase1": {"sizes": sorted(list(p1_sizes)), "num_sizes": len(p1_sizes), "entries_per_strategy": p1_strategies},
        "phase2": {"sizes": sorted(list(p2_sizes)), "num_sizes": len(p2_sizes), "entries_per_strategy": p2_strategies}
    })

@app.route('/health')
def health():
    file_status = {}
    for name in ['T1Rs.json', 'T2Rs.json', 'T3Rs.json', 'T5Rs.json']:
        path = find_file(name)
        file_status[name] = {"found": path is not None, "path": path}
    
    drop_files = {}
    for s in ['dualstack', 'dslite', 'nat64']:
        path = find_file(f"T2_drop_analysis_{s}.json")
        drop_files[s] = {"found": path is not None, "path": path}
    
    return jsonify({
        "status": "healthy",
        "work_dir": WORK_DIR,
        "test_files": file_status,
        "drop_analysis_files": drop_files
    })

# ─────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────

if __name__ == '__main__':
    templates_dir = os.path.join(BASE_DIR, 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print("📁 Created 'templates' folder")
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print("📁 Created 'data' folder")

    print("=" * 60)
    print("🚀 IPv6 Migration Dashboard Server")
    print("=" * 60)
    print(f"📁 Working Directory: {WORK_DIR}")
    print()
    
    for name in ['T1Rs.json', 'T2Rs.json', 'T3Rs.json', 'T5Rs.json']:
        path = find_file(name)
        status = "✅" if path else "❌"
        size = f"({os.path.getsize(path):,} bytes)" if path else ""
        print(f"   {status} {name} {size}")
    
    port = int(os.environ.get('PORT', 5000))
    
    print(f"\n🌐 Dashboard: http://0.0.0.0:{port}")
    print(f"📋 Summary:   http://0.0.0.0:{port}/summary")
    print(f"📊 Analysis:  http://0.0.0.0:{port}/analysis")
    print(f"💚 Health:    http://0.0.0.0:{port}/health")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)