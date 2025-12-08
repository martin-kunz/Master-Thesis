import os
import argparse


def main():
    parser = argparse.ArgumentParser(description="Generates execution commands for LLM-Query experiments (GHRB & Defects4J).")

    # Required arguments
    parser.add_argument("--dataset", required=True, choices=["ghrb", "d4j"], 
                        help="Select the dataset: 'ghrb' or 'd4j'.")
    parser.add_argument("--input_dir", required=True, 
                        help="Path to the directory containing the .json bug reports.")
    parser.add_argument("--output_dir", required=True, 
                        help="Target path where the generated test files (.txt) will be stored.")
    parser.add_argument("--cmd_file", required=True, 
                        help="Path to the output file where all commands will be written (e.g., all_cmds.txt).")

    # Optional arguments
    parser.add_argument("--n", type=int, default=5, 
                        help="Number of repetitions per bug (Default: 5).")
    parser.add_argument("--runner_script", default="llm_query.py", 
                        help="Name of the Python script to execute (Default: llm_query.py).")
    parser.add_argument("--template", default="2example_chat", 
                        help="Template name (Only relevant for GHRB, Default: basic_chat).")

    args = parser.parse_args()

    # Note: We do not create args.output_dir here because this script only generates text commands.
    # The directory creation usually happens when the generated commands are actually executed.

    commands = []

    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        return

    print(f"Reading bug reports from: {args.input_dir}")
    print(f"Dataset: {args.dataset.upper()}")
    print(f"Repetitions: {args.n}")

    # List all json files
    files = [f for f in os.listdir(args.input_dir) if f.endswith(".json")]
    
    if not files:
        print("No .json files found")
        return

    for filename in sorted(files):
        name = filename[:-5]
        
        if "-" in name:
            project, bugid = name.rsplit("-", 1)
            
            for n in range(args.n):
                test_filename = f"{project}_{bugid}_n{n}.txt"
                full_output_path = os.path.join(args.output_dir, test_filename)

                # Construct command based on dataset
                if args.dataset == "ghrb":
                    # GHRB
                    cmd = (
                        f"python3.9 {args.runner_script} -d ghrb "
                        f"-p {project} -b {bugid} "
                        f"--template {args.template} "
                        f"-o {full_output_path}"
                    )
                else: # Defect4J
                    cmd = (
                        f"python3.9 {args.runner_script} -d d4j "
                        f"-p {project} -b {bugid} "
                        f"--out {full_output_path}"
                    )

                commands.append(cmd)

    # Write commands to file
    if commands:
        with open(args.cmd_file, "w") as f:
            f.write("\n".join(commands))
        print(f"{len(commands)} commands successfully written to {args.cmd_file}")
    else:
        print("No commands generated")

if __name__ == "__main__":
    main()