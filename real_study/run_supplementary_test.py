"""One supplementary launch per originally missing Scala slot; offline preview default."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import run_search as runner

ROOT = Path(__file__).resolve().parent
SUP = ROOT / 'supplementary_test'
METHODS = ('default', 'bayesian')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def amendment():
    frozen = runner.read(ROOT / 'final_test_protocol.json')
    sources = ['final_test_protocol.json'] + [f'test_{m}_state.json' for m in
               ('default', 'random', 'bayesian', 'multifidelity')]
    for method in METHODS:
        row = runner.read(ROOT / f'test_{method}_state.json')['records'][0]
        if row['task'] != 'python-scala-translation' or row.get('reward') is not None or row['status'] not in ('skipped_docker_failure', 'skipped_command_timeout'):
            raise RuntimeError('Supplement eligibility changed: ' + method)
    for method in ('default', 'random', 'bayesian', 'multifidelity'):
        if any(not runner.resolved(r) for r in runner.read(ROOT / f'test_{method}_state.json')['records']):
            raise RuntimeError('Original test billing/outcome unresolved.')
    return dict(schema=1, original_sha256={name: digest(ROOT / name) for name in sources},
        authorized_scope='User requested an amendment after inspecting original failure logs and results.',
        methods=list(METHODS), task=frozen['test'][0],
        configs={m: frozen['selections'][m]['config'] for m in METHODS}, fixed=frozen['fixed'],
        benchmark_commit=frozen['benchmark_commit'], maximum_launches_per_method=1,
        rules='Supplementary only, after observing main results. Preserve original protocol, ledgers and primary table. No tuning, changed task limits, best-of-attempt selection or further retries. A second unscored failure stays missing. Supplementary completed estimates must be labelled and shown beside original results.',
        accounting='Dedicated exclusive key. All supplementary usage intervals retained, including failures. Same original shared USD 2 test admission budget and USD 0.20 reserve; no budget reset. Stable zero is observed zero, not proof of free usage.',
        test_budget_usd=frozen['test_budget_usd'], reserve_usd=frozen['admission_reserve_usd'],
        cause_note='Default: failed apt/JDK download during image build. Bayesian: unscored 900-second command timeout with empty trajectory; root cause unconfirmed. Existing build cache may be used; no task or agent timeout changes.')


def freeze():
    plan = amendment()
    SUP.mkdir(exist_ok=True)
    path = SUP / 'amendment.json'
    if path.exists():
        if runner.read(path) != plan:
            raise RuntimeError('Amendment or original evidence changed; no launch.')
    else:
        # Exclusive create: the first preview freezes the amendment before paid runs.
        with path.open('x', encoding='utf-8') as f:
            json.dump(plan, f, indent=2)
            f.write('\n')
    return plan


def classify(result, task):
    reward = (result.get('rewards') or {}).get('reward')
    timeout = result.get('agent_timeout_info') or {}
    scored_timeout = (result.get('error_category') == 'timeout'
        and result.get('error') == f"Agent prompt exceeded wall-clock budget {task['agent_timeout_sec']:g}s"
        and timeout.get('reason') == 'wall_clock_timeout'
        and timeout.get('timeout_sec') == task['agent_timeout_sec']
        and timeout.get('terminal_event_recorded') is True)
    valid = (result.get('task_name') == task['name'] and result.get('verifier_error') is None
        and (not result.get('error') or scored_timeout)
        and type(reward) in (int, float) and math.isfinite(reward) and 0 <= reward <= 1)
    return reward if valid else None


def settle(path, plan, key):
    state = runner.read(path)
    row = state['records'][0]
    if row['status'] in ('complete', 'missing'):
        print('Supplement already settled. No task launched.')
        return
    if row.get('returncode') is None:
        raise RuntimeError('Launch completion unknown; inspect process/logs. No relaunch allowed.')
    paths = sorted(Path(row['jobs_dir']).rglob('result.json'))
    row['result_paths'] = [str(p) for p in paths]
    reward = None
    if len(paths) == 1:
        result = runner.read(paths[0])
        row.update(raw_result=result, result_sha256=digest(paths[0]))
        reward = classify(result, plan['task'])
        if row['returncode'] != 0:
            reward = None
    row.update(reward=reward, strict_pass=reward == 1 if reward is not None else None, status='billing_pending')
    audit = {'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'usage_snapshots_usd': []}
    row.setdefault('billing_checks', []).append(audit)
    runner.save(path, state)
    print('Checking account usage for 60 seconds. No additional model request.', flush=True)
    for delay in (0, 20, 20, 20):
        time.sleep(delay)
        audit['usage_snapshots_usd'].append(runner.usage(key))
        runner.save(path, state)
    values = audit['usage_snapshots_usd']
    before = row['key_usage_before_usd']
    if len(set(values[-3:])) != 1 or values[-1] < before:
        raise RuntimeError('Billing unsettled; reconcile only, never relaunch.')
    row.update(status='complete' if reward is not None else 'missing',
               cost_usd=values[-1]-before, cost_note='Exclusive-key observed interval, subject to delayed billing; zero is not proof of free usage.')
    runner.save(path, state)
    print(json.dumps({k: row.get(k) for k in ('task','status','reward','strict_pass','cost_usd','result_paths')}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=METHODS, required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--execute', action='store_true')
    action.add_argument('--reconcile-only', action='store_true')
    parser.add_argument('--exclusive-key', action='store_true')
    args = parser.parse_args()
    if (args.execute or args.reconcile_only) and not args.exclusive_key:
        parser.error('Execution/reconciliation requires --exclusive-key.')
    plan = freeze()
    path = SUP / f'{args.method}_state.json'
    if not args.execute and not args.reconcile_only:
        print(json.dumps(dict(mode='OFFLINE PREVIEW', model_calls=0, method=args.method,
            task=plan['task']['name'], config=plan['configs'][args.method],
            prior_supplement_exists=path.exists(), rules=plan['rules']), indent=2))
        return
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise RuntimeError('OPENROUTER_API_KEY missing.')
    lock = ROOT / 'search.lock'
    with lock.open('x') as f:
        f.write(str(os.getpid()))
    try:
        if args.reconcile_only:
            # Reject late reconciliation after a different supplement was launched.
            row = runner.read(path)['records'][0]
            for other_path in SUP.glob('*_state.json'):
                other = runner.read(other_path)['records'][0]
                if other_path != path and other['key_usage_before_usd'] >= row['key_usage_before_usd']:
                    raise RuntimeError('Potential overlapping billing interval; manual audit needed.')
            settle(path, plan, key)
            return
        if path.exists():
            raise RuntimeError('Supplement slot already consumed; use --reconcile-only if needed. No relaunch.')
        for other_path in SUP.glob('*_state.json'):
            if runner.read(other_path)['records'][0]['status'] not in ('complete', 'missing'):
                raise RuntimeError('Unsettled supplement blocks next launch.')
        repo = Path.home() / 'pe6203-linux/skillsbench'
        if not shutil.which('bench') or runner.read(ROOT/'installation_hardening_check.json')['status'] != 'passed':
            raise RuntimeError('Bench or passed installation check missing.')
        if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip() != plan['benchmark_commit']:
            raise RuntimeError('Benchmark commit changed.')
        if digest(repo/'tasks'/plan['task']['name']/'task.md') != plan['task']['definition_sha256']:
            raise RuntimeError('Task definition changed.')
        if subprocess.check_output(['docker', 'info', '--format', '{{.OSType}}'], text=True).strip() != 'linux':
            raise RuntimeError('Linux Docker required.')
        subprocess.run(['docker','image','inspect','pe6203-test-prepared:python-scala-translation'], check=True, stdout=subprocess.DEVNULL)
        original_spent = sum(runner.accounted_cost(runner.read(ROOT/f'test_{m}_state.json')) for m in ('default','random','bayesian','multifidelity'))
        extra_spent = sum(runner.read(p)['records'][0]['cost_usd'] for p in SUP.glob('*_state.json'))
        before = runner.usage(key)
        if original_spent + extra_spent + plan['reserve_usd'] > plan['test_budget_usd'] or before >= 7.75:
            raise RuntimeError('Original shared budget admission stopped.')
        jobs = repo/'jobs'/('supplement-'+args.method+'-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        command = runner.command_for('bench', repo, {'fixed': plan['fixed']}, plan['task'], plan['configs'][args.method], jobs)
        command = [sys.executable, str(ROOT/'bench_hardened.py'), *command[1:]]
        state = dict(method=args.method, amendment_sha256=digest(SUP/'amendment.json'),
                     records=[dict(task=plan['task']['name'], status='started', key_usage_before_usd=before, jobs_dir=str(jobs), command=command)])
        runner.save(path, state)  # Persist consumed slot before any subprocess/model request.
        env = dict(os.environ, LITELLM_API_KEY=key, LITELLM_BASE_URL='https://openrouter.ai/api/v1')
        state['records'][0]['returncode'] = subprocess.run(command, cwd=repo, env=env).returncode
        runner.save(path, state)
        settle(path, plan, key)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
