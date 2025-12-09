import os
import json
import flask
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import webbrowser

# Initialize Flask app
# Initialize Flask app
app = Flask(__name__)
# Configure limits immediately
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024 # 4 GB
app.config['DATA_UPLOAD_MAX_NUMBER_FILES'] = 100000 # Unlimited logic might be flaky?
app.config['DATA_UPLOAD_MAX_NUMBER_FIELDS'] = 100000 # Unlimited logic might be flaky?
print(f"DEBUG STARTUP: MAX_CONTENT_LENGTH={app.config['MAX_CONTENT_LENGTH']}")
print(f"DEBUG STARTUP: DATA_UPLOAD_MAX_NUMBER_FILES={app.config['DATA_UPLOAD_MAX_NUMBER_FILES']}")


CORS(app) # Enable CORS for development (Vite runs on 5173, Flask on 5000)

# Configuration
# output root where report.json lives. 
# Based on previous context: d:/thinksolv/tast1_fr/manual_output
OUTPUT_ROOT = os.path.abspath(r"D:\thinksolv\tast1_fr\manual_output")
REPORT_PATH = os.path.join(OUTPUT_ROOT, "report.json")

import sys
# Add src directory to path so we can import docx_formula_mover as a package
# Current file is in d:/thinksolv/tast1_fr/src/server.py
# We want to import from d:/thinksolv/tast1_fr/src/docx_formula_mover
# So we add d:/thinksolv/tast1_fr/src to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import shutil
# Import directly from the package
from docx_formula_mover.scanner import DocxScanner
from docx_formula_mover.utils import generate_reports

