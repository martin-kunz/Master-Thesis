#!/usr/bin/env python3
import os, glob, asyncio
from openai import OpenAI
from llm_query import make_messages_from_file

API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=API_KEY)

JSON_DIR = "/root/data/Defects4J/bug_report"
OUT_DIR  = "/root/libro/data/Defects4J/gen_tests"
os.makedirs(OUT_DIR, exist_ok=True)

sem = asyncio.Semaphore(32)  # z.B. 32 gleichzeitige Calls

async def gen_test(json_path, n):
    project, bug_id = os.path.basename(json_path)[:-5].split("-",1)
    prompt, stop = make_messages_from_file(json_path)
    async with sem:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=prompt,
            stop=stop,
        )
    out = f"{OUT_DIR}/{project}_{bug_id}_n{n}.txt"
    with open(out, "w") as f:
        f.write(resp.choices[0].message.content)
    print(f"✔ {project}-{bug_id}-n{n}")

async def main():
    tasks = []
    for json_path in glob.glob(f"{JSON_DIR}/*.json"):
        for n in range(50):
            tasks.append(gen_test(json_path, n))
    # Starte alle Tasks, gestaffelt über das Semaphore-Limit
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())