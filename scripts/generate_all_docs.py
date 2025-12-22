#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from pathlib import Path
from make_javadoc import create_bundle

# Configuration
REPOS_BASE_DIR = "repos"
OUTPUT_JSON_FILE = os.path.join(REPOS_BASE_DIR, "all_javadoc_bundles.json")
MAX_DOC_CHARS = 15000 
MAX_BLOCKS_PER_CLASS = 15
ALSO_EXTERNAL = True
VERBOSE = True
M2_REPO = str(Path.home() / ".m2" / "repository")

def find_representative_bugs(repos_dir):
    """Identify project types by finding folders ending in '_1'."""
    targets = []
    if not os.path.isdir(repos_dir):
        print(f"[ERROR] Directory not found: {repos_dir}")
        return []
        
    for item in sorted(os.listdir(repos_dir)):
        if os.path.isdir(os.path.join(repos_dir, item)) and item.endswith("_1"):
            targets.append(item)
            
    print(f"[INFO] Target bugs found: {targets}")
    return targets

def main():
    target_bugs = find_representative_bugs(REPOS_BASE_DIR)
    if not target_bugs:
        return

    all_documentation = {}

    for bug_name in target_bugs:
        workdir = os.path.join(REPOS_BASE_DIR, bug_name)
        print(f"\n--- Processing {bug_name} ---")
        
        # Extract Javadoc bundle for the current bug
        bundle_content = create_bundle(
            workdir=workdir,
            max_doc_chars=MAX_DOC_CHARS,
            max_blocks_per_class=MAX_BLOCKS_PER_CLASS,
            m2_repo=M2_REPO,
            also_external=ALSO_EXTERNAL,
            verbose=VERBOSE,
            bug_json=None
        )
        
        all_documentation[bug_name] = bundle_content
        print(f"--- Finished {bug_name}, Size: {len(bundle_content)} chars ---")

    # Save all results to a single JSON file
    try:
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_documentation, f, indent=2, ensure_ascii=False)
        print(f"\n[SUCCESS] Documentation saved to '{OUTPUT_JSON_FILE}'.")
    except Exception as e:
        print(f"\n[ERROR] Failed to save JSON: {e}")

if __name__ == "__main__":
    main()