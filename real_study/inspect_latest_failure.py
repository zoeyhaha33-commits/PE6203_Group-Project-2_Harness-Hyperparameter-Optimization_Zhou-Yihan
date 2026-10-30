"""Read-only selected diagnostics; no model or billing requests."""
import json
from pathlib import Path

root = Path('/home/zoeyhaha33/pe6203-linux/skillsbench/jobs/search-multifidelity-20261029T152332087639Z')
for p in sorted(root.rglob('result.json')):
    r = json.loads(p.read_text())
    print(json.dumps({k: r.get(k) for k in ('rollout_name', 'rewards', 'error', 'error_category', 'verifier_error', 'n_tool_calls', 'agent_result', 'started_at', 'finished_at')}, indent=2))
    log = p.parent / 'agent/pi_acp.txt'
    if log.exists():
        print('Pi log tail:', log.read_text()[-2500:])
