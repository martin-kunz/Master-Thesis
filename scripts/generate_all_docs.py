#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_all_docs.py
Durchläuft den Defects4J repos-Ordner, extrahiert für jeden Bug-Typ (z.B. Chart_1, Closure_1)
ein Javadoc-Bundle und speichert alle Ergebnisse in einer einzigen JSON-Datei.
"""

import os
import json
from pathlib import Path

# Importiere die Kernlogik aus dem angepassten Skript
from make_javadoc import create_bundle

# --- Konfiguration ---
# Passe diese Pfade und Werte bei Bedarf an
REPOS_BASE_DIR = "repos"  # Der Ordner, der alle Checkouts enthält
OUTPUT_JSON_FILE = os.path.join(REPOS_BASE_DIR, "all_javadoc_bundles.json")
MAX_DOC_CHARS = 15000     # Zeichenlimit für JEDES einzelne Bundle
MAX_BLOCKS_PER_CLASS = 15 # Javadoc-Blöcke pro Klasse
ALSO_EXTERNAL = True     # Externe Bibliotheken durchsuchen? (langsamer)
VERBOSE = True            # Mehr Log-Ausgaben?
M2_REPO = str(Path.home() / ".m2" / "repository")


def find_representative_bugs(repos_dir):
    """Findet für jeden Projekttyp den Bug mit der ID 1."""
    targets = []
    if not os.path.isdir(repos_dir):
        print(f"[ERROR] Repository-Verzeichnis nicht gefunden: {repos_dir}")
        return []
        
    # Heuristik: Finde alle Ordner, die auf "_1" enden.
    # Dies ist ein einfacher Weg, um den ersten Bug jedes Projekts zu finden.
    for item in sorted(os.listdir(repos_dir)):
        if os.path.isdir(os.path.join(repos_dir, item)) and item.endswith("_1"):
            targets.append(item)
            
    print(f"[INFO] Gefundene Ziel-Bugs: {targets}")
    return targets

def main():
    """Hauptfunktion des Skripts."""
    target_bugs = find_representative_bugs(REPOS_BASE_DIR)
    
    if not target_bugs:
        return

    all_documentation = {}

    for bug_name in target_bugs:
        workdir = os.path.join(REPOS_BASE_DIR, bug_name)
        print(f"\n--- Verarbeite {bug_name} ---")
        
        # Rufe die wiederverwendbare Funktion auf
        bundle_content = create_bundle(
            workdir=workdir,
            max_doc_chars=MAX_DOC_CHARS,
            max_blocks_per_class=MAX_BLOCKS_PER_CLASS,
            m2_repo=M2_REPO,
            also_external=ALSO_EXTERNAL,
            verbose=VERBOSE,
            bug_json=None  # Wir haben hier keine spezifischen Bug-Reports
        )
        
        all_documentation[bug_name] = bundle_content
        print(f"--- Fertig mit {bug_name}, Bundle-Größe: {len(bundle_content)} Zeichen ---")

    # Speichere das gesammelte Ergebnis als JSON
    try:
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_documentation, f, indent=2, ensure_ascii=False)
        print(f"\n[SUCCESS] Alle Dokumentationen wurden erfolgreich in '{OUTPUT_JSON_FILE}' gespeichert.")
    except Exception as e:
        print(f"\n[ERROR] Fehler beim Speichern der JSON-Datei: {e}")


if __name__ == "__main__":
    main()
    