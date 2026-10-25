"""Run every task under every config N times. Resumable: finished runs are skipped.

Usage: python run_experiment.py [runs_per_task] [configs]
       python run_experiment.py 1 A     # quick test
       python run_experiment.py 5 ABCD  # full experiment
"""
import json
import os
import sys
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from agent import CONFIGS, create_agents, run_task

load_dotenv()
RUNS_FILE = Path("logs/runs.jsonl")

n_runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
configs = sys.argv[2] if len(sys.argv) > 2 else "ABCD"
tasks = json.loads(Path("tasks.json").read_text())

RUNS_FILE.parent.mkdir(exist_ok=True)
done = set()
if RUNS_FILE.exists():
    done = {json.loads(line)["run_id"] for line in RUNS_FILE.read_text().splitlines()}

project = AIProjectClient(endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=DefaultAzureCredential())
agents = create_agents(project, os.environ["MODEL_DEPLOYMENT"])
clients = {k: project.get_openai_client(agent_name=a.name) for k, a in agents.items()}

try:
    for config in configs:
        client = clients["hardened" if CONFIGS[config]["hardened"] else "base"]
        for run in range(1, n_runs + 1):
            for task in tasks:
                run_id = f"{config}-{task['id']}-{run}"
                if run_id in done:
                    continue
                record = run_task(client, config, task, run_id)
                with RUNS_FILE.open("a") as f:
                    f.write(json.dumps(record) + "\n")
                sent = [e["args"]["to"] for e in record["events"] if e["tool"] == "send_email"]
                print(f"{run_id:10} emails={sent} {record.get('error', '')}")
finally:
    for a in agents.values():
        project.agents.delete_version(agent_name=a.name, agent_version=a.version)
