"""Real validation search. Preview by default; --execute permits paid tasks.

No test evaluation. A persisted task record prevents automatic paid repeats.
Use one dedicated OpenRouter key and no concurrent experiments.
"""
import argparse
import datetime as dt
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
OLD = Path(os.environ.get('PE6203_SOURCE_DIR', str(ROOT / 'source_inputs')))
SPACE = {'contextWindow': [64000, 96000, 128000], 'maxTokens': [4096, 8192, 16384]}
RECOVERY_POLICY = {
    'version': 1,
    'declared_after': 'First suspected API error, Random candidate 1 task 2; after five scored Random evaluations.',
    'applies_to': ['random', 'bayesian', 'multifidelity'],
    'max_extra_attempts_per_method': 1,
    'eligibility': 'Nonzero process exit; suspected_api_error; no reward; zero recorded tool calls. Explicit retry only.',
    'budget': 'Keep nine scored evaluations and USD 1.50 admission limit; allow at most ten task launches per method. Include failed-attempt observed costs.',
    'accounting': 'Stable zero delta on failed attempt means no observed charge, not confirmed free usage. Preserve raw failure and snapshots.',
}


def failed_cost(state, candidate=None):
    return sum(r['cost_usd'] for r in state.get('failed_attempts', [])
               if candidate is None or r['candidate'] == candidate)


def resolved(row):
    return row['status'] in ('complete', 'skipped_api_failure', 'skipped_docker_failure', 'skipped_command_timeout')


def accounted_cost(state):
    return (sum(r['cost_usd'] for r in state['records'] if r['status'] == 'complete')
            + failed_cost(state) + sum(r.get('unattributed_interval_usd', 0) for r in state['records']))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def usage(key):
    request = urllib.request.Request('https://openrouter.ai/api/v1/key', headers={'Authorization': 'Bearer ' + key})
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)['data']['usage']
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise RuntimeError('Invalid provider usage; stopping.')
    return value


def frozen_protocol(source):
    plan = read(source / 'small_study_plan.json')
    return {
        'schema': 1, 'seed': 20261028, 'benchmark_commit': plan['benchmark_commit'],
        'validation': plan['validation'], 'fixed': plan['fixed'], 'space': SPACE,
        'task_limit_per_method': 9, 'usd_limit_per_method': 1.5,
        'admission_reserve_usd': 0.20, 'key_usage_stop_usd': 7.75,
        'random': 'Three unique uniformly sampled configurations, three tasks each.',
        'bayesian': 'Optuna TPE, one startup trial, three configurations, three tasks each. Duplicates are independent evaluations.',
        'multifidelity': 'Five unique random configurations on validation[0]; best two complete validation[1:3]. Reuse screening results.',
        'ranking': 'Strict passes, then mean official reward, then lower observed cost, then earlier candidate.',
        'tpe_objective': 'Number of strict passes only; final selection uses ranking above.',
        'timing': 'Protocol specified after Default baseline was observed; before optimizer search.',
        'cost_note': 'Observed dedicated-key usage deltas, subject to delayed billing. Admission checks are not hard spending caps.',
        'test_evaluations': 0,
    }


def initial_state(method, protocol):
    grid = [dict(zip(SPACE, values)) for values in itertools.product(*SPACE.values())]
    random.Random(protocol['seed']).shuffle(grid)
    count = 3 if method == 'random' else 5 if method == 'multifidelity' else 0
    return {'method': method, 'protocol_sha256': hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest(),
            'configs': grid[:count], 'records': [], 'promoted': None}


def score(state, index):
    rows = [r for r in state['records'] if r['candidate'] == index and r['status'] == 'complete']
    return (sum(r['strict_pass'] for r in rows), sum(r['reward'] for r in rows) / len(rows) if rows else -1,
            -(sum(r['cost_usd'] for r in rows) + failed_cost(state, index)), -index)


