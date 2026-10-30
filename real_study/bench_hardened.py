"""BenchFlow CLI with installation-only hardening; no changes to agent logic."""
import dataclasses
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shlex
import subprocess
import sys


def harden(command):
    boundary = ' && export DEBIAN_FRONTEND=noninteractive;'
    if command.count(boundary) != 1:
        raise RuntimeError('Unexpected installer structure; refusing to patch.')
    if '@earendil-works/pi-coding-agent@0.81.0' not in command or 'pi-acp@0.0.34' not in command:
        raise RuntimeError('Required version pins missing.')
    first, second = command.split(boundary)
    retry = 'curl --retry 2 --retry-all-errors --retry-delay 2 --connect-timeout 20 --max-time 180 -fsSLo'
    parts = [first, 'export DEBIAN_FRONTEND=noninteractive;' + second]
    apt = 'apt-get -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 -o Acquire::Retries=1 -o APT::Update::Error-Mode=any'
    parts = [p.replace('curl -fsSLo', retry).replace('apt-get update', apt + ' update').replace('apt-get install', apt + ' install')
             .replace('npm install -g', 'npm --fetch-retries=2 --fetch-timeout=60000 install -g') for p in parts]
    result = ' && '.join('sh -eu -c ' + shlex.quote(p) for p in parts)
    checks = '''
test -x /opt/benchflow/bin/pi && test -x /opt/benchflow/bin/pi-acp &&
test "$(/opt/benchflow/node/bin/node --version)" = v22.20.0 &&
test "$(/opt/benchflow/bin/pi --version)" = 0.81.0 &&
/opt/benchflow/node/bin/node -e 'const fs=require("fs"); const p=JSON.parse(fs.readFileSync("/opt/benchflow/js-agents/lib/node_modules/pi-acp/package.json","utf8")); if(p.version!=="0.0.34")process.exit(1)' &&
echo 'PE6203 installation checks passed'
'''
    return result + ' && sh -eu -c ' + shlex.quote(checks)


def main():
    if importlib.metadata.version('benchflow') != '0.6.3':
        raise RuntimeError('Expected BenchFlow 0.6.3.')
    from benchflow.agents.registry import AGENTS
    original = AGENTS['pi-acp'].install_cmd
    hardened = harden(original)
    AGENTS['pi-acp'] = dataclasses.replace(AGENTS['pi-acp'], install_cmd=hardened)
    if sys.argv[1:] == ['--check-install']:
        print('Disposable Ubuntu installation check. No credentials or model requests.', flush=True)
        evidence_path = Path(__file__).parent / 'installation_hardening_check.json'
        evidence_path.write_text(json.dumps({'status': 'pending', 'model_calls': 0}) + '\n')
        try:
            subprocess.run(['docker', 'run', '--rm', 'ubuntu:24.04', 'sh', '-eu', '-c', hardened], check=True, timeout=900)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            evidence_path.write_text(json.dumps({'status': 'failed', 'model_calls': 0, 'reason': type(error).__name__}) + '\n')
            raise SystemExit('Installation check failed; do not start benchmark tasks. Inspect download output and rerun --check-install after connectivity recovers.') from None
        evidence = {'status': 'passed', 'benchflow': '0.6.3', 'node': '22.20.0', 'pi': '0.81.0', 'pi_acp': '0.0.34',
                    'original_install_sha256': hashlib.sha256(original.encode()).hexdigest(),
                    'hardened_install_sha256': hashlib.sha256(hardened.encode()).hexdigest(),
                    'model_calls': 0, 'note': 'Installation-only amendment after multifidelity sixth evaluation; same pins and agent logic. Fresh task containers still depend on network.'}
        evidence_path.write_text(json.dumps(evidence, indent=2) + '\n')
        return
    from benchflow.cli.main import app
    app()


if __name__ == '__main__':
    main()
