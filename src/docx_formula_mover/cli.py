import argparse
import os
import sys
from .scanner import DocxScanner
from . import utils

def main():
    parser = argparse.ArgumentParser(description="docx-formula-mover: Scan and move docx files based on $$ matching.")
    
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    scan_parser = subparsers.add_parser('scan', help='Scan a file or directory')
    scan_parser.add_argument('input_path', help='Input file or directory path')
    scan_parser.add_argument('--out', required=True, help='Output root directory')
    scan_parser.add_argument('--recursive', action=argparse.BooleanOptionalAction, default=True, help='Recursively scan directories')
    scan_parser.add_argument('--dry-run', action='store_true', help='Do not move files, just report')
    scan_parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.command == 'scan':
        run_scan(args)

def run_scan(args):
    input_path = os.path.abspath(args.input_path)
    output_root = os.path.abspath(args.out)
    recursive = args.recursive
    dry_run = args.dry_run
    verbose = args.verbose
    
    if verbose:
        print(f"Scanning: {input_path}")
        print(f"Output to: {output_root}")
        print(f"Recursive: {recursive}")
        print(f"Dry run: {dry_run}")

    scanner = DocxScanner()
    files_to_process = []

    if os.path.isfile(input_path):
        files_to_process.append(input_path)
    elif os.path.isdir(input_path):
        if recursive:
            for root, dirs, files in os.walk(input_path):
                for f in files:
                    if f.lower().endswith('.docx'):
                        files_to_process.append(os.path.join(root, f))
        else:
             for f in os.listdir(input_path):
                 if f.lower().endswith('.docx'):
                     files_to_process.append(os.path.join(input_path, f))
    else:
        print(f"Error: Path not found: {input_path}")
        sys.exit(1)

    results_info = []
    
    ensure_dirs = set()
    
    for file_path in files_to_process:
        if verbose:
            print(f"Processing: {file_path}")
            
        result = scanner.scan_file(file_path)
        
        # Classification
        if result.skipped:
            label = "skipped"
            dest_folder = None
        elif result.is_error:
            label = "formula_error"
            dest_folder = os.path.join(output_root, "formula_error")
        else:
            label = "no_error"
            dest_folder = os.path.join(output_root, "no_error")
            
        # Move logic
        output_path = ""
        if dest_folder:
            # If dry run, show where it would go
            output_path = utils.move_file(file_path, dest_folder, dry_run=dry_run)
            
            if verbose:
                print(f"  -> Detected: {label}")
                if dry_run:
                    print(f"  -> Would move to: {output_path}")
                else:
                    print(f"  -> Moved to: {output_path}")
            
        results_info.append({
            "input_path": file_path,
            "output_path": output_path,
            "label": label,
            "matches": [m for m in result.matches], # Ensure serializable
            "skipped": result.skipped
        })

    # Generate report
    utils.generate_reports(results_info, output_root)
    print("Done.")

if __name__ == "__main__":
    main()
