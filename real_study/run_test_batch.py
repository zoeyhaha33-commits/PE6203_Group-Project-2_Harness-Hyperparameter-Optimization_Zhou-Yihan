"""Run remaining test slots for one method serially; stop on the first error."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from run_search import resolved

ROOT = Path(__file__).resolve().parent
METHODS = ('default', 'random', 'bayesian', 'multifidelity')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def pending_guard():
    for p in ROOT.glob('test_*_state.json'):
        if any(not resolved(r) for r in read(p)['records']):
            raise RuntimeError('Unresolved test record: ' + str(p) + '. Audit it before continuing; no automatic retries.')


def run_batch(method):
    pending_guard()
    p = ROOT / f'test_{method}_state.json'
    count = len(read(p)['records']) if p.exists() else 0
    while count < 3:
        print(f'Batch {method}: starting slot {count + 1}/3', flush=True)
        subprocess.run([sys.executable, str(ROOT / 'run_test.py'), '--method', method, '--execute'], check=True)
        pending_guard()
        new_count = len(read(p)['records'])
        if new_count != count + 1:
            raise RuntimeError('Unexpected test progress; stopping.')
        count = new_count
    print(f'Batch {method}: all three test slots completed. No configuration changed.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=METHODS, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        p = ROOT / f'test_{args.method}_state.json'
        rows = read(p)['records'] if p.exists() else []
        print(json.dumps({'mode': 'OFFLINE PREVIEW', 'method': args.method, 'model_calls': 0,
                          'recorded_slots': len(rows), 'maximum_remaining_slots': 3 - len(rows),
                          'execution': 'serial; wait for billing after every task; stop on error; never retry started slots'}, indent=2))
        return
    # No model requests until every original task image has successfully built.
    protocol = read(ROOT / 'final_test_protocol.json')
    for task in protocol['test']:
        found = False
        for p in (ROOT / 'test_image_checks').glob('*/result.json'):
            result = read(p)
            if result.get('task') == task['name'] and result.get('status') == 'passed' and result.get('commit') == protocol['benchmark_commit']:
                image = subprocess.run(['docker', 'image', 'inspect', result['image_id']], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if image.returncode == 0:
                    found = True
                    break
        if not found:
            raise SystemExit('No successful cached environment preparation for ' + task['name'] + '; no test started.')
    try:
        run_batch(args.method)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit('Batch stopped: ' + str(error)) from None


if __name__ == '__main__':
    main()