@app.route('/api/report', methods=['GET'])
def get_report():
    if not os.path.exists(REPORT_PATH):
        # Return empty list instead of 404 if no report yet, or specific status
        return jsonify([]) 
        
    try:
        with open(REPORT_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# State for async processing
SCAN_STATE = {
    "status": "idle", # idle, processing, completed, error
    "progress": 0,
    "total": 0,
    "message": ""
}
SCAN_LOCK = threading.Lock()

def update_state(status, progress=0, total=0, message=""):
    with SCAN_LOCK:
        SCAN_STATE["status"] = status
        SCAN_STATE["progress"] = progress
        if total > 0: SCAN_STATE["total"] = total
        SCAN_STATE["message"] = message

def run_scan_async(scan_files, error_dir, no_error_dir):
    try:
        scanner = DocxScanner()
        scan_results = []
        
        # Import move_file from utils
        from docx_formula_mover.utils import move_file

        total = len(scan_files)
        update_state("processing", 0, total, "Scanning...")

        for i, file_path in enumerate(scan_files):
            # Update progress every file? Or every N?
            update_state("processing", i, total, f"Scanning {i+1}/{total}")
            
            try:
                result = scanner.scan_file(file_path)
                # result is a ScanResult object, not a dict
                dest_folder = error_dir if result.is_error else no_error_dir
                
                output_path = ""
                if not result.skipped:
                    output_path = move_file(file_path, dest_folder, dry_run=False)
                else:
                    output_path = file_path 
                    
                scan_results.append({
                    "input_path": file_path,
                    "output_path": output_path,
                    "label": "formula_error" if result.is_error else ("skipped" if result.skipped else "no_error"),
                    "matches": result.matches,
                    "skipped": result.skipped
                })
            except Exception as e:
                print(f"Error scanning {file_path}: {e}")
                # We should probably record error but continue?
                # For now just continue
                pass

        generate_reports(scan_results, OUTPUT_ROOT)
        update_state("completed", total, total, "Done")
        
    except Exception as e:
        print(f"Scan failed: {e}")
        update_state("error", 0, 0, str(e))

@app.route('/api/status', methods=['GET'])
def get_status():
    with SCAN_LOCK:
        return jsonify(SCAN_STATE)

@app.route('/api/session/start', methods=['POST'])
def start_session():
    # Clear temp uploads for new session
    print("DEBUG: Session Start - Clearing temp_uploads")
    temp_dir = os.path.join(OUTPUT_ROOT, "temp_uploads")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    return jsonify({"message": "Session started"})

@app.route('/api/upload_chunk', methods=['POST'])
def upload_chunk():
    try:
        files = request.files.getlist("files")
        print(f"DEBUG: Chunk Received - {len(files)} files")
        temp_dir = os.path.join(OUTPUT_ROOT, "temp_uploads")
        if not os.path.exists(temp_dir):
             os.makedirs(temp_dir)
             
        saved_count = 0
        for file in files:
            if file.filename:
                # Use secure_filename if possible, but keep simple for now
                filename = file.filename
                save_path = os.path.join(temp_dir, filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                file.save(save_path)
                saved_count += 1
        print(f"DEBUG: Chunk Saved - {saved_count} files saved")
        return jsonify({"message": f"Chunk saved {saved_count} files", "count": saved_count})
    except Exception as e:
        print(f"Chunk upload error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/scan_start', methods=['POST'])
def start_scan():
    print("DEBUG: Scan Start Request Received")
    # Check if busy?
    with SCAN_LOCK:
        if SCAN_STATE["status"] == "processing":
            return jsonify({"error": "Scan in progress"}), 409

    temp_dir = os.path.join(OUTPUT_ROOT, "temp_uploads")
    if not os.path.exists(temp_dir):
        print("DEBUG: temp_uploads not found")
        return jsonify({"error": "No files found to scan"}), 400

    # Ensure dest folders exist
    error_dir = os.path.join(OUTPUT_ROOT, "formula_error")
    no_error_dir = os.path.join(OUTPUT_ROOT, "no_error")
    os.makedirs(error_dir, exist_ok=True)
    os.makedirs(no_error_dir, exist_ok=True)
            
    # Prepare file list for scanner
    scan_files = []
    for root, dirs, files_in_dir in os.walk(temp_dir):
        for name in files_in_dir:
            scan_files.append(os.path.join(root, name))
            
    print(f"DEBUG: Scan Start - Found {len(scan_files)} files in temp_uploads")
    
    # Spawn Thread
    thread = threading.Thread(target=run_scan_async, args=(scan_files, error_dir, no_error_dir))
    thread.start()
    
    return jsonify({"message": f"Scanning {len(scan_files)} files started.", "count": len(scan_files)})


# Deprecated legacy upload (kept for compatibility or removal)
@app.route('/api/upload', methods=['POST'])
def upload_file():
    # Only one upload route should exist. 
    # Use the one defined earlier.
    # We will DELETE this block if it was a duplicate, or RENAME it if we want to replace.
    # But wait, replace_file_content replaces the chunk.
    # The chunk I am replacing is lines 208-247.
    pass 




@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal Server Error", "details": str(error)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found", "details": str(error)}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, flask.HTTPException):
        return e
    return jsonify({"error": str(e)}), 500

@app.route('/api/download/<type>', methods=['GET'])
def download_zip(type):
    # type: 'error' or 'clean'
    if type == 'error':
        source_dir = os.path.join(OUTPUT_ROOT, "formula_error")
        filename = "formula_errors"
    elif type == 'clean':
        source_dir = os.path.join(OUTPUT_ROOT, "no_error")
        filename = "clean_files"
    else:
        return jsonify({"error": "Invalid type"}), 400
        
    if not os.path.exists(source_dir):
        os.makedirs(source_dir) # Ensure it exists so we return empty zip if needed? Or error?
        # Better to return empty zip or handle gracefully.
        
    # Create zip in memory or temp
    shutil.make_archive(os.path.join(OUTPUT_ROOT, filename), 'zip', source_dir)
    zip_path = os.path.join(OUTPUT_ROOT, f"{filename}.zip")
    
    try:
        return flask.send_file(zip_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_files():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    clear_type = data.get('type') # 'error' or 'clean'
    
    target_folder = ""
    if clear_type == 'error':
        target_folder = os.path.join(OUTPUT_ROOT, "formula_error")
    elif clear_type == 'clean':
        target_folder = os.path.join(OUTPUT_ROOT, "no_error")
    else:
        return jsonify({"error": "Invalid type. Use 'error' or 'clean'"}), 400
        
    if not os.path.exists(target_folder):
        return jsonify({"message": "Directory does not exist", "deleted": 0})
        
    try:
        deleted_count = 0
        for filename in os.listdir(target_folder):
            file_path = os.path.join(target_folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                deleted_count += 1
        return jsonify({"message": f"Cleared {clear_type} files", "deleted": deleted_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print(f"Serving report from: {REPORT_PATH}")
    app.run(port=5000, debug=True)
