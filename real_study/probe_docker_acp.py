"""Build a separate fixed-version diagnostic image; optionally run one ACP prompt."""
import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='Build diagnostic image only; no model call.')
    parser.add_argument('--execute', action='store_true', help='Build if needed and send one optional paid ACP diagnostic prompt.')
    parser.add_argument('--self-test', action='store_true', help='Run ACP against a mock provider inside Docker; no real model calls.')
    args = parser.parse_args()
    if args.execute and args.self_test:
        parser.error('--execute and --self-test cannot be combined')
    if not args.prepare and not args.execute and not args.self_test:
        print('Use --prepare for image preparation only, or --execute for one paid diagnostic prompt. No action taken.')
        return
    if os.name == 'nt':
        raise SystemExit('Run with the BenchFlow Python interpreter inside WSL.')
    if (ROOT / 'search.lock').exists():
        raise SystemExit('Search is active; wait for it to finish.')
    if importlib.metadata.version('benchflow') != '0.6.3':
        raise SystemExit('Expected BenchFlow 0.6.3.')
    from benchflow.agents.registry import AGENTS
    install = AGENTS['pi-acp'].install_cmd
    if '@earendil-works/pi-coding-agent@0.81.0' not in install or 'pi-acp@0.0.34' not in install:
        raise SystemExit('Installed registry does not contain the required version pins.')
    context = ROOT / 'docker_probe_build'
    context.mkdir(exist_ok=True)
    (context / 'install.sh').write_text('#!/bin/sh\nset -eu\n' + install + '\n')
    for name in ('pi_capture.py', 'acp_probe_inside.py'):
        shutil.copyfile(ROOT / name, context / name)
    dockerfile = '''FROM python:3.12-slim-bookworm
COPY install.sh /tmp/install.sh
RUN sh /tmp/install.sh
COPY pi_capture.py /opt/diagnostic/pi_capture.py
COPY acp_probe_inside.py /opt/diagnostic/acp_probe_inside.py
RUN mv /opt/benchflow/bin/pi /opt/benchflow/bin/pi-original && printf '#!/bin/sh\\nexec python3 /opt/diagnostic/pi_capture.py "$@"\\n' > /opt/benchflow/bin/pi && chmod +x /opt/benchflow/bin/pi && mkdir /work /out
WORKDIR /work
ENTRYPOINT ["python3", "/opt/diagnostic/acp_probe_inside.py"]
'''
    (context / 'Dockerfile').write_text(dockerfile)
    digest = hashlib.sha256(b''.join((context / n).read_bytes() for n in ('Dockerfile', 'install.sh', 'pi_capture.py', 'acp_probe_inside.py'))).hexdigest()[:16]
    image = 'pe6203-acp-diagnostic:' + digest
    found = subprocess.run(['docker', 'image', 'inspect', image], capture_output=True)
    if found.returncode:
        print('Building isolated diagnostic image. No model calls during build.', flush=True)
        subprocess.run(['docker', 'build', '-t', image, str(context)], check=True)
    if not args.execute and not args.self_test:
        print('Image ready:', image, '\nModel calls: 0')
        return
    key = 'offline-test-key' if args.self_test else os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise SystemExit('OPENROUTER_API_KEY missing; no model call.')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT / ('docker_acp_probe_' + stamp)
    output.mkdir()
    name = 'pe6203-acp-probe-' + stamp.lower()
    env = dict(os.environ, BENCHFLOW_PROVIDER_API_KEY=key,
               PE6203_OFFLINE_SELF_TEST='1' if args.self_test else '0',
               BENCHFLOW_PROVIDER_PROTOCOL='openai-completions',
               BENCHFLOW_PROVIDER_BASE_URL='https://openrouter.ai/api/v1',
               BENCHFLOW_PROVIDER_NAME='benchflow-qwen', BENCHFLOW_PROVIDER_MODEL='qwen/qwen3-coder',
               BENCHFLOW_PROVIDER_MODELS=json.dumps([{'id': 'qwen/qwen3-coder', 'contextWindow': 128000,
                   'maxTokens': 16, 'reasoning': False, 'input': ['text']}]))
    command = ['docker', 'run', '--rm', '--name', name, '--mount', f'type=bind,source={output},target=/out']
    for variable in ('PE6203_OFFLINE_SELF_TEST', 'BENCHFLOW_PROVIDER_API_KEY', 'BENCHFLOW_PROVIDER_PROTOCOL', 'BENCHFLOW_PROVIDER_BASE_URL',
                     'BENCHFLOW_PROVIDER_NAME', 'BENCHFLOW_PROVIDER_MODEL', 'BENCHFLOW_PROVIDER_MODELS'):
        command += ['-e', variable]
    command.append(image)
    print('OFFLINE MOCK SELF-TEST.' if args.self_test else 'ONE optional paid ACP prompt, max output 16 tokens.', 'Logs:', output, flush=True)
    try:
        subprocess.run(command, env=env, timeout=240, check=True)
    finally:
        # Only this uniquely named disposable diagnostic container is removed.
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    print('Diagnostic finished; no benchmark task launched; search state unchanged.')
    if args.self_test:
        report = json.loads((output / 'summary.json').read_text())
        requests = report.get('offline_mock_requests', [])
        if report['status'] != 'ok' or len(requests) != 1 or (requests[0].get('max_tokens') or requests[0].get('max_completion_tokens')) != 16:
            raise SystemExit('Offline ACP self-test failed; inspect logs.')
        print('PASS: Docker -> launcher -> ACP -> Pi -> mock streaming provider; one request, output cap 16.')


if __name__ == '__main__':
    main()
