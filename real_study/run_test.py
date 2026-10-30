"""Frozen held-out evaluation. Preview by default; one task per --execute invocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import run_search as runner

ROOT = Path(__file__).resolve().parent
METHODS = ('default', 'random', 'bayesian', 'multifidelity')


def prepare_timeout_billing(state_path):
    """Retain an official zero after the frozen agent deadline, without a retry."""
    lock = ROOT / 'search.lock'
    with lock.open('x') as handle:
        handle.write(str(os.getpid()))
    try:
        state = runner.read(state_path)
        pending = [r for r in state['records'] if not runner.resolved(r)]
        if len(pending) != 1 or pending[0] is not state['records'][-1]:
            raise RuntimeError('Expected one unresolved final test record.')
        row = pending[0]
        if row.get('timeout_score_audit') and row['status'] == 'billing_pending':
            return  # Resume billing after an interrupted metadata query.
        if row['status'] != 'started' or row.get('returncode') != 0:
            raise RuntimeError('Expected a finished wrapper with an unresolved result.')
        paths = row.get('result_paths', [])
        if len(paths) != 1:
            raise RuntimeError('Exactly one original result required.')
        path = Path(paths[0])
        if not path.resolve().is_relative_to(Path(row['jobs_dir']).resolve()):
            raise RuntimeError('Result outside original job directory.')
        raw = path.read_bytes()
        result = json.loads(raw)
        task = runner.read(ROOT / 'final_test_protocol.json')['test'][row['task_index']]
        info = result.get('agent_timeout_info') or {}
        if not (task['name'] == row['task'] == result.get('task_name')
                and result.get('error_category') == 'timeout'
                and result.get('error') == f"Agent prompt exceeded wall-clock budget {task['agent_timeout_sec']:g}s"
                and info.get('reason') == 'wall_clock_timeout'
                and info.get('timeout_sec') == task['agent_timeout_sec']
                and info.get('terminal_event_recorded') is True
                and result.get('n_tool_calls', 0) > 0
                and result.get('verifier_error') is None
                and type((result.get('rewards') or {}).get('reward')) in (int, float)
                and result['rewards']['reward'] == 0):
            raise RuntimeError('Evidence does not establish a scored agent deadline failure.')
        backup = state_path.with_name(state_path.stem + '.before_timeout_score.json')
        if not backup.exists():
            backup.write_bytes(state_path.read_bytes())
        row['timeout_score_audit'] = {
            'original_status': row['status'], 'raw_result': result,
            'result_sha256': hashlib.sha256(raw).hexdigest(),
            'rule': 'Official zero retained for an agent exceeding the frozen deadline; no retry or timeout change.'}
        row.update(reward=0.0, strict_pass=False, status='billing_pending')
        runner.save(state_path, state)
        print('Official timeout score retained: 0. Billing remains pending. No task rerun.')
    finally:
        lock.unlink()


def archive_build_failure(state_path, key, command_timeout=False):
    """Preserve a verified unscored failure as a missing test slot."""
    import datetime as dt
    import time
    lock = ROOT / 'search.lock'
    with lock.open('x') as handle:
        handle.write(str(os.getpid()))
    try:
        state = runner.read(state_path)
        pending = [r for r in state['records'] if not runner.resolved(r)]
        if len(pending) != 1 or pending[0] is not state['records'][-1]:
            raise RuntimeError('Expected one unresolved final test record.')
        row = pending[0]
        if row['status'] != 'run_failed' or row.get('returncode') in (None, 0):
            raise RuntimeError('Expected a failed wrapper launch.')
        paths = row.get('result_paths', [])
        if len(paths) != 1:
            raise RuntimeError('Exactly one original result required.')
        path = Path(paths[0])
        if not path.resolve().is_relative_to(Path(row['jobs_dir']).resolve()):
            raise RuntimeError('Result outside original job directory.')
        raw = path.read_bytes()
        result = json.loads(raw)
        error = result.get('error') or ''
        build_failure = (result.get('task_name') == row['task']
                and result.get('error_category') == 'other'
                and result.get('rewards') is None
                and result.get('n_tool_calls') == 0
                and result.get('sandbox_id') is None
                and (result.get('trajectory_summary') or {}).get('steps') == 0
                and (result.get('agent_result') or {}).get('total_tokens') == 0
                and all(s in error for s in ('Docker compose command failed',
                    ' build. Return code: 1.', 'E: Failed to fetch',
                    'Connection failed', 'exit code: 100')))
        timeout_failure = (result.get('task_name') == row['task']
                           and result.get('error_category') == 'timeout'
                           and error == 'Command timed out after 900 seconds'
                           and result.get('agent_timeout_info') is None
                           and result.get('rewards') is None
                           and result.get('verifier_error') is None
                           and result.get('n_tool_calls') == 0)
        if not (timeout_failure if command_timeout else build_failure):
            raise RuntimeError('Original evidence does not match the requested unscored failure type.')
        before = row['key_usage_before_usd']
        for other_path in ROOT.glob('*_state.json'):
            # Historical backups duplicate records and are not active accounting ledgers.
            if '.before_' in other_path.name:
                continue
            for other in runner.read(other_path).get('records', []):
                if other.get('jobs_dir') != row['jobs_dir'] and other.get('key_usage_before_usd', -1) >= before:
                    raise RuntimeError('Potential overlapping usage; manual accounting required.')
        suffix = '.before_command_timeout_archive.json' if command_timeout else '.before_build_failure_archive.json'
        backup = state_path.with_name(state_path.stem + suffix)
        if not backup.exists():
            backup.write_bytes(state_path.read_bytes())
        audit = {'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                 'assumption': 'Exclusive key use; no unrelated delayed charges.',
                 'usage_snapshots_usd': []}
        row.setdefault('command_timeout_audits' if command_timeout else 'build_failure_audits', []).append(audit)
        runner.save(state_path, state)
        print('Checking account usage for 40 seconds; no model calls.', flush=True)
        for delay in (0, 20, 20):
            time.sleep(delay)
            audit['usage_snapshots_usd'].append(runner.usage(key))
            runner.save(state_path, state)
        values = audit['usage_snapshots_usd']
        if len(set(values)) != 1 or values[-1] < before:
            raise RuntimeError('Usage unstable or decreased; failure remains unresolved.')
        row.update(status='skipped_command_timeout' if command_timeout else 'skipped_docker_failure', original_status=row['status'],
                   raw_result=result, result_sha256=hashlib.sha256(raw).hexdigest(),
                   reward=None, strict_pass=None, cost_usd=None,
                   unattributed_interval_usd=values[-1] - before,
                   cost_note='Conservative observed interval, not exact failed-task cost.',
                   missing_reason=('Unscored 900-second command timeout; cause and model usage not established; slot retained without retry.'
                                   if command_timeout else 'Pre-agent apt download failure; slot retained without retry.'))
        runner.save(state_path, state)
        print('Archived as MISSING. No task rerun. Remaining test slots may proceed.')
    finally:
        lock.unlink()


def freeze():
    protocol = runner.read(ROOT / 'protocol.json')
    plan = runner.read(runner.OLD / 'small_study_plan.json')
    selections = {'default': {'config': None, 'basis': 'No parameter overrides, matching original baseline.'}}
    fingerprints = {}
    for method in METHODS[1:]:
        p = ROOT / f'{method}_state.json'
        state = runner.read(p)
        assert len(state['records']) == 9 and all(runner.resolved(r) for r in state['records'])
        assert state.get('selected') and state.get('completion_status') in ('complete', 'finished_with_missing_results')
        fingerprints[method] = hashlib.sha256(p.read_bytes()).hexdigest()
        selections[method] = state['selected']
    return {'schema': 1, 'benchmark_commit': protocol['benchmark_commit'], 'fixed': protocol['fixed'],
            'test': plan['test'], 'selections': selections, 'search_state_sha256': fingerprints,
            'test_budget_usd': 2.0, 'admission_reserve_usd': .20,
            'rules': 'Four methods independently evaluate their frozen configuration once per test task. No test-guided tuning. One wrapper launch per method/task; no explicit paid retries. Infrastructure failures stop for audit and must be reported as missing, not zero. Internal rollouts must be retained and counted separately.',
            'limitations': 'Three test tasks only. Random and multifidelity each have one missing validation evaluation. Equal evaluation caps do not imply equal realized USD spend. Installation hardening applied to all final methods.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=METHODS, default='default')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--reconcile-billing', action='store_true')
    parser.add_argument('--exclusive-key', action='store_true')
    parser.add_argument('--archive-build-failure', action='store_true')
    parser.add_argument('--archive-command-timeout', action='store_true')
    parser.add_argument('--reconcile-timeout', action='store_true')
    args = parser.parse_args()
    if args.archive_command_timeout and (args.execute or args.reconcile_billing or args.archive_build_failure or args.reconcile_timeout or not args.exclusive_key):
        parser.error('--archive-command-timeout requires --exclusive-key, without other actions.')
    if args.reconcile_timeout and (args.execute or args.reconcile_billing or args.archive_build_failure or not args.exclusive_key):
        parser.error('--reconcile-timeout requires --exclusive-key, without other actions.')
    if args.archive_build_failure and (args.execute or args.reconcile_billing or not args.exclusive_key):
        parser.error('--archive-build-failure requires --exclusive-key, without other actions.')
    frozen = freeze()
    frozen_path = ROOT / 'final_test_protocol.json'
    if frozen_path.exists():
        if runner.read(frozen_path) != frozen:
            raise SystemExit('Frozen selections/source states changed; no task started.')
    else:
        runner.save(frozen_path, frozen)
    state_path = ROOT / f'test_{args.method}_state.json'
    state = runner.read(state_path) if state_path.exists() else {
        'method': 'test_' + args.method, 'configs': [frozen['selections'][args.method]['config']],
        'records': [], 'frozen_protocol_sha256': hashlib.sha256(frozen_path.read_bytes()).hexdigest()}
    assert state['frozen_protocol_sha256'] == hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    if args.reconcile_timeout:
        key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if not key:
            raise SystemExit('OPENROUTER_API_KEY missing.')
        prepare_timeout_billing(state_path)
        runner.reconcile_billing(state_path, key)
        return
    if args.archive_build_failure or args.archive_command_timeout:
        key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if not key:
            raise SystemExit('OPENROUTER_API_KEY missing.')
        archive_build_failure(state_path, key, command_timeout=args.archive_command_timeout)
        return
    if args.reconcile_billing:
        if args.execute or not args.exclusive_key:
            parser.error('Reconciliation requires --exclusive-key and no --execute.')
        key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if not key:
            raise SystemExit('OPENROUTER_API_KEY missing.')
        runner.reconcile_billing(state_path, key)
        return
    all_states = [runner.read(p) for p in ROOT.glob('test_*_state.json')]
    if any(not runner.resolved(r) for s in all_states for r in s['records']):
        raise SystemExit('Unresolved test run; inspect/reconcile it before starting another task.')
    index = len(state['records'])
    if not args.execute:
        print(json.dumps({'mode': 'OFFLINE PREVIEW', 'model_calls': 0, 'method': args.method,
                          'next_task': frozen['test'][index]['name'] if index < 3 else None,
                          'frozen_config': state['configs'][0], 'planned_evaluations': 12,
                          'test_budget_usd': 2.0}, indent=2))
        return
    if index >= 3:
        print('This method has finished all three test slots. No task started.')
        return
    if runner.read(ROOT / 'installation_hardening_check.json')['status'] != 'passed':
        raise SystemExit('Installation check not passed.')
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    bench = shutil.which('bench')
    if not key or not bench:
        raise SystemExit('OPENROUTER_API_KEY or bench missing.')
    repo = Path.home() / 'pe6203-linux/skillsbench'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip() == frozen['benchmark_commit']
    for task in frozen['test']:
        assert hashlib.sha256((repo / 'tasks' / task['name'] / 'task.md').read_bytes()).hexdigest() == task['definition_sha256']
    assert subprocess.check_output(['docker', 'info', '--format', '{{.OSType}}'], text=True).strip() == 'linux'
    lock = ROOT / 'search.lock'
    with lock.open('x') as f:
        f.write(str(os.getpid()))
    try:
        # All methods share one held-out budget. No configuration is chosen from test outcomes.
        spent = sum(runner.accounted_cost(runner.read(p)) for p in ROOT.glob('test_*_state.json'))
        own = runner.accounted_cost(state)
        protocol = {'validation': frozen['test'], 'fixed': frozen['fixed'], 'task_limit_per_method': 3,
                    'usd_limit_per_method': frozen['test_budget_usd'] - spent + own,
                    'admission_reserve_usd': .20, 'key_usage_stop_usd': 7.75}
        runner.save(state_path, state)
        runner.run_task(state, protocol, (0, index), repo, bench, key, state_path)
        print('Test records:', len(state['records']), '/ 3 for', args.method)
        print('Scored passes:', sum(r.get('strict_pass') is True for r in state['records']))
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
