"""Layer d: detection rules over the tool-call log.

Deliberately separate from tools.py: monitoring should not trust the code it monitors,
so it re-parses recipients itself and also fires on calls the allowlist already blocked.

Usage: python detect.py   -> prints alerts and writes logs/alerts.jsonl
"""
import json
import re
from pathlib import Path

LOG_FILE = Path("logs/toolcalls.jsonl")
ALERT_FILE = Path("logs/alerts.jsonl")
EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
TRUSTED_DOMAINS = {"firma.no"}


def detect(event: dict) -> dict | None:
    """Return an alert for one tool-call event, or None."""
    if event["tool"] == "send_email":
        domains = EMAIL_RE.findall(event["args"].get("to", ""))
        external = [d for d in domains if d.lower() not in TRUSTED_DOMAINS]
        if external or not domains:
            return {"severity": "high", "rule": "email_to_untrusted_domain", "domains": external}
    if event["status"] == "blocked_by_shield":
        return {"severity": "medium", "rule": "prompt_injection_in_document", "doc": event["args"]["name"]}
    return None


if __name__ == "__main__":
    alerts = []
    for line in LOG_FILE.read_text().splitlines():
        event = json.loads(line)
        if alert := detect(event):
            alerts.append({**alert, "run_id": event["run_id"], "ts": event["ts"], "tool_status": event["status"]})
    ALERT_FILE.write_text("".join(json.dumps(a) + "\n" for a in alerts))
    for a in alerts:
        print(f"[{a['severity'].upper():6}] {a['run_id']:10} {a['rule']} {a.get('domains', a.get('doc'))} ({a['tool_status']})")
    print(f"\n{len(alerts)} alerts written to {ALERT_FILE}")
