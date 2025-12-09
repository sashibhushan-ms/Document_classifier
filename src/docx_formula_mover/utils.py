import os
import shutil
import json
import csv

def ensure_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def move_file(src_path, dest_folder, dry_run=False):
    """
    Copies file to dest_folder.
    If dry_run is True, detects where it WOULD go but doesn't copy.
    Returns the destination path.
    """
    filename = os.path.basename(src_path)
    dest_path = os.path.join(dest_folder, filename)
    
    if not dry_run:
        ensure_directory(dest_folder)
        # Handle collision? Overwrite?
        # Requirement doesn't specify. Standard mv overwrites or fails.
        # Python shutil.copy2 overwrites if dest is file.
        shutil.copy2(src_path, dest_path)
        
    return dest_path

def generate_reports(scan_results, output_root):
    """
    Generates report.json and report.csv in output_root.
    scan_results is a list of ScanResult objects + metadata about where they moved.
    Shape of info needed:
    {
        "input_path": str,
        "output_path": str,
        "label": "formula_error" | "no_error" | "skipped",
        "matches": list,
        "skipped": bool
    }
    """
    ensure_directory(output_root)
    
    report_data = []
    
    for item in scan_results:
        report_data.append({
            "input_path": item["input_path"],
            "output_path": item["output_path"],
            "label": item["label"],
            "matches": item["matches"],
            "skipped": item["skipped"]
        })
        
    # JSON
    json_path = os.path.join(output_root, "report.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2)
        
    # CSV
    csv_path = os.path.join(output_root, "report.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header
        writer.writerow(["input_path", "output_path", "label", "skipped", "match_count"])
        for item in report_data:
            writer.writerow([
                item["input_path"],
                item["output_path"],
                item["label"],
                item["skipped"],
                len(item["matches"])
            ])
            
    print(f"Reports generated at {output_root}")