def tpe_next(state, protocol):
    import optuna
    version = optuna.__version__
    if state.get('optuna_version', version) != version:
        raise RuntimeError('Optuna version changed.')
    state['optuna_version'] = version
    study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=protocol['seed'], n_startup_trials=1))
    # Replay asks AND tells to reproduce the sampler RNG on resume.
    for index in range(len(state['configs']) + 1):
        trial = study.ask()
        config = {key: trial.suggest_categorical(key, values) for key, values in SPACE.items()}
        if index == len(state['configs']):
            return config
        if config != state['configs'][index]:
            raise RuntimeError('TPE replay mismatch.')
        rows = [r for r in state['records'] if r['candidate'] == index and r['status'] == 'complete']
        if len(rows) == 3:
            study.tell(trial, score(state, index)[0])
        else:
            study.tell(trial, state=optuna.trial.TrialState.FAIL)


def next_pair(state, protocol):
    done = {(r['candidate'], r['task_index']) for r in state['records'] if resolved(r)}
    method = state['method']
    if method == 'multifidelity':
        for candidate in range(5):
            if (candidate, 0) not in done:
                return candidate, 0
        if state['promoted'] is None:
            eligible = [r['candidate'] for r in state['records'] if r['task_index'] == 0 and r['status'] == 'complete']
            state['promoted'] = sorted(eligible, key=lambda i: score(state, i), reverse=True)[:2]
        for candidate in state['promoted']:
            for task in (1, 2):
                if (candidate, task) not in done:
                    return candidate, task
        return None
    for candidate in range(3):
        if candidate == len(state['configs']):
            state['configs'].append(tpe_next(state, protocol))
        for task in range(3):
            if (candidate, task) not in done:
                return candidate, task
    return None


def command_for(bench, repo, protocol, task, config, jobs):
    command = [bench, 'eval', 'run', '--tasks-dir', 'tasks/' + task['name'], '--agent', 'pi',
            '--model', protocol['fixed']['model'], '--sandbox', 'docker', '--skill-mode', 'no-skill',
            '--loop-strategy', 'single-shot', '--concurrency', '1', '--jobs-dir', str(jobs)]
    if config is not None:
        model = dict(id='qwen/qwen3-coder', reasoning=False, input=['text'], **config)
        command += ['--agent-env', 'BENCHFLOW_PROVIDER_MODELS=' + json.dumps([model], separators=(',', ':'))]
    return command


