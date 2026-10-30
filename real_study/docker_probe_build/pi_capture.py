#!/usr/bin/env python3
"""Diagnostic-only transparent Pi stdout capture; installed inside probe image."""
import os
import subprocess
import sys
import threading

key = os.environ.get('BENCHFLOW_PROVIDER_API_KEY', '')
def scrub(data):
    return data.replace(key.encode(), b'[REDACTED]') if key else data

process = subprocess.Popen(['/opt/benchflow/bin/pi-original', *sys.argv[1:], '--no-tools', '--no-extensions'],
                           stdin=sys.stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def relay(source, destination, path):
    with open(path, 'ab', buffering=0) as log:
        for line in iter(source.readline, b''):
            log.write(scrub(line))
            destination.write(line)
            destination.flush()

threads = [threading.Thread(target=relay, args=(process.stdout, sys.stdout.buffer, '/out/pi-rpc.jsonl')),
           threading.Thread(target=relay, args=(process.stderr, sys.stderr.buffer, '/out/pi-stderr.txt'))]
for thread in threads:
    thread.start()
code = process.wait()
for thread in threads:
    thread.join()
sys.exit(code)
