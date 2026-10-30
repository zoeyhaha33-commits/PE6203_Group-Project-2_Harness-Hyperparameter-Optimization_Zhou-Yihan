"""Build unchanged held-out task environments without credentials/model requests."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
TASKS = ('python-scala-translation', 'reserves-at-risk-calc', 'threejs-structure-parser')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=TASKS, default=TASKS[0])
    parser.add_argument('--execute', action='store_true', help='Build image only; no benchmark or model call.')
    parser.add_argument('--use-vpn-proxy', action='store_true',
                        help='Use the verified Windows HTTP proxy on host.docker.internal:10809 for build downloads only.')
    parser.add_argument('--build-timeout', type=int, choices=range(300, 3601), default=1800,
                        help='Preparation-only wall-clock limit in seconds; does not change benchmark task limits.')
    args = parser.parse_args()
    repo = Path.home() / 'pe6203-linux/skillsbench'
    context = repo / 'tasks' / args.task / 'environment'
    image = 'pe6203-test-prepared:' + args.task
    command = ['docker', 'build', '--progress=plain', '-t', image]
    if args.use_vpn_proxy:
        for variable in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
            command += ['--build-arg', variable + '=http://host.docker.internal:10809']
    command += [str(context)]
    if not args.execute:
        print(json.dumps({'mode': 'preview', 'task': args.task, 'command': command, 'model_calls': 0}, indent=2))
        return
    if (ROOT / 'search.lock').exists():
        raise SystemExit('An evaluation is active; finish it first.')
    protocol = json.loads((ROOT / 'final_test_protocol.json').read_text())
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    assert commit == protocol['benchmark_commit'], 'Benchmark commit changed.'
    record = {'task': args.task, 'image': image, 'command': command, 'commit': commit,
              'dockerfile_sha256': hashlib.sha256((context / 'Dockerfile').read_bytes()).hexdigest(),
              'model_calls': 0, 'build_timeout_sec': args.build_timeout,
              'uses_verified_vpn_proxy': args.use_vpn_proxy,
              'note': 'Unmodified task Dockerfile/context; BuildKit cache only. Preparation timeout does not change benchmark limits or authorize test retries.'}
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'test_image_checks' / (stamp + '_' + args.task)
    output.mkdir(parents=True)
    print('Building environment only. Model calls: 0. Log:', output / 'build.log', flush=True)
    start = time.monotonic()
    with (output / 'build.log').open('w') as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=args.build_timeout)
            record['returncode'] = result.returncode
            record['status'] = 'passed' if result.returncode == 0 else 'failed'
        except subprocess.TimeoutExpired:
            record['status'] = 'build_timeout'
            record['reason'] = 'Preparation wall-clock limit reached; this alone does not establish a package installation error.'
    record['elapsed_sec'] = round(time.monotonic() - start, 1)
    if record['status'] == 'passed':
        record['image_id'] = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
    (output / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    if record['status'] != 'passed':
        lines = (output / 'build.log').read_text(errors='replace').splitlines()
        print('\n'.join(lines[-35:]))
        raise SystemExit('Environment not ready. Do not start model evaluation.')


if __name__ == '__main__':
    main()
