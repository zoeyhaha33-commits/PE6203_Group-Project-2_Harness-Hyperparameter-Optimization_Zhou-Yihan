"""One-off audited recovery of a failed Pi startup followed by one scored rollout.

No benchmark, model or billing calls. Never select among multiple scored rollouts.
"""
import hashlib
import argparse
from pathlib import Path
import run_search as runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evaluation', type=int, choices=(4, 5, 6), default=4)
    evaluation = parser.parse_args().evaluation
    label, stamp, candidate, task_index, tools = {
        4: ('fourth', '20261029T152332087639Z', 3, 0, 21),
        5: ('fifth', '20261029T155543025739Z', 4, 0, 4),
        6: ('sixth', '20261029T161225489387Z', 1, 1, 4),
    }[evaluation]
    path = runner.ROOT / 'multifidelity_state.json'
    lock = runner.ROOT / 'search.lock'
    with lock.open('x') as f:
        f.write('offline-fourth-result-recovery')
    try:
        state = runner.read(path)
        row = state['records'][-1]
        assert len(state['records']) == evaluation and row['candidate'] == candidate and row['task_index'] == task_index
        assert stamp in row['jobs_dir']
        if row.get('multiple_result_audit'):
            print('Already recovered. No task launched.')
            return
        assert row['status'] == 'run_failed' and row['returncode'] == 0
        paths = [Path(p) for p in row['result_paths']]
        assert len(paths) == 2
        results = [runner.read(p) for p in paths]
        scored = [(p, r) for p, r in zip(paths, results) if isinstance(r.get('rewards'), dict)]
        failed = [(p, r) for p, r in zip(paths, results) if r.get('rewards') is None]
        assert len(scored) == len(failed) == 1
        good_path, good = scored[0]
        bad_path, bad = failed[0]
        assert all(r['task_name'] == row['task'] for r in results)
        assert bad.get('error_category') == 'acp_error' and 'Could not start pi: executable not found' in bad.get('error', '')
        assert bad['n_tool_calls'] == 0 and bad.get('verifier_error') is None
        assert bad['finished_at'] < good['started_at']
        assert good.get('error') is None and good.get('verifier_error') is None
        assert good['rewards']['reward'] == 0 and good['n_tool_calls'] == tools
        backup = path.with_name(f'multifidelity_state.before_{label}_result_recovery.json')
        assert not backup.exists()
        backup.write_bytes(path.read_bytes())
        evidence = {'basis': 'One unscored Pi startup failure followed by exactly one scored rollout; no choice among scored results.',
                    'scored_result_path': str(good_path),
                    'rollouts': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'raw_result': r}
                                 for p, r in zip(paths, results)],
                    'count_note': 'task_launches counts wrapper launches plus explicit retry archives; this launch contains two internal rollouts.',
                    'billing_note': 'Attribute the whole exclusive-key interval once, including internal failed startup, subject to delayed billing.'}
        audit_path = runner.ROOT / f'{label}_result_recovery_audit.json'
        runner.save(audit_path, evidence)
        row.update(status='billing_pending', reward=0.0, strict_pass=False,
                   error=None, verifier_error=None,
                   multiple_result_audit=audit_path.name,
                   scored_result_path=str(good_path), internal_rollout_count=2,
                   internal_unscored_startup_failures=1)
        runner.save(path, state)
        assert runner.read(path)['records'][-1]['status'] == 'billing_pending'
        print(f'Recovered {label} evaluation: reward 0; billing pending. Both original results preserved. No task launched.')
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