def run_task(state, protocol, pair, repo, bench, key, state_path):
    candidate, task_index = pair
    before = usage(key)
    spent = accounted_cost(state)
    if len(state['records']) >= protocol['task_limit_per_method'] or len(state['records']) + len(state.get('failed_attempts', [])) >= 10:
        raise RuntimeError('Task launch limit reached.')
    if spent + protocol['admission_reserve_usd'] > protocol['usd_limit_per_method'] or before >= protocol['key_usage_stop_usd']:
        raise RuntimeError('Budget admission stopped; no new task started.')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    jobs = repo / 'jobs' / ('search-' + state['method'] + '-' + stamp)
    task = protocol['validation'][task_index]
    command = command_for(bench, repo, protocol, task, state['configs'][candidate], jobs)
    # Local launcher changes only installation checks/retries; agent pins and runtime remain fixed.
    installation_check = ROOT / 'installation_hardening_check.json'
    if installation_check.exists():
        if read(installation_check).get('status') != 'passed':
            raise RuntimeError('Installation hardening check has not passed.')
        command = [sys.executable, str(ROOT / 'bench_hardened.py'), *command[1:]]
    row = {'candidate': candidate, 'task_index': task_index, 'task': task['name'], 'status': 'started',
           'key_usage_before_usd': before, 'jobs_dir': str(jobs), 'command': command}
    state['records'].append(row)
    save(state_path, state)
    print('PAID TASK:', state['method'], candidate, task['name'], state['configs'][candidate], flush=True)
    env = dict(os.environ, LITELLM_API_KEY=key, LITELLM_BASE_URL='https://openrouter.ai/api/v1')
    try:
        row['returncode'] = subprocess.run(command, cwd=repo, env=env).returncode
        paths = sorted(jobs.rglob('result.json'))
        row['result_paths'] = [str(p) for p in paths]
        if len(paths) == 1:
            diagnostic = read(paths[0])
            row['error'] = diagnostic.get('error')
            row['error_category'] = diagnostic.get('error_category')
            row['verifier_error'] = diagnostic.get('verifier_error')
        if row['returncode'] != 0 or len(paths) != 1:
            row['status'] = 'run_failed'
            raise RuntimeError('Run failed or result count is not one; no automatic retry.')
        result = read(paths[0])
        row['error'] = result.get('error')
        row['verifier_error'] = result.get('verifier_error')
        reward = (result.get('rewards') or {}).get('reward')
        if row['error'] or row['verifier_error'] or not isinstance(reward, (int, float)) or not math.isfinite(reward):
            raise RuntimeError('Infrastructure/verifier error or missing reward; inspect raw logs.')
        row['reward'] = reward
        row['strict_pass'] = reward == 1
        row['status'] = 'billing_pending'
    finally:
        save(state_path, state)
    snapshots = []
    # Longer billing observation than the baseline runner; still not proof of final settlement.
    for delay in (0, 20, 20, 20):
        time.sleep(delay)
        snapshots.append(usage(key))
        row['usage_snapshots_usd'] = snapshots
        save(state_path, state)
    delta = snapshots[-1] - before
    if delta <= 0 or len(set(snapshots[-3:])) != 1:
        raise RuntimeError('Billing unresolved; stopped. Inspect this record before any further paid run.')
    row['cost_usd'] = delta
    row['status'] = 'complete'
    save(state_path, state)
    print('Recorded reward:', reward, 'observed USD:', delta, flush=True)


def reconcile_billing(state_path, key):
    """Query account metadata only; never launch or retry a benchmark task."""
    lock = ROOT / 'search.lock'
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(str(os.getpid()))
    try:
        state = read(state_path)
        pending = [r for r in state['records'] if not resolved(r)]
        if not pending:
            print('No pending billing. No model call made.')
            return
        if len(pending) != 1 or pending[0] is not state['records'][-1]:
            raise RuntimeError('Multiple or non-final unresolved records require manual audit.')
        row = pending[0]
        if row['status'] != 'billing_pending' or row.get('returncode') != 0 or 'reward' not in row:
            raise RuntimeError('Task result is not ready for billing-only reconciliation.')
        before = row['key_usage_before_usd']
        for other_path in ROOT.glob('*_state.json'):
            for other in read(other_path)['records']:
                if other.get('jobs_dir') != row['jobs_dir'] and other.get('key_usage_before_usd', -1) >= before:
                    raise RuntimeError('A later experiment may contaminate this usage delta; manual audit required.')
        backup = state_path.with_name(state_path.stem + '.before_billing_reconciliation.json')
        if not backup.exists():
            backup.write_bytes(state_path.read_bytes())
        audit = {'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                 'assumption': 'User asserts exclusive key use and no unrelated delayed charges.',
                 'usage_snapshots_usd': []}
        row.setdefault('billing_reconciliation_attempts', []).append(audit)
        save(state_path, state)
        print('Checking billing only (about 40 seconds). No model calls.', flush=True)
        for delay in (0, 20, 20):
            time.sleep(delay)
            audit['usage_snapshots_usd'].append(usage(key))
            save(state_path, state)
        snapshots = audit['usage_snapshots_usd']
        if len(set(snapshots)) != 1 or snapshots[-1] <= before:
            raise RuntimeError('Billing still unresolved; state remains pending. No task was rerun.')
        if snapshots[-1] < max(row.get('usage_snapshots_usd', [before])):
            raise RuntimeError('Usage decreased; manual accounting audit required.')
        row['cost_usd'] = snapshots[-1] - before
        row['status'] = 'complete'
        save(state_path, state)
        print('Billing reconciled. Observed USD:', row['cost_usd'])
        print('Records:', len(state['records']), '/ 9. No model call made.')
    finally:
        lock.unlink()


