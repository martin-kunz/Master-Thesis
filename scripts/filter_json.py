import json
import os

# Pfad zu den offiziellen Bug-Reports des Frameworks
bug_report_dir = '../data/GHRB/bug_report/'

# Ihre zusammengeführte, aber ungefilterte Ergebnisdatei
input_json_path = '../results/merged_ghrb_from_gpt.json'

# Name für die neue, gefilterte Ausgabedatei
output_json_path = '../results/merged_ghrb_filtered.json'

# 1. Alle validen/bekannten Bug-IDs aus den Dateinamen im Verzeichnis sammeln
try:
    # Erstellt eine Liste von Bug-IDs, indem es ".md" vom Ende jedes Dateinamens entfernt
    valid_bug_ids = {filename.replace('.md', '') for filename in os.listdir(bug_report_dir)}
    print(f"✅ {len(valid_bug_ids)} valide Bug-IDs im GHRB-Benchmark gefunden.")
except FileNotFoundError:
    print(f"FEHLER: Das Verzeichnis der Bug-Reports wurde nicht gefunden: {bug_report_dir}")
    exit()

# 2. Ihre JSON-Datei laden
try:
    with open(input_json_path, 'r') as f:
        all_results = json.load(f)
except FileNotFoundError:
    print(f"FEHLER: Ihre Input-JSON-Datei wurde nicht gefunden: {input_json_path}")
    exit()

# 3. Neues Dictionary erstellen, das nur die validen Bugs enthält
filtered_results = {}
original_count = len(all_results)
removed_count = 0

for bug_id, data in all_results.items():
    if bug_id in valid_bug_ids:
        filtered_results[bug_id] = data
    else:
        print(f"INFO: Unbekannter Bug '{bug_id}' wird entfernt.")
        removed_count += 1

# 4. Die gefilterten Ergebnisse in eine neue Datei schreiben
with open(output_json_path, 'w') as f:
    json.dump(filtered_results, f, indent=2)

print(f"\nFilterung abgeschlossen!")
print(f"Originale Anzahl Bugs: {original_count}")
print(f"Entfernte (unbekannte) Bugs: {removed_count}")
print(f"Verbleibende (valide) Bugs: {len(filtered_results)}")
print(f"Gefilterte Ergebnisse wurden in '{output_json_path}' gespeichert.")