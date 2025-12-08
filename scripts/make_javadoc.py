#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_javadoc.py (Refactored)
Erzeugt ein kompaktes Javadoc-Bundle (Markdown) für die tatsächlich genutzten Klassen
einer Defects4J-Bugversion. Läuft im Docker/Apptainer-Container.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# (Alle Hilfsfunktionen wie log, run, d4j_export, etc. bleiben hier unverändert)
# --- Anfang der Hilfsfunktionen ---

def log(msg, verbose=False):
    if verbose:
        print(msg)

def run(cmd, cwd=None):
    res = subprocess.run(
        cmd if isinstance(cmd, list) else cmd.split(),
        cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def d4j_export(prop, workdir):
    c, out, err = run(["defects4j", "export", "-p", prop, "-w", workdir])
    if c != 0:
        raise RuntimeError(err or out)
    return out.strip()

def read_text(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

def javadoc_blocks(java_txt):
    if not java_txt: return []
    pat = re.compile(r"/\*\*([\s\S]*?)\*/\s*(public|protected|private|class|interface|enum)", re.M)
    blocks = []
    for raw, _kw in pat.findall(java_txt):
        block = re.sub(r'^\s*\*\s?', '', raw, flags=re.M).strip()
        if block: blocks.append(block)
    return blocks

def find_major_pkg(src_dir):
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
            if not line.startswith("import "): continue
            imp = line[len("import "):].rstrip(";").strip()
            if not imp or imp.startswith("static "): continue
            imports.add(imp)
    return sorted(imports)

def clean_and_split_imports(imports_raw):
    imports, wildcards = [], []
    for imp in imports_raw:
        if not imp or imp.endswith(".") or imp.startswith("static "): continue
        if imp.endswith(".*"): wildcards.append(imp[:-2])
        else: imports.append(imp)
    return sorted(set(imports)), sorted(set(wildcards))

def expand_wildcard_pkg(pkg, src_root, bug_text, limit=5):
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
    if hits: return sorted(set(hits))
    return sorted(set(others[:limit]))

def rank_imports(imports, bug_text, proj_rootpkg):
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
        log(f"[WARN] unzip failed: {jar}\n{err or out}", verbose)
        return None
    return dest

# --- Ende der Hilfsfunktionen ---

def create_bundle(workdir, max_doc_chars, max_blocks_per_class, m2_repo, also_external, verbose, bug_json=None):
    """Die Kernlogik zur Erstellung eines Javadoc-Bundles für ein einzelnes Repository."""
    workdir = os.path.abspath(workdir)
    if not Path(workdir, ".defects4j.config").exists():
        log(f"[ERROR] {workdir} ist kein gültiges Defects4J-Checkout.", verbose)
        return f"# Error\n\n{workdir} ist kein gültiges Defects4J-Checkout."

    try:
        src_dir_rel = d4j_export("dir.src.classes", workdir)
        cp = d4j_export("cp.compile", workdir)
    except Exception as e:
        log(f"[ERROR] defects4j export fehlgeschlagen in {workdir}:\n{e}", verbose)
        return f"# Error\n\ndefects4j export fehlgeschlagen:\n{e}"

    src_dir = os.path.join(workdir, src_dir_rel) if not os.path.isabs(src_dir_rel) else src_dir_rel
    log(f"[INFO] src_dir = {src_dir}", verbose)
    
    bug_text = ""
    if bug_json and Path(bug_json).exists():
        try:
            data = json.loads(read_text(bug_json) or "{}")
            bug_text = f"{data.get('title','')}\n{data.get('description','')}"
        except Exception as e:
            log(f"[WARN] Bugreport konnte nicht geparst werden: {e}", verbose)

    imports_raw = collect_imports(src_dir)
    imports, wildcards = clean_and_split_imports(imports_raw)
    proj_root = find_major_pkg(src_dir)
    
    expanded = [item for pkg in wildcards for item in expand_wildcard_pkg(pkg, src_dir, bug_text, limit=5)]
    imports = sorted(set(imports + expanded))
    
    if not imports:
        log(f"[WARN] Keine Imports in {workdir} gefunden.", verbose)
        return "# Library Docs Bundle\n\n_No imports found._"
        
    ranked = rank_imports(imports, bug_text, proj_root)
    
    extracted_roots = []
    if also_external and cp:
        jars = collect_classpath_jars(cp)
        for j in jars:
            s = sibling_sources_jar(j) or m2_sources_jar_guess(j, m2_repo)
            if not s or not os.path.exists(s): continue
            dest = os.path.join(workdir, "extracted", os.path.basename(s).replace(".jar", ""))
            root = ensure_unzip(s, dest, verbose=verbose)
            if root: extracted_roots.append(root)

    out = [f"# Library Docs Bundle for {os.path.basename(workdir)}\n"]
    total_len = lambda: sum(len(x) for x in out)
    seen = set()

    for imp in ranked:
        if imp in seen or total_len() >= max_doc_chars: break
        seen.add(imp)
        out.append(f"## {imp}\n")
        
        found_doc = False
        
        p = map_import_to_path(imp, src_dir)
        txt = read_text(p)
        if txt:
            blocks = javadoc_blocks(txt)
            if blocks:
                for b in blocks[:max_blocks_per_class]:
                    out.append("> " + b.replace("\n", "\n> ") + "\n")
                found_doc = True

        if not found_doc:
            for root in extracted_roots:
                p = map_import_to_path(imp, root)
                txt = read_text(p)
                if txt:
                    blocks = javadoc_blocks(txt)
                    if blocks:
                        for b in blocks[:max_blocks_per_class]:
                            out.append("> " + b.replace("\n", "\n> ") + "\n")
                        found_doc = True
                        break
        
        if not found_doc:
            out.append("_No Javadoc found._\n")

    bundle = "".join(out)
    if len(bundle) > max_doc_chars:
        bundle = bundle[:max_doc_chars] + "\n[...truncated...]\n"
    
    # Clean up extracted sources to save space
    if extracted_roots:
        shutil.rmtree(os.path.join(workdir, "extracted"), ignore_errors=True)

    return bundle

def parse_args():
    p = argparse.ArgumentParser(description="Build a compact Javadoc bundle for a D4J bug checkout.")
    p.add_argument("bug_json", nargs="?", default=None, help="Pfad zur Bugreport-JSON (für besseres Relevanz-Ranking; optional).")
    p.add_argument("--workdir", required=True, help="Defects4J Checkout-Verzeichnis (enthält .defects4j.config).")
    p.add_argument("--max-doc-chars", type=int, default=20000, help="Maximale Zeichen im erzeugten Bundle (Default: 20000).")
    p.add_argument("--max-blocks-per-class", type=int, default=20, help="Maximale Javadoc-Blöcke je Klasse (Default: 20).")
    p.add_argument("--m2-repo", default=str(Path.home() / ".m2" / "repository"), help="Pfad zum lokalen Maven-Repo (für -sources Lookup).")
    p.add_argument("--also-external", action="store_true", help="Auch externe Bibliotheken berücksichtigen (langsamer).")
    p.add_argument("--verbose", action="store_true", help="Mehr Logausgabe.")
    return p.parse_args()

def main():
    """Die ursprüngliche Kommandozeilen-Funktionalität."""
    args = parse_args()
    
    bundle = create_bundle(
        workdir=args.workdir,
        max_doc_chars=args.max_doc_chars,
        max_blocks_per_class=args.max_blocks_per_class,
        m2_repo=args.m2_repo,
        also_external=args.also_external,
        verbose=args.verbose,
        bug_json=args.bug_json
    )
    
    out_path = os.path.join(args.workdir, "javadoc_bundle.txt")
    Path(out_path).write_text(bundle, encoding="utf-8")
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()