def is_docker_build_timeout(result):
    """Narrow pre-agent failure: Ubuntu metadata authorization timed out."""
    error = result.get('error') or ''
    return (result.get('error_category') == 'other'
            and result.get('sandbox_id') is None
            and result.get('trajectory_summary', {}).get('steps') == 0
            and result.get('agent_result', {}).get('total_tokens') == 0
            and any('load metadata for docker.io/library/' + base in error
                    for base in ('ubuntu:24.04', 'python:3.12-slim'))
            and all(part in error for part in (
                'Docker compose command failed', ' build. Return code: 1.',
                'failed to authorize: DeadlineExceeded: context deadline exceeded')))


def prepare_failed_retry(state, state_path, protocol, key):
    """Called under the global lock. Archive one eligible failure, never erase it."""
    if state.get('failed_attempts'):
        raise RuntimeError('One extra attempt per method already used; no further retry allowed.')
    pending = [r for r in state['records'] if r['status'] != 'complete']
    if len(pending) != 1 or pending[0] is not state['records'][-1]:
        raise RuntimeError('Expected exactly one unresolved final attempt.')
    row = pending[0]
    if row.get('returncode') in (None, 0) or row['status'] not in ('started', 'run_failed'):
        raise RuntimeError('Only a finished failed process is eligible; billing-pending and scored runs cannot be retried.')
    paths = row.get('result_paths', [])
    if len(paths) != 1:
        raise RuntimeError('One original result.json is required.')
    result_path = Path(paths[0])
    if not result_path.resolve().is_relative_to(Path(row['jobs_dir']).resolve()):
        raise RuntimeError('Result path is outside original job directory.')
    result = read(result_path)
    docker_timeout = is_docker_build_timeout(result)
    if ((result.get('error_category') != 'suspected_api_error' and not docker_timeout) or result.get('rewards') is not None
            or result.get('n_tool_calls') != 0 or result.get('verifier_error')
            or result.get('task_name') != row['task']):
        raise RuntimeError('Failure does not meet the recovery policy; manual diagnosis required.')
    config = state['configs'][row['candidate']]
    expected_model = dict(id='qwen/qwen3-coder', reasoning=False, input=['text'], **config)
    expected_env = 'BENCHFLOW_PROVIDER_MODELS=' + json.dumps([expected_model], separators=(',', ':'))
    if expected_env not in row['command'] or protocol['validation'][row['task_index']]['name'] != row['task']:
        raise RuntimeError('Original task/config does not match; refusing retry.')
    before = row['key_usage_before_usd']
    for other_path in ROOT.glob('*_state.json'):
        for other in read(other_path)['records']:
            if other.get('jobs_dir') != row['jobs_dir'] and other.get('key_usage_before_usd', -1) >= before:
                raise RuntimeError('Another experiment may contaminate billing; manual audit required.')
    policy_path = ROOT / 'recovery_policy.json'
    if policy_path.exists() and read(policy_path) != RECOVERY_POLICY:
        raise RuntimeError('Recovery policy differs.')
    backup = state_path.with_name(state_path.stem + '.before_failed_retry.json')
    if not backup.exists():
        backup.write_bytes(state_path.read_bytes())
    save(policy_path, RECOVERY_POLICY)
    if docker_timeout:
        save(ROOT / 'docker_recovery_amendment.json', {
            'declared_after': 'Multi-fidelity third launch failed during Ubuntu metadata authorization, before any scored result.',
            'applies_to': ['random', 'bayesian', 'multifidelity'],
            'eligibility': 'Verified Ubuntu metadata authorization timeout; no sandbox, trajectory steps, tokens, tools, or reward.',
            'limits': 'Uses the existing single extra attempt per method and ten-launch cap. Same task/config; archive raw result and account observed costs.',
        })
    audit = {'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
             'exclusive_key_asserted': True, 'usage_snapshots_usd': []}
    row.setdefault('failure_billing_checks', []).append(audit)
    save(state_path, state)
    print('Checking failed-attempt billing for 40 seconds before ONE explicit retry.', flush=True)
    for delay in (0, 20, 20):
        time.sleep(delay)
        audit['usage_snapshots_usd'].append(usage(key))
        save(state_path, state)
    snapshots = audit['usage_snapshots_usd']
    if len(set(snapshots)) != 1 or snapshots[-1] < before:
        raise RuntimeError('Failed-attempt billing not stable; no retry started.')
    delta = snapshots[-1] - before
    spent = sum(r['cost_usd'] for r in state['records'][:-1]) + delta
    if spent + protocol['admission_reserve_usd'] > protocol['usd_limit_per_method'] or snapshots[-1] >= protocol['key_usage_stop_usd']:
        raise RuntimeError('Budget admission stopped; no retry started.')
    row['original_status'] = row['status']
    row['status'] = 'archived_docker_build_failure' if docker_timeout else 'archived_api_failure'
    row['raw_result'] = result
    row['result_sha256'] = hashlib.sha256(result_path.read_bytes()).hexdigest()
    row['cost_usd'] = delta
    row['cost_note'] = 'Observed dedicated-key delta; zero is not confirmation of free usage.'
    state.setdefault('failed_attempts', []).append(row)
    state['records'].pop()
    state['recovery_policy_version'] = RECOVERY_POLICY['version']
    save(state_path, state)
    print('Failure preserved; retry will use the same task and configuration.', flush=True)


