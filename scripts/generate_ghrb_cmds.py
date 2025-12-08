import os

# --- Konfiguration ---
input_dir = "/root/libro/data/GHRB/bug_report"
script_to_run = "llm_query-basic.py"
output_dir = "/root/libro/data/GHRB/gen_tests_basic"
output_file = "all_ghrb_cmds.txt"
template_name = "basic_chat"
n_repetitions = 5
# --- Ende Konfiguration ---

os.makedirs(output_dir, exist_ok=True)

commands = []

if not os.path.exists(input_dir):
    print(f"Fehler: Eingabeverzeichnis '{input_dir}' nicht gefunden.")
else:
    for filename in os.listdir(input_dir):
        if filename.endswith(".json"):
            name = filename[:-5]  # Entfernt ".json"
            
            if "-" in name:
                project, bugid = name.rsplit("-", 1) 
                
                for n in range(n_repetitions):
                    # KORREKTUR HIER: Wir bauen den Dateinamen manuell mit Unterstrich zusammen
                    # Statt f"{name}_n{n}.txt" nutzen wir:
                    output_filename = f"{project}_{bugid}_n{n}.txt"
                    
                    cmd = (
                        f"python3.9 {script_to_run} -d ghrb "
                        f"-p {project} -b {bugid} "
                        f"--template {template_name} "
                        f"-o {output_dir}/{output_filename}"
                    )
                    commands.append(cmd)

if commands:
    with open(output_file, "w") as f:
        f.write("\n".join(commands))
    print(f"{len(commands)} GHRB-Befehle in '{output_file}' geschrieben.")
else:
    print("Keine passenden Dateien gefunden.")