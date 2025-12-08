import subprocess
import os
import sys
import shutil
import argparse


# Example usage:
#
# python3 run_ghrb_pipeline.py \
#   --exp_name "exp4" \
#   --gen_test_dir "/root/data/GHRB/gen_tests_exp4" \
#   --repos_base "/root/data/GHRB/repos"


# Projects list
PROJECTS = [
    ("google_gson", "gson", "11", "/root/data/GHRB/set_env_gson.sh"),
    ("assertj_assertj-core", "assertj-core", "17", "/root/data/GHRB/set_env.sh"),
    ("jhy_jsoup", "jsoup", "17", "/root/data/GHRB/set_env.sh"),
    ("FasterXML_jackson-databind", "jackson-databind", "17", "/root/data/GHRB/set_env.sh"),
    ("checkstyle_checkstyle", "checkstyle", "17", "/root/data/GHRB/set_env.sh"),
    ("Hakky54_sslcontext-kickstart", "sslcontext-kickstart", "17", "/root/data/GHRB/set_env.sh")
]

def run_cmd(command, cwd=None, shell=False, capture_output=False):
    """
    Executes a command. Uses Bash only if shell=True
    """
    try:
        if shell:
            result = subprocess.run(command, cwd=cwd, shell=True, check=True, executable='/bin/bash', capture_output=capture_output)
        else:
            result = subprocess.run(command, cwd=cwd, shell=False, check=True, capture_output=capture_output)
        
        if capture_output:
            return result.stdout.decode('utf-8').strip()
            
    except subprocess.CalledProcessError as e:
        if not capture_output: 
            print(f"Error executing: {command}")
            if hasattr(e, 'stderr') and e.stderr:
                print(f"Details: {e.stderr.decode('utf-8')}")
        return False
    return True


def set_java(version):
    """Sets the active Java version using update-alternatives"""
    print(f"Switching to Java {version}")
    path = f"/usr/lib/jvm/java-{version}-openjdk-amd64/bin/java"
    run_cmd(["update-alternatives", "--set", "java", path])


def remove_git_lock(repo_path):
    """Removes potentially orphaned index.lock files."""
    lock_file = os.path.join(repo_path, ".git", "index.lock")
    if os.path.exists(lock_file):
        print(f"Removing lock file: {lock_file}")
        try:
            os.remove(lock_file)
        except Exception as e:
            print(f"Could not remove lock file: {e}")


def check_env(env_script):
    """Checks and prints the active Java and Maven versions"""
    cmd = f"source {env_script} && java -version 2>&1 | head -n 1 && mvn -version | head -n 1"
    output = run_cmd(cmd, shell=True, capture_output=True)
    if output:
        print(output)
    else:
        print("Could not determine versions")


def clean_repo(repo_name, repos_base):
    """Cleans the git repository and resets it."""
    path = os.path.join(repos_base, repo_name)
    if os.path.exists(path):
        print(f"Cleaning Repo: {repo_name}")
        
        remove_git_lock(path)
        
        run_cmd(["git", "clean", "-fdx"], cwd=path)
        run_cmd(["git", "reset", "--hard"], cwd=path)
    else:
        print(f"Repository not found: {path}")


def main():
    # Command line arguments
    parser = argparse.ArgumentParser(description="Run GHRB experiments with configurable paths")
    
    parser.add_argument(
        "--exp_name", 
        required=True, 
        help="Suffix for the experiment name (e.g., exp4)"
    )
    parser.add_argument(
        "--gen_test_dir", 
        required=True, 
        help="Directory path for generated tests (e.g., /root/data/GHRB/gen_tests_...)"
    )
    parser.add_argument(
        "--repos_base", 
        required=True, 
        help="Base directory containing the repositories (e.g., /root/data/GHRB/repos)"
    )

    args = parser.parse_args()

    print("Starting GHRB Run")
    print(f"Configuration: Exp={args.exp_name}, TestDir={args.gen_test_dir}, Repos={args.repos_base}")
    
    os.chdir("/root/libro/scripts")

    for proj_id, folder, java_ver, env_script in PROJECTS:
        print(f"\n{'='*60}")
        print(f"Processing: {proj_id}")
        print(f"{'='*60}")

        clean_repo(folder, args.repos_base)

        set_java(java_ver)

        check_env(env_script)

        cmd = (
            f"source {env_script} && "
            f"python3.9 postprocess_ghrb.py "
            f"-p {proj_id} "
            f"--all "
            f"--exp_name {args.exp_name} "
            f"--gen_test_dir {args.gen_test_dir}"
        )

        success = run_cmd(cmd, cwd="/root/libro/scripts", shell=True)
        
        if success:
            print(f"{proj_id} successful")
        else:
            print(f"{proj_id} failed")

if __name__ == "__main__":
    main()