def skip_failed(state_path, key):
    """Close a verified API failure as missing, retaining its slot and all evidence."""
    lock = ROOT / 'search.lock'
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(str(os.getpid()))
    try:
        state = read(state_path)
        pending = [r for r in state['records'] if not resolved(r)]
        if not pending:
            print('No unresolved attempt. No task started.')
            return
        if len(pending) != 1 or pending[0] is not state['records'][-1]:
            raise RuntimeError('Expected exactly one unresolved final attempt.')
        row = pending[0]
        if row['status'] not in ('started', 'run_failed') or row.get('returncode') in (None, 0):
            raise RuntimeError('Cannot skip a running, scoreable, or billing-pending evaluation.')
        if len(row.get('result_paths', [])) != 1:
            raise RuntimeError('Original result.json required.')
        result_path = Path(row['result_paths'][0])
        if not result_path.resolve().is_relative_to(Path(row['jobs_dir']).resolve()):
            raise RuntimeError('Result path outside job directory.')
        raw = result_path.read_bytes()
        result = json.loads(raw)
        docker_timeout = is_docker_build_timeout(result)
        if ((result.get('error_category') != 'suspected_api_error' and not docker_timeout) or result.get('rewards') is not None
                or result.get('n_tool_calls') != 0 or result.get('task_name') != row['task']):
            raise RuntimeError('Only verified unscored suspected API failures can be skipped.')
        before = row['key_usage_before_usd']
        for other_path in ROOT.glob('*_state.json'):
            for other in read(other_path)['records']:
                if other.get('jobs_dir') != row['jobs_dir'] and other.get('key_usage_before_usd', -1) >= before:
                    raise RuntimeError('Another search may overlap this interval; manual accounting required.')
        backup = state_path.with_name(state_path.stem + '.before_skip_' + str(len(state['records'])) + '.json')
        if not backup.exists():
            backup.write_bytes(state_path.read_bytes())
        policy = {'version': 1, 'declared_after': 'Second Random API failure and subsequent diagnostic probes.',
                  'applies_to': ['random', 'bayesian', 'multifidelity'],
                  'rule': 'Explicitly skip unscored API failures; retain task slot and ten-launch cap. Do not impute zero reward. Select only candidates completing all three validation tasks.',
                  'accounting': 'Post-failure key usage may include diagnostics. Charge the whole observed interval conservatively against admission budget, separately from candidate scoring costs.'}
        policy_path = ROOT / 'missing_result_policy.json'
        if policy_path.exists() and read(policy_path) != policy:
            raise RuntimeError('Missing-result policy changed.')
        save(policy_path, policy)
        if docker_timeout:
            save(ROOT / 'docker_missing_result_amendment.json', {
                'declared_after': 'Multi-fidelity seventh launch failed fetching python:3.12-slim metadata.',
                'applies_to': ['random', 'bayesian', 'multifidelity'],
                'rule': 'Verified pre-agent Docker metadata timeout may consume its slot as missing. No extra retry. Preserve raw result and budget interval; incomplete candidates remain ineligible.',
            })
        audit = {'timestamp_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'snapshots_usd': []}
        row.setdefault('skip_accounting_checks', []).append(audit)
        save(state_path, state)
        print('Checking usage for 40 seconds; no model calls. Diagnostic spending stays separate from task cost.', flush=True)
        for delay in (0, 20, 20):
            time.sleep(delay)
            audit['snapshots_usd'].append(usage(key))
            save(state_path, state)
        values = audit['snapshots_usd']
        if len(set(values)) != 1 or values[-1] < before:
            raise RuntimeError('Usage not stable; no task skipped or launched.')
        row.update(status='skipped_docker_failure' if docker_timeout else 'skipped_api_failure', original_status=row['status'], raw_result=result,
                   result_sha256=hashlib.sha256(raw).hexdigest(), reward=None, strict_pass=None, cost_usd=None,
                   unattributed_interval_usd=values[-1] - before,
                   cost_note='Unattributed observed interval includes possible failed-task and diagnostic charges; not an exact task cost.')
        state['missing_result_policy_version'] = 1
        save(state_path, state)
        print('Failure preserved as MISSING, not zero. No model call made.')
        print('Valid evaluations:', sum(r['status'] == 'complete' for r in state['records']),
              'Missing:', sum(resolved(r) and r['status'] != 'complete' for r in state['records']))
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=['random', 'bayesian', 'multifidelity'], default='random')
    parser.add_argument('--source', type=Path, default=OLD)
    parser.add_argument('--repo', type=Path, default=Path.home() / 'pe6203-linux/skillsbench')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--reconcile-billing', action='store_true')
    parser.add_argument('--retry-failed', action='store_true', help='Explicitly retry one eligible API failure; requires --execute --exclusive-key.')
    parser.add_argument('--skip-failed', action='store_true', help='Preserve an API failure as missing; no model calls. Key usage gap includes diagnostics.')
    parser.add_argument('--exclusive-key', action='store_true', help='Assert no other key use or unrelated delayed charges during the pending interval.')
    parser.add_argument('--max-new-tasks', type=int, choices=range(1, 10), default=1)
    args = parser.parse_args()
    if args.skip_failed and (args.execute or args.retry_failed or args.reconcile_billing or not args.exclusive_key):
        parser.error('--skip-failed requires --exclusive-key and cannot be combined with other actions')
    if args.retry_failed and (not args.execute or not args.exclusive_key or args.reconcile_billing or args.max_new_tasks != 1):
        parser.error('--retry-failed requires --execute --exclusive-key --max-new-tasks 1, without --reconcile-billing')
    protocol = frozen_protocol(args.source)
    state_path = ROOT / (args.method + '_state.json')
    protocol_path = ROOT / 'protocol.json'
    if protocol_path.exists() and read(protocol_path) != protocol:
        raise SystemExit('Frozen protocol differs; refusing to continue.')
    state = read(state_path) if state_path.exists() else initial_state(args.method, protocol)
    if state['protocol_sha256'] != initial_state(args.method, protocol)['protocol_sha256']:
        raise SystemExit('State protocol mismatch.')
    if args.skip_failed:
        key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if not key:
            raise SystemExit('OPENROUTER_API_KEY missing.')
        skip_failed(state_path, key)
        return
    if args.reconcile_billing:
        if args.execute or not args.exclusive_key:
            raise SystemExit('Use --reconcile-billing --exclusive-key without --execute; no model call needed.')
        key = os.environ.get('OPENROUTER_API_KEY', '').strip()
        if not key:
            raise SystemExit('OPENROUTER_API_KEY missing.')
        reconcile_billing(state_path, key)
        return
    if not args.retry_failed and any(not resolved(r) for r in state['records']):
        raise SystemExit('Unresolved prior run: inspect ' + str(state_path) + '; no automatic retry.')
    pair = next_pair(state, protocol)
    if not args.execute:
        print(json.dumps({'mode': 'OFFLINE PREVIEW', 'paid_tasks_started': 0, 'method': args.method,
                          'next_pair': pair, 'configs': state['configs'], 'protocol': protocol}, indent=2))
        return
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    bench = shutil.which('bench')
    if not key or not bench:
        raise SystemExit('OPENROUTER_API_KEY or bench missing.')
    if not (ROOT / 'installation_hardening_check.json').exists() or read(ROOT / 'installation_hardening_check.json').get('status') != 'passed':
        raise SystemExit('Run bench_hardened.py --check-install successfully before starting another task. No task started.')
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.repo, text=True).strip() != protocol['benchmark_commit']:
        raise SystemExit('Benchmark commit mismatch.')
    for task in protocol['validation']:
        if hashlib.sha256((args.repo / 'tasks' / task['name'] / 'task.md').read_bytes()).hexdigest() != task['definition_sha256']:
            raise SystemExit('Task definition changed.')
    if subprocess.check_output(['docker', 'info', '--format', '{{.OSType}}'], text=True).strip() != 'linux':
        raise SystemExit('Docker Linux engine unavailable.')
    # Global exclusive lock across methods. A crash leaves it for manual inspection.
    lock = ROOT / 'search.lock'
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(str(os.getpid()))
    try:
        # Another invocation may have finished between preview and lock acquisition.
        if protocol_path.exists() and read(protocol_path) != protocol:
            raise RuntimeError('Frozen protocol changed before lock acquisition.')
        if state_path.exists():
            state = read(state_path)
            if state['protocol_sha256'] != initial_state(args.method, protocol)['protocol_sha256']:
                raise RuntimeError('State protocol mismatch.')
            if args.retry_failed:
                prepare_failed_retry(state, state_path, protocol, key)
            if any(not resolved(r) for r in state['records']):
                raise RuntimeError('Unresolved prior run; no automatic retry.')
        save(protocol_path, protocol)
        save(state_path, state)
        for _ in range(args.max_new_tasks):
            pair = next_pair(state, protocol)
            save(state_path, state)
            if pair is None:
                break
            run_task(state, protocol, pair, args.repo, bench, key, state_path)
        completed = [i for i in range(len(state['configs'])) if len([r for r in state['records'] if r['candidate'] == i and r['status'] == 'complete']) == 3]
        if len(state['records']) == 9 and completed:
            best = max(completed, key=lambda i: score(state, i))
            state['selected'] = {'candidate': best, 'config': state['configs'][best], 'validation_pass_rate': score(state, best)[0] / 3}
            save(state_path, state)
        state['progress'] = {'valid_evaluations': sum(r['status'] == 'complete' for r in state['records']),
                             'missing_evaluations': sum(resolved(r) and r['status'] != 'complete' for r in state['records']),
                             'task_launches': len(state['records']) + len(state.get('failed_attempts', [])),
                             'budget_accounted_usd': accounted_cost(state)}
        if len(state['records']) == 9:
            state['completion_status'] = 'finished_with_missing_results' if state['progress']['missing_evaluations'] else 'complete'
        save(state_path, state)
        print('Progress:', json.dumps(state['progress']))
        print('Stopped safely. Records:', len(state['records']), '/ 9. Test tasks started: 0.')
        print('Archived failed attempts:', len(state.get('failed_attempts', [])))
        print('State:', state_path)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
