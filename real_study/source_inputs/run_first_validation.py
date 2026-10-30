"""One default-configuration validation task, with persisted cost accounting."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from calibrate_real_run import metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task-index', type=int, choices=(0, 1, 2), default=0)
    args = parser.parse_args()
    shared = Path(__file__).resolve().parent
    plan = json.loads((shared / 'small_study_plan.json').read_text(encoding='utf-8'))
    repo = Path.home() / 'pe6203-linux/skillsbench'
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise SystemExit('API key absent in this terminal; no task started.')
    task = plan['validation'][args.task_index]
    raw = (repo / 'tasks' / task['name'] / 'task.md').read_bytes()
    if hashlib.sha256(raw).hexdigest() != task['definition_sha256']:
        raise SystemExit('Task definition changed; no task started.')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    if commit != plan['benchmark_commit']:
        raise SystemExit('Benchmark commit changed; no task started.')
    docker = subprocess.run(['docker', 'info', '--format', '{{.OSType}}'], capture_output=True, text=True)
    if docker.returncode or docker.stdout.strip() != 'linux':
        raise SystemExit('Docker Linux engine unavailable; no task started.')
    bench = shutil.which('bench')
    if not bench:
        raise SystemExit('bench absent; no task started.')
    # Refuse accidental paid repeats, including after a crash.
    folder = shared / 'validation_baseline'
    folder.mkdir(exist_ok=True)
    marker = folder / ('first_task.json' if args.task_index == 0 else f'task_{args.task_index + 1}.json')
    if marker.exists():
        raise SystemExit(f'This task has already been started. Inspect {marker}; no automatic repeat.')
    spent = 0.0
    for previous in (folder / name for name in ('first_task.json', 'task_2.json', 'task_3.json')):
        if not previous.exists():
            continue
        prior = json.loads(previous.read_text(encoding='utf-8'))
        delta = prior.get('observed_cost_delta_usd')
        if not isinstance(delta, (int, float)) or delta <= 0:
            raise SystemExit('Previous run cost unresolved; no additional paid task started.')
        spent += delta
    if spent + 0.20 > plan['budget_allocations_usd']['default_validation']:
        raise SystemExit('Baseline allocation lacks USD 0.20 admission reserve; no task started.')
    before = metadata(key).get('usage')
    if not isinstance(before, (int, float)) or before >= 7.75:
        raise SystemExit('Usage unavailable or project reserve reached; no task started.')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    jobs = repo / 'jobs' / ('validation-default-' + stamp)
    command = [bench, 'eval', 'run', '--tasks-dir', 'tasks/' + task['name'],
               '--agent', 'pi', '--model', plan['fixed']['model'], '--sandbox', 'docker',
               '--skill-mode', 'no-skill', '--loop-strategy', 'single-shot',
               '--concurrency', '1', '--jobs-dir', str(jobs)]
    record = {'phase': 'validation', 'method': 'default', 'task': task['name'],
              'benchmark_commit': commit, 'status': 'started', 'jobs_dir': str(jobs),
              'key_usage_before_usd': before, 'settings_override': None,
              'test_tasks_started': 0, 'command': command,
              'budget_note': 'One task only; USD 0.50 baseline allocation is not a provider-enforced hard cap. Dedicated key required.'}

    def save():
        marker.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # Exclusive creation protects against two invocations starting together.
    with marker.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
    env = dict(os.environ, LITELLM_API_KEY=key, LITELLM_BASE_URL='https://openrouter.ai/api/v1')
    print('Running ONE validation task with default settings:', task['name'], flush=True)
    print('Do not use this key for other requests during accounting. Report:', marker, flush=True)
    try:
        record['returncode'] = subprocess.run(command, cwd=repo, env=env).returncode
    finally:
        record['status'] = 'process_finished_or_interrupted'
        record['results'] = []
        for path in sorted(jobs.rglob('result.json')):
            result = json.loads(path.read_text(encoding='utf-8'))
            reward = (result.get('rewards') or {}).get('reward')
            record['results'].append({'path': str(path), 'reward': reward,
                                      'strict_pass': reward == 1 and not result.get('error') and not result.get('verifier_error'),
                                      'error': result.get('error'), 'verifier_error': result.get('verifier_error'),
                                      'tool_calls': (result.get('agent_result') or {}).get('n_tool_calls')})
        save()
        snapshots = []
        for delay in (0, 10, 20):
            time.sleep(delay)
            try:
                snapshots.append(metadata(key).get('usage'))
            except Exception as exc:
                record['billing_query_error_type'] = type(exc).__name__
        valid = [v for v in snapshots if isinstance(v, (int, float))]
        record['key_usage_after_snapshots_usd'] = snapshots
        record['observed_cost_delta_usd'] = max(valid) - before if valid else None
        record['cost_note'] = 'Delayed billing and concurrent requests can affect deltas; missing or zero delta is not confirmed free usage.'
        save()
        print('Observed cost USD:', record['observed_cost_delta_usd'])
        print('Results:', record['results'])
        print('Finished. No further validation or test task will start automatically.')


if __name__ == '__main__':
    main()
