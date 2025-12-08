import re
import os
import argparse
import sys
from typing import List


def extract_test_methods(file_content: str) -> List[str]:
    """
    Extracts Java methods (starting with @Test or public void) by parsing
    the source code and counting curly braces to find the method body.

    @param file_content: The full content of the Java file as a string.
    @return: A list of strings, where each string is a complete extracted Java method.
    """
    extracted_methods: List[str] = []

    # Regex looks for the start of a method (ignoring class/import statements before it)
    # Matches: optional @Test, then public void, method name, args, optional throws, starting brace
    method_start_pattern = re.compile(
        r'(@Test\s+)?public\s+void\s+[\w]+\s*\([^)]*\)\s*(throws\s+[\w,\s]+)?\s*\{',
        re.MULTILINE | re.DOTALL
    )

    for match in method_start_pattern.finditer(file_content):
        start_index: int = match.start()

        # Find first opening '{' after regex match
        brace_search = re.search(r'\{', file_content[start_index:])
        if not brace_search:
            continue

        current_idx: int = start_index + brace_search.start()

        # Brace Counting Logic to find matching closing brace
        open_braces: int = 0
        
        # Iterate through str character by character
        for i in range(current_idx, len(file_content)):
            char = file_content[i]
            if char == '{':
                open_braces += 1
            elif char == '}':
                open_braces -= 1

            if open_braces == 0:
                full_method = file_content[start_index:i + 1]
                extracted_methods.append(full_method.strip())
                break

    return extracted_methods


def main() -> None:
    """
    Main function to handle command line arguments and file processing.
    Reads raw text files, extracts Java methods, and saves them to a destination.
    
    @return: None
    """
    # CLI Argument parsing
    parser = argparse.ArgumentParser(description="Extracts the first Java test method from raw text files.")
    
    parser.add_argument("--source_dir", required=True, type=str,
                        help="Path to the directory containing the raw generated test files.")
    
    parser.add_argument("--dest_dir", required=True, type=str,
                        help="Path to the directory where cleaned files will be saved.")

    args = parser.parse_args()

    if not os.path.exists(args.source_dir):
        print(f"Error: Source directory {args.source_dir} not found")
        sys.exit(1)

    if not os.path.exists(args.dest_dir):
        try:
            os.makedirs(args.dest_dir)
            print(f"Created directory: {args.dest_dir}")
        except OSError as e:
            print(f"Error creating destination directory: {e}")
            sys.exit(1)
    else:
        print(f"Destination directory exists: {args.dest_dir}")

    try:
        files: List[str] = [f for f in os.listdir(args.source_dir) if f.endswith('.txt')]
    except OSError as e:
        print(f"Error reading source directory: {e}")
        sys.exit(1)

    print(f"Starting processing of {len(files)} files...\n")

    count_success: int = 0
    count_skipped: int = 0

    for filename in files:
        input_path: str = os.path.join(args.source_dir, filename)
        output_path: str = os.path.join(args.dest_dir, filename)

        try:
            with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
                content: str = f.read()

            methods: List[str] = extract_test_methods(content)

            if methods:
                clean_content: str = methods[0]

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(clean_content)
                
                count_success += 1
            else:
                count_skipped += 1
                print(f"[SKIP] No test method found in: {filename}")

        except Exception as e:
            print(f"Failed to process file {filename}: {e}")

    print(f"Successfully created: {count_success}")
    print(f"Skipped (empty/no test): {count_skipped}")
    print(f"Saved to: {os.path.abspath(args.dest_dir)}")

if __name__ == "__main__":
    main()