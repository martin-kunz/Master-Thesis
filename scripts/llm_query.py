#!/usr/bin/env python
# coding: utf-8

import os
import re
import json
import argparse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from config import llm_exp_config
from llm_api import model_is_chat, query_llm

TEMPLATE_DIR = llm_exp_config['template_dir']

# NEU: Hier werden die Prompts gespeichert
PROMPT_LOG_DIR = 'root/libro/data/prompt_examples'

# --- KONFIGURATION DER EXPERIMENTE ---
EXPERIMENT_CONFIGS = {
    "libro":          {"template_base": "2example_chat", "include_docs": False},
    "libro-repro":    {"template_base": "2example_chat", "include_docs": False},
    "basic":          {"template_base": "basic_chat",    "include_docs": False},
    "exp1":           {"template_base": "exp1_chat",     "include_docs": False},
    "exp2":           {"template_base": "exp2_chat",     "include_docs": True},
    "exp3":           {"template_base": "exp3_chat",     "include_docs": True},
    "exp4":           {"template_base": "exp4_chat",     "include_docs": True},
    "all":            {"template_base": "all_in_chat",   "include_docs": True},
    "legacy":         {"template_base": "2example_chat", "include_docs": False}
}

def make_messages_from_file(rep_title, rep_content, project_name, 
                            template_file, dataset, include_docs=False):
    """
    Erstellt die Prompt-Messages.
    """
    rep_title = BeautifulSoup(rep_title.strip(), 'html.parser').get_text()
    rep_content = md(rep_content.strip())

    # 1. Bug Report Text
    bug_report_content = f"""
# {rep_title}
## Description
{rep_content}
"""

    # 2. Dokumentation
    if not include_docs:
        enhanced_content = bug_report_content
    else:
        if dataset == 'ghrb':
            doc_filename = 'javadocs_GHRB.json'
        else:
            doc_filename = 'javadocs_Defects4J.json'

        # Versuche relativen Pfad oder Fallback
        docs_file_path = os.path.join(TEMPLATE_DIR, '../javadoc', doc_filename)
        if not os.path.exists(docs_file_path):
             # Fallback: Relativ zum Skript oder hardcoded
             script_dir = os.path.dirname(os.path.abspath(__file__))
             docs_file_path = os.path.join(script_dir, '../javadoc', doc_filename)
             
             if not os.path.exists(docs_file_path):
                 # Dein absoluter Pfad als letzter Fallback
                 docs_file_path = f'/vol/fob-vol7/mi21/kunzmart/Master-Thesis/libro/data/javadoc/{doc_filename}'

        project_docs = "Documentation not found."
        
        if os.path.exists(docs_file_path):
            try:
                with open(docs_file_path, 'r', encoding='utf-8') as f:
                    all_docs = json.load(f)
                
                # --- INTELLIGENTE SUCHE ---
                # 1. Exakter Match
                found_doc = all_docs.get(project_name)
                
                # 2. GHRB Fix: Wenn "user_repo" nicht gefunden, versuche "repo"
                if not found_doc and "_" in project_name:
                    simple_name = project_name.split("_", 1)[1] # Alles nach dem ersten "_"
                    found_doc = all_docs.get(simple_name)
                
                if found_doc:
                    project_docs = found_doc
                else:
                    # Optional: Zeige erste 3 Keys zum Debuggen
                    # keys_preview = list(all_docs.keys())[:3]
                    pass 

            except Exception as e:
                print(f"Warning: Could not load docs from {docs_file_path}: {e}")
        else:
            print(f"Warning: Documentation file not found at {docs_file_path}")
        
        enhanced_content = f"""
{bug_report_content}
---

To help you, here is some relevant API documentation for the project '{project_name}':
---
{project_docs}
"""

    # --- Template verarbeiten ---
    with open(template_file, 'r', encoding='utf-8') as f:
        messages = json.load(f)

        for msg in messages:
            # Examples laden
            example_text_path = re.findall(r'{%(.+?)%}', msg['content'])
            if len(example_text_path) > 0:
                for ef in example_text_path:
                    full_example_path = os.path.join(TEMPLATE_DIR, ef)
                    if os.path.exists(full_example_path):
                        with open(full_example_path, 'r', encoding='utf-8') as f_ex:
                            example_text = f_ex.read()
                        msg['content'] = msg['content'].replace('{%'+ef+'%}', example_text)
                    else:
                        print(f"Warning: Example file {ef} not found at {full_example_path}")

            # Content einfügen
            if '{{bug_report_content}}' in msg['content']:
                msg['content'] = msg['content'].replace('{{bug_report_content}}', enhanced_content)

    return messages, None


def make_prompt_from_file(rep_title, rep_content,
                          use_plain_text, use_html,
                          template_file):
    if use_plain_text:
        rep_title = BeautifulSoup(rep_title.strip(), 'html.parser').get_text()
        rep_content = BeautifulSoup(rep_content.strip(), 'html.parser').get_text()
    elif not use_html:
        rep_title = BeautifulSoup(rep_title.strip(), 'html.parser').get_text()
        rep_content = md(rep_content.strip())

    with open(template_file, 'r', encoding='utf-8') as f:
        template_str = f.read()
        prompt = template_str.replace('{{title}}', rep_title.strip())
        prompt = prompt.replace('{{content}}', rep_content.strip())
        nonempty_lines = [e for e in template_str.split('\n') if len(e) != 0]
        last_line = nonempty_lines[-1]
        prompt = prompt.strip().removesuffix(last_line).strip()
        end_string = last_line.removeprefix('{{endon}}:').strip()

    return prompt, [end_string]


