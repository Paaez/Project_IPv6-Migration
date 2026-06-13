import json
import os
import re
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Cloud-compatible path - uses 'data' folder in same directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Also check the original Project Directory path
ORIGINAL_PROJECT_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project\Project Directory"

# Use data folder if it exists, otherwise use original path
if os.path.exists(DATA_DIR) and os.listdir(DATA_DIR):
    PROJECT_DIR = DATA_DIR
    print(f"📁 Using data directory: {PROJECT_DIR}")
else:
    PROJECT_DIR = ORIGINAL_PROJECT_DIR
    print(f"📁 Using original project directory: {PROJECT_DIR}")

JSON_FILES = {
    "test1": os.path.join(PROJECT_DIR, "T1Rs.json"),
    "test2": os.path.join(PROJECT_DIR, "T2Rs.json"),
    "test3": os.path.join(PROJECT_DIR, "T3Rs.json"),
    "test5": os.path.join(PROJECT_DIR, "T5Rs.json")
}

def find_file(filename):
    """Try to find a file in multiple locations"""
    paths = [
        os.path.join(PROJECT_DIR, filename),
        os.path.join(ORIGINAL_PROJECT_DIR, filename),
        os.path.join(DATA_DIR, filename),
        os.path.join(BASE_DIR, filename),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return paths[0]  # Return first path as default

def load_json_file(filepath):
    print(f"Attempting to load: {filepath}")
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        try:
            data = json.loads(content)
            print(f"✅ Loaded {len(data)} entries from {os.path.basename(filepath)}")
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
            print(f"✅ Recovered {len(data)} entries from {os.path.basename(filepath)}")
            return data if data else None
    except Exception as e:
        print(f"❌ Error loading {filepath}: {e}")
        return None

def process_test_data(raw_data):
    if not raw_data: return {}
    aggregation = {}
    for entry in raw_data:
        try:
            m = entry.get('metric')
            s = entry.get('strategy')
            v = entry.get('value')
            if not m or not s or v is None: continue
            v = float(v) if not isinstance(v, (int, float)) else v
            if m not in aggregation: aggregation[m] = {}
            if s not in aggregation[m]: aggregation[m][s] = []
            aggregation[m][s].append(v)
        except (ValueError, TypeError):
            continue
    results = {}
    for metric, strategies in aggregation.items():
        results[metric] = {}
        for strategy, values in strategies.items():
            if len(values) > 0:
                results[metric][strategy] = sum(values) / len(values)
    return results

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/test1')
def test1_page(): 
    return render_template('test1.html')

@app.route('/test2')
def test2_page(): 
    return render_template('test2.html')

@app.route('/test3')
def test3_page(): 
    return render_template('test3.html')

@app.route('/test5')
def test5_page(): 
    return render_template('test5.html')

@app.route('/summary')
def summary_page(): 
    return render_template('summary.html')

# API Routes
@app.route('/api/test1')
def api_test1():
    data = process_test_data(load_json_file(JSON_FILES["test1"]))
    return jsonify(data) if data else (jsonify({"error": "No data found for Test 1"}), 404)

@app.route('/api/test2')
def api_test2():
    data = process_test_data(load_json_file(JSON_FILES["test2"]))
    return jsonify(data) if data else (jsonify({"error": "No data found for Test 2"}), 404)

@app.route('/api/test3')
def api_test3():
    data = process_test_data(load_json_file(JSON_FILES["test3"]))
    return jsonify(data) if data else (jsonify({"error": "No data found for Test 3"}), 404)

@app.route('/api/test5')
def api_test5():
    data = process_test_data(load_json_file(JSON_FILES["test5"]))
    return jsonify(data) if data else (jsonify({"error": "No data found for Test 5"}), 404)

@app.route('/api/drop-analysis/<strategy>')
def api_drop_analysis(strategy):
    """API endpoint for drop analysis data from TEST 2"""
    filename = f"T2_drop_analysis_{strategy}.json"
    drop_file = find_file(filename)
    
    print(f"🔍 Looking for drop analysis: {filename}")
    print(f"   Trying path: {drop_file}")
    print(f"   Exists: {os.path.exists(drop_file)}")
    
    if not os.path.exists(drop_file):
        # List files in directories for debugging
        for d in [PROJECT_DIR, ORIGINAL_PROJECT_DIR, DATA_DIR, BASE_DIR]:
            if os.path.exists(d):
                files = [f for f in os.listdir(d) if 'drop' in f.lower()]
                if files:
                    print(f"   Found in {d}: {files}")
        
        return jsonify({
            "error": f"No drop analysis for {strategy}", 
            "path": drop_file,
            "checked_dirs": [PROJECT_DIR, ORIGINAL_PROJECT_DIR, DATA_DIR]
        }), 404
    
    try:
        with open(drop_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ Loaded drop analysis for {strategy}")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/debug5')
def debug5():
    """Debug endpoint for TEST 5 data"""
    raw_data = load_json_file(JSON_FILES["test5"])
    if not raw_data:
        return jsonify({"error": "No data found"})
    
    p1_sizes = set()
    p2_sizes = set()
    strategies_count_p1 = {}
    strategies_count_p2 = {}
    
    for entry in raw_data:
        metric = entry.get('metric', '')
        strategy = entry.get('strategy', '?')
        
        if 'T5_P1_Frag_' in metric:
            match = re.search(r'T5_P1_Frag_(\d+)B_', metric)
            if match:
                p1_sizes.add(int(match.group(1)))
            strategies_count_p1[strategy] = strategies_count_p1.get(strategy, 0) + 1
                
        elif 'T5_P2_Frag_' in metric:
            match = re.search(r'T5_P2_Frag_(\d+)B_', metric)
            if match:
                p2_sizes.add(int(match.group(1)))
            strategies_count_p2[strategy] = strategies_count_p2.get(strategy, 0) + 1
    
    return jsonify({
        "total_entries": len(raw_data),
        "phase1": {"sizes": sorted(list(p1_sizes)), "num_sizes": len(p1_sizes), "entries_per_strategy": strategies_count_p1},
        "phase2": {"sizes": sorted(list(p2_sizes)), "num_sizes": len(p2_sizes), "entries_per_strategy": strategies_count_p2}
    })

@app.route('/health')
def health_check():
    """Health check endpoint to verify data files"""
    file_status = {}
    for name, path in JSON_FILES.items():
        file_status[name] = {
            "exists": os.path.exists(path),
            "path": path,
            "size": os.path.getsize(path) if os.path.exists(path) else 0
        }
    
    drop_files = {}
    for strategy in ['dualstack', 'dslite', 'nat64']:
        filename = f"T2_drop_analysis_{strategy}.json"
        drop_path = find_file(filename)
        drop_files[strategy] = {
            "exists": os.path.exists(drop_path),
            "path": drop_path,
            "size": os.path.getsize(drop_path) if os.path.exists(drop_path) else 0
        }
    
    return jsonify({
        "status": "healthy",
        "data_directory": PROJECT_DIR,
        "original_directory": ORIGINAL_PROJECT_DIR,
        "test_files": file_status,
        "drop_analysis_files": drop_files
    })

# ─────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────

if __name__ == '__main__':
    if not os.path.exists(PROJECT_DIR):
        os.makedirs(PROJECT_DIR)
        print(f"📁 Created data directory: {PROJECT_DIR}")
    
    templates_dir = os.path.join(BASE_DIR, 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print("📁 Created 'templates' folder.")

    print("="*60)
    print("🚀 IPv6 Migration Dashboard Server")
    print("="*60)
    print(f"📁 Data Directory: {PROJECT_DIR}")
    print(f"📁 Original Dir:   {ORIGINAL_PROJECT_DIR}")
    
    for test_name, filepath in JSON_FILES.items():
        exists = "✅" if os.path.exists(filepath) else "❌"
        size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        print(f"   {exists} {test_name.upper()}: {os.path.basename(filepath)} ({size:,} bytes)")
    
    port = int(os.environ.get('PORT', 5000))
    
    print(f"\n📊 Dashboard: http://0.0.0.0:{port}")
    print(f"📋 Summary:  http://0.0.0.0:{port}/summary")
    print(f"🔍 Debug T5: http://0.0.0.0:{port}/debug5")
    print(f"💚 Health:   http://0.0.0.0:{port}/health")
    print("="*60)
    
    app.run(host='0.0.0.0', port=port, debug=False)