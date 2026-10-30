"""One-off, offline reconciliation of the 2026-10-29 cross-method billing interval."""
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import shutil

import run_search as search


def main():
    root = Path(__file__).resolve().parent
    source = root.parent.parent / 'openrouter_activity_2026-10-29.csv'
    audit_dir = root / 'billing_audit_20261029_overlap'
    assert not (root / 'search.lock').exists(), 'A search is active.'
    assert not audit_dir.exists(), 'Already audited; inspect existing evidence instead of rerunning.'
    states = {m: search.read(root / f'{m}_state.json') for m in ('bayesian', 'multifidelity')}
    b = states['bayesian']['records'][-1]
    m = states['multifidelity']['records'][0]
    assert len(states['bayesian']['records']) == 9 and len(states['multifidelity']['records']) == 1
    assert b['status'] == 'billing_pending' and m['status'] == 'complete'
    assert '20261029T051306378140Z' in b['jobs_dir'] and '20261029T051559429367Z' in m['jobs_dir']
    assert b['returncode'] == m['returncode'] == 0
    assert b['reward'] == m['reward'] == 0 and b['strict_pass'] is False and m['strict_pass'] is False
    assert b['key_usage_before_usd'] == m['key_usage_before_usd'] == 0.57610279
    with source.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    relevant = [r for r in rows if '2026-10-29 05:13:06' <= r['created_at'] < '2026-10-29 05:20:00']
    assert len(relevant) == len({r['generation_id'] for r in relevant}) == 37
    assert all(r['app_name'] == 'pi' and r['api_key_name'] == 'Key' and 'qwen3-coder' in r['model_permaslug'] for r in relevant)
    groups = {
        'bayesian': [r for r in relevant if r['created_at'] < '2026-10-29 05:15:59'],
        'multifidelity': [r for r in relevant if r['created_at'] >= '2026-10-29 05:15:59'],
    }
    assert len(groups['bayesian']) == 15 and len(groups['multifidelity']) == 22
    totals = {name: sum((Decimal(r['cost_total']) for r in group), Decimal(0)) for name, group in groups.items()}
    delta = Decimal(str(m['usage_snapshots_usd'][-1])) - Decimal(str(m['key_usage_before_usd']))
    residual = delta - sum(totals.values())
    assert totals == {'bayesian': Decimal('0.006310'), 'multifidelity': Decimal('0.032206')}
    assert delta == Decimal('0.03853010') and residual == Decimal('0.00001410')
    audit = {
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source': source.name,
        'method': 'Sum exported cost_total by non-overlapping run time windows; do not add cost_cache again.',
        'time_basis': 'CSV times treated as UTC; generation ID epoch and displayed UTC+08 timestamps agree.',
        'attribution_assumption': 'No unrelated requests on this key in these run windows. Time-based attribution, not a join to task request IDs.',
        'precision_note': 'Exported costs have limited precision. Residual cause unconfirmed; not assigned to either task.',
        'observed_interval_usd': str(delta),
        'unattributed_residual_usd': str(residual),
        'residual_budget_policy': 'Reserve once in multifidelity unattributed_interval_usd for conservative admission; exclude from candidate task cost.',
        'groups': {name: {'requests': group, 'cost_usd': str(totals[name])} for name, group in groups.items()},
    }
    audit_dir.mkdir()
    shutil.copy2(source, audit_dir / source.name)
    for name in states:
        shutil.copy2(root / f'{name}_state.json', audit_dir / f'{name}_state.before.json')
    search.save(audit_dir / 'audit.json', audit)
    for name, row in [('bayesian', b), ('multifidelity', m)]:
        row['billing_csv_reconciliation'] = {
            'audit_path': 'billing_audit_20261029_overlap/audit.json',
            'previous_status': row['status'], 'previous_cost_usd': row.get('cost_usd'),
            'basis': 'Exported request costs attributed by isolated run time window; limited CSV precision.',
            'request_count': len(groups[name]),
        }
        row['cost_usd'] = float(totals[name])
        row['status'] = 'complete'
    m['unattributed_interval_usd'] = float(residual)
    m['unattributed_interval_note'] = 'Shared billing residual, reserved here once for budget only; not attributed to this task.'
    for name, state in states.items():
        state['progress'] = {
            'valid_evaluations': sum(r['status'] == 'complete' for r in state['records']),
            'missing_evaluations': sum(r['status'] == 'skipped_api_failure' for r in state['records']),
            'task_launches': len(state['records']) + len(state.get('failed_attempts', [])),
            'budget_accounted_usd': search.accounted_cost(state),
        }
        if name == 'bayesian':
            best = max(range(len(state['configs'])), key=lambda i: search.score(state, i))
            state['selected'] = {'candidate': best, 'config': state['configs'][best], 'validation_pass_rate': search.score(state, best)[0] / 3}
            state['completion_status'] = 'complete'
        search.save(root / f'{name}_state.json', state)
    # Independent conservation check: the affected interval is counted exactly once.
    assert Decimal(str(b['cost_usd'])) + Decimal(str(m['cost_usd'])) + Decimal(str(m['unattributed_interval_usd'])) == delta
    for name, state in states.items():
        assert search.read(root / f'{name}_state.json') == state
        print(name, json.dumps(state['progress']), 'selected:', state.get('selected'))
    print('No API/model calls. Original states and CSV preserved in', audit_dir)


if __name__ == '__main__':
    main()