def query_llm_for_gentest(proj, bug_id, model, 
                          template_name, include_docs, dataset, 
                          use_plain_text=False, use_html=False, 
                          save_prompt=False, prompt_save_path=None):
    
    # Pfad zum Bug Report Verzeichnis basierend auf dataset bestimmen
    if dataset == 'ghrb':
        current_br_dir = llm_exp_config['bug_report_dir']['ghrb']
    else:
        current_br_dir = llm_exp_config['bug_report_dir']['d4j']

    bug_file_path = os.path.join(current_br_dir, f"{proj}-{bug_id}.json")
    
    if not os.path.exists(bug_file_path):
        print(f"ERROR: Bug report file not found at {bug_file_path}")
        return ""

    with open(bug_file_path, 'r', encoding='utf-8') as f:
        br = json.load(f)
        
    chat_mode = model_is_chat(model)

    # Template Pfad
    template_path = os.path.join(TEMPLATE_DIR, f'{template_name}.json')
    if not chat_mode:
        template_path = os.path.join(TEMPLATE_DIR, f'{template_name}.txt')

    if chat_mode:
        prompt, stop = make_messages_from_file(
            br['title'], br['description'],
            proj,
            template_file=template_path,
            dataset=dataset,
            include_docs=include_docs
        )
    else:
        desc_key = 'description_fixed' if 'description_fixed' in br else 'description'
        if 'description_fixed' in br:
             use_html = True 
             use_plain_text = False

        prompt, stop = make_prompt_from_file(
            br['title'], br[desc_key],
            use_plain_text=use_plain_text,
            use_html=use_html, 
            template_file=template_path
        )

    # --- SPEICHER-LOGIK ---
    if save_prompt:
        ext = 'json' if chat_mode else 'txt'
        
        # Wenn kein Pfad via CLI übergeben wurde, nutze den Default-Ordner
        if prompt_save_path is None:
            filename = f'{proj}-{bug_id}-{template_name}.{ext}'
            prompt_save_path = os.path.join(PROMPT_LOG_DIR, filename)
        
        # Ordner erstellen (rekursiv)
        os.makedirs(os.path.dirname(prompt_save_path) if os.path.dirname(prompt_save_path) else '.', exist_ok=True)
        
        print(f"Saving prompt to: {prompt_save_path}")
        with open(prompt_save_path, 'w', encoding='utf-8') as f:
            if ext == 'json':
                json.dump(prompt, f, indent=2)
            else:
                f.write(prompt)

    print("================ ANFRAGE-PROMPT AN LLM ================")
    if chat_mode:
        print(json.dumps(prompt, indent=2))
    else:
        print(prompt)
    print("======================================================")

    query_result = query_llm(prompt, model, stop)
    
    if not chat_mode:
        gen_test = 'public void test' + query_result
    else:
        if "```" in query_result:
            if "```java" in query_result:
                parts = query_result.split("```java")
                if len(parts) > 1:
                    gen_test = parts[1].split("```")[0]
                else:
                    gen_test = query_result.split("```")[1]
            else:
                gen_test = query_result.split("```")[1]
        else:
            gen_test = query_result
            
    return gen_test


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset', default='d4j', help='dataset to use: d4j or ghrb')
    parser.add_argument('-p', '--project', default='Time')
    parser.add_argument('-b', '--bug_id', type=int, default=23)
    parser.add_argument('--use_html', action='store_true')
    parser.add_argument('--use_plain_text', action='store_true')
    
    # Trigger zum Speichern
    parser.add_argument('--save_prompt', action='store_true', help="Saves the prompt to disk")
    
    parser.add_argument('--experiment', default='legacy', 
                        choices=EXPERIMENT_CONFIGS.keys())
    
    parser.add_argument('--template_override', default=None)

    parser.add_argument('--model', default='OpenAI/gpt-3.5-turbo')
    parser.add_argument('-o', '--out', default='output.txt')
    parser.add_argument('--prompt_out', default=None)
    args = parser.parse_args()

    # Config laden
    if args.experiment not in EXPERIMENT_CONFIGS:
        print(f"Error: Experiment '{args.experiment}' not found in config. Using legacy.")
        selected_config = EXPERIMENT_CONFIGS['legacy']
    else:
        selected_config = EXPERIMENT_CONFIGS[args.experiment]
    
    template_name = args.template_override if args.template_override else selected_config['template_base']
    should_include_docs = selected_config['include_docs']

    print(f"Running Experiment: {args.experiment}")
    print(f"Dataset: {args.dataset} | Project: {args.project} | Bug: {args.bug_id}")

    gen_test = query_llm_for_gentest(
        proj=args.project, 
        bug_id=args.bug_id, 
        model=args.model,
        template_name=template_name,
        include_docs=should_include_docs,
        dataset=args.dataset,
        use_plain_text=args.use_plain_text, 
        use_html=args.use_html,
        save_prompt=args.save_prompt, 
        prompt_save_path=args.prompt_out
    )

    if gen_test:
        print(f"Saving test to: {os.path.abspath(args.out)}")
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(gen_test)
    else:
        print("No test generated. Check logs.")