import json
import os
import argparse
import sys


PROJECTS = [
    "assertj_assertj-core",
    "checkstyle_checkstyle",
    "FasterXML_jackson-databind",
    "google_gson",
    "Hakky54_sslcontext-kickstart",
    "jhy_jsoup"
]


def load_json(filepath):
    """Safely loads a JSON file."""
    if not os.path.exists(filepath):
        print(f"File {filepath} not found")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"File {filepath} is not valid JSON")
        return None


def normalize_project_key(key):
    """
    Adapts project keys to the GHRB paper format.
    Converts e.g. 'FasterXML_jackson-databind_3418' to 'FasterXML_jackson-databind-3418'
    (Changes the last underscore before the ID to a hyphen).
    """
    if '_' in key:
        parts = key.rsplit('_', 1)
        if len(parts) == 2 and parts[1].isdigit():
            return f"{parts[0]}-{parts[1]}"
    return key


def transform_entry(entry_data):
    """
    Transforms a single test entry into the flat GHRB format.
    Extracts 'testclass' and sets it as 'injected_test'.
    """
    if isinstance(entry_data, str):
        return entry_data

    if isinstance(entry_data, dict):
        new_entry = {}
        
        new_entry['success'] = entry_data.get('success', False)
        new_entry['fixed'] = entry_data.get('fixed', None)

        old_buggy = entry_data.get('buggy', {})
        if old_buggy:
            new_buggy = old_buggy.copy()
            
            if 'testclass' in new_buggy:
                testclass_data = new_buggy['testclass']
                if isinstance(testclass_data, list) and len(testclass_data) > 0:
                    new_entry['injected_test'] = testclass_data[0]
                
                del new_buggy['testclass']
            
            if 'injected_test' in entry_data:
                new_entry['injected_test'] = entry_data['injected_test']

            new_entry['buggy'] = new_buggy
        
        return new_entry

    return entry_data


def main():
    # CLI argument parsing
    parser = argparse.ArgumentParser(description="Merges and normalizes GHRB experiment JSON files.")
    
    parser.add_argument("--prefix", required=True, 
                        help="The experiment prefix (e.g., 'basic', 'exp1', 'exp4_bereinigt').")
    
    parser.add_argument("--input_dir", default=".", 
                        help="Directory containing the input JSON files (Default: current directory).")
    
    parser.add_argument("--output_dir", default=".", 
                        help="Directory where the merged JSON will be saved (Default: current directory).")

    args = parser.parse_args()

    merged_data = {}
    
    print(f"Starting Merge for Experiment: '{args.prefix}'")
    print(f"Input Dir:  {args.input_dir}")
    print(f"Output Dir: {args.output_dir}")
    print("-" * 50)

    files_processed = 0

    for project_suffix in PROJECTS:
        filename = f"{args.prefix}_{project_suffix}.json"
        filepath = os.path.join(args.input_dir, filename)
        
        print(f"Processing: {filename}")
        data = load_json(filepath)
        
        if data:
            files_processed += 1
            for raw_key, test_cases in data.items():
                normalized_key = normalize_project_key(raw_key)
                
                transformed_cases = {}
                
                if isinstance(test_cases, dict):
                    for test_name, test_data in test_cases.items():
                        transformed_cases[test_name] = transform_entry(test_data)
                    
                    merged_data[normalized_key] = transformed_cases
                else:
                    merged_data[normalized_key] = test_cases

    print("-" * 50)
    
    if files_processed == 0:
        sys.exit(1)

    # Create output filename
    output_filename = f"{args.prefix}_GHRB.json"
    output_path = os.path.join(args.output_dir, output_filename)
    
    print(f"Saving result to: {output_path}")
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, indent=2)
        print(f"{files_processed} files were merged successfully")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    main()