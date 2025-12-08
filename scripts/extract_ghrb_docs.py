#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from pathlib import Path

REPOS_BASE_DIR = "repos"
OUTPUT_JSON_FILE = "ghrb_javadoc_bundles.json"
MAX_DOC_CHARS = 15000
MAX_BLOCKS_PER_CLASS = 20
VERBOSE = True


def log(msg):
    if VERBOSE:
        print(msg)

def read_text(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

def javadoc_blocks(java_txt):
    if not java_txt:
        return []

    pat = re.compile(r"/\*\*([\s\S]*?)\*/\s*(public|protected|private|class|interface|enum|@)", re.M)
    blocks = []
    for raw, _kw in pat.findall(java_txt):
        block = re.sub(r'^\s*\*\s?', '', raw, flags=re.M).strip()
        if block:
            blocks.append(block)
    return blocks

def collect_imports(src_dir):
    imports = set()
    for f in Path(src_dir).rglob("*.java"):
        t = read_text(f)
        if not t:
            continue
        for line in t.splitlines():
            line = line.strip()
            if line.startswith("import "):
                imp = line[len("import "):].rstrip(";").strip()
                if imp and not imp.startswith("static ") and not imp.endswith(".*"):
                    imports.add(imp)
    return sorted(imports)

def map_import_to_path(imp, src_root):
    return os.path.join(src_root, *imp.split(".")) + ".java"

def find_source_directory(project_path):
    project_name = os.path.basename(project_path)

    # Liste der zu prüfenden Pfade
    candidates = [
        "src/main/java",
        "src/java",
        "src",
        "gson/src/main/java",
        "sslcontext-kickstart/src/main/java",
    ]

    for candidate in candidates:
        path = Path(project_path) / candidate
        if path.is_dir():
            log(f"Source code folder found: {path}")
            return str(path)

    log(f"No source code folder found in {project_path}")
    return None

def create_bundle_for_project(project_path):
    project_name = os.path.basename(project_path)
    log(f"Process {project_name}")
    
    src_dir = find_source_directory(project_path)
    if not src_dir:
        return f"# Javadoc Bundle for {project_name}\n\n_No imports found._"

    imports = collect_imports(src_dir)
    if not imports:
        return f"# Javadoc Bundle for {project_name}\n\n_No imports found._"

    out = [f"# Javadoc Bundle for {project_name}\n"]
    total_len = lambda: sum(len(x) for x in out)

    for imp in imports:
        if imp.startswith(('java.', 'javax.', 'sun.', 'com.sun.')):
            continue
        
        if total_len() >= MAX_DOC_CHARS:
            break

        path_to_source = map_import_to_path(imp, src_dir)
        txt = read_text(path_to_source)
        
        if txt:
            blocks = javadoc_blocks(txt)
            if blocks:
                out.append(f"## {imp}\n")
                for b in blocks[:MAX_BLOCKS_PER_CLASS]:
                    out.append("> " + b.replace("\n", "\n> ") + "\n")

    bundle = "".join(out)
    if len(bundle) > MAX_DOC_CHARS:
        bundle = bundle[:MAX_DOC_CHARS] + "\n[...truncated...]\n"
        
    log(f"Created, Size: {len(bundle)}")
    return bundle


def main():
    if not os.path.isdir(REPOS_BASE_DIR):
        print(f"[ERROR] {REPOS_BASE_DIR} not found")
        return

    all_documentation = {}
    project_dirs = [d for d in os.scandir(REPOS_BASE_DIR) if d.is_dir()]

    for dir_entry in project_dirs:
        bundle = create_bundle_for_project(dir_entry.path)
        all_documentation[dir_entry.name] = bundle

    try:
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_documentation, f, indent=2, ensure_ascii=False)
        print(f"\n[SUCCESS] All documentation has been saved in {OUTPUT_JSON_FILE}")
    except Exception as e:
        print(f"\n[ERROR] Error saving the JSON file: {e}")

if __name__ == "__main__":
    main()