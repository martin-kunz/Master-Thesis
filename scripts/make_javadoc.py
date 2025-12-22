#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def log(msg, verbose=False):
    if verbose: print(msg)


def run(cmd, cwd=None):
    res = subprocess.run(
        cmd if isinstance(cmd, list) else cmd.split(),
        cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def d4j_export(prop, workdir):
    """Export Defects4J configuration properties."""
    c, out, err = run(["defects4j", "export", "-p", prop, "-w", workdir])
    if c != 0: raise RuntimeError(err or out)
    return out.strip()


def read_text(p):
    try: return Path(p).read_text(encoding="utf-8", errors="ignore")
    except: return None


def javadoc_blocks(java_txt):
    """Extract Javadoc comment blocks using regex."""
    if not java_txt: return []
    pat = re.compile(r"/\*\*([\s\S]*?)\*/\s*(public|protected|private|class|interface|enum)", re.M)
    blocks = []
    for raw, _kw in pat.findall(java_txt):
        block = re.sub(r'^\s*\*\s?', '', raw, flags=re.M).strip()
        if block: blocks.append(block)
    return blocks


def find_major_pkg(src_dir):
    """Determine the primary package name of the project."""
    pkgs = {}
    for f in Path(src_dir).rglob("*.java"):
        t = read_text(f)
        if not t: continue
        m = re.search(r'^\s*package\s+([\w\.]+)\s*;', t, re.M)
        if m:
            parts = m.group(1).split(".")
            root = ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
            pkgs[root] = pkgs.get(root, 0) + 1
    return max(pkgs, key=pkgs.get) if pkgs else ""


def collect_imports(src_dir):
    imports = set()
    for f in Path(src_dir).rglob("*.java"):
        t = read_text(f)
        if not t: continue
        for line in t.splitlines():
            line = line.strip()
            if line.startswith("import "):
                imp = line[len("import "):].rstrip(";").strip()
                if imp and not imp.startswith("static "): imports.add(imp)
    return sorted(imports)


def clean_and_split_imports(imports_raw):
    imports, wildcards = [], []
    for imp in imports_raw:
        if not imp or imp.endswith(".") or imp.startswith("static "): continue
        if imp.endswith(".*"): wildcards.append(imp[:-2])
        else: imports.append(imp)
    return sorted(set(imports)), sorted(set(wildcards))


def expand_wildcard_pkg(pkg, src_root, bug_text, limit=5):
    """Find specific classes within a wildcard import package."""
    base = Path(src_root, *pkg.split("."))
    if not base.exists(): return []
    bug_lc = (bug_text or "").lower()
    hits, others = [], []
    for f in base.rglob("*.java"):
        cls = f.stem
        t = read_text(f) or ""
        m = re.search(r'^\s*package\s+([\w\.]+)\s*;', t, re.M)
        if not m: continue
        fqcn = m.group(1) + "." + cls
        if cls.lower() in bug_lc: hits.append(fqcn)
        else: others.append(fqcn)
    return sorted(set(hits)) if hits else sorted(set(others[:limit]))


def rank_imports(imports, bug_text, proj_rootpkg):
    """Rank imports by relevance to the bug report."""
    bug_lc = (bug_text or "").lower()
    def score(imp):
        s = 0
        if proj_rootpkg and imp.startswith(proj_rootpkg + "."): s += 5
        simple = imp.split(".")[-1].lower()
        if simple in bug_lc: s += 3
        return (-s, imp)
    return sorted(set(imports), key=score)


def map_import_to_path(imp, src_root):
    return os.path.join(src_root, *imp.split(".")) + ".java"


def collect_classpath_jars(cp):
    return [p for p in cp.split(os.pathsep) if p.endswith(".jar")]


def sibling_sources_jar(jar_path):
    base, ext = os.path.splitext(jar_path)
    cand = base + "-sources" + ext
    return cand if os.path.exists(cand) else None


def m2_sources_jar_guess(jar_path, m2_repo):
    name = os.path.basename(jar_path)
    if "-" not in name: return None
    artifact = "-".join(name.split("-")[:-1])
    version = name.split("-")[-1].replace(".jar", "")
    pattern = os.path.join(m2_repo, "**", artifact, version, f"{artifact}-{version}-sources.jar")
    matches = glob.glob(pattern, recursive=True)
    return matches[0] if matches else None


def ensure_unzip(jar, dest, verbose=False):
    os.makedirs(dest, exist_ok=True)
    code, out, err = run(["jar", "xf", jar], cwd=dest)
    if code != 0:
        log(f"[WARNING]: unzip failed: {jar}", verbose)
        return None
    return dest


def create_bundle(workdir, max_doc_chars, max_blocks_per_class, m2_repo, also_external, verbose, bug_json=None):
    """Core logic to generate a compact Markdown Javadoc bundle."""
    workdir = os.path.abspath(workdir)
    if not Path(workdir, ".defects4j.config").exists():
        return f"# Error\n\n{workdir} is not a valid D4J checkout."

    try:
        src_dir_rel = d4j_export("dir.src.classes", workdir)
        cp = d4j_export("cp.compile", workdir)
    except Exception as e:
        return f"# Error\n\nd4j export failed: {e}"

    src_dir = os.path.join(workdir, src_dir_rel)
    bug_text = ""
    if bug_json and Path(bug_json).exists():
        data = json.loads(read_text(bug_json) or "{}")
        bug_text = f"{data.get('title','')}\n{data.get('description','')}"

    imports_raw = collect_imports(src_dir)
    imports, wildcards = clean_and_split_imports(imports_raw)
    proj_root = find_major_pkg(src_dir)
    
    expanded = [item for pkg in wildcards for item in expand_wildcard_pkg(pkg, src_dir, bug_text)]
    ranked = rank_imports(sorted(set(imports + expanded)), bug_text, proj_root)
    
    extracted_roots = []
    if also_external and cp:
        for j in collect_classpath_jars(cp):
            s = sibling_sources_jar(j) or m2_sources_jar_guess(j, m2_repo)
            if s and os.path.exists(s):
                dest = os.path.join(workdir, "extracted", os.path.basename(s).replace(".jar", ""))
                root = ensure_unzip(s, dest, verbose)
                if root: extracted_roots.append(root)

    out = [f"# Library Docs Bundle for {os.path.basename(workdir)}\n"]
    seen = set()

    for imp in ranked:
        if imp in seen or sum(len(x) for x in out) >= max_doc_chars: break
        seen.add(imp)
        out.append(f"## {imp}\n")
        
        found = False
        for root in [src_dir] + extracted_roots:
            txt = read_text(map_import_to_path(imp, root))
            if txt:
                blocks = javadoc_blocks(txt)
                for b in blocks[:max_blocks_per_class]:
                    out.append("> " + b.replace("\n", "\n> ") + "\n")
                found = True
                break
        if not found: out.append("_No Javadoc found._\n")

    bundle = "".join(out)
    if len(bundle) > max_doc_chars: bundle = bundle[:max_doc_chars] + "\n[...truncated...]\n"
    shutil.rmtree(os.path.join(workdir, "extracted"), ignore_errors=True)
    return bundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bug_json", nargs="?")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--max-doc-chars", type=int, default=20000)
    parser.add_argument("--max-blocks-per-class", type=int, default=20)
    parser.add_argument("--m2-repo", default=str(Path.home() / ".m2" / "repository"))
    parser.add_argument("--also-external", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    
    bundle = create_bundle(args.workdir, args.max_doc_chars, args.max_blocks_per_class, args.m2_repo, args.also_external, args.verbose, args.bug_json)
    Path(os.path.join(args.workdir, "javadoc_bundle.txt")).write_text(bundle, encoding="utf-8")


if __name__ == "__main__":
    main()