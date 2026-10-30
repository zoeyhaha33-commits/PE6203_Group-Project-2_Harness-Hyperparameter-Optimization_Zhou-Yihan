"""One optional paid diagnostic request, separate from benchmark/search state."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.request


def read_stream(response, report):
    """Retain SSE errors even when the HTTP status is 200."""
    report.update(reply='', error=None, stream_done=False, events=0)
    data = []
    def consume():
        if not data:
            return
        payload = '\n'.join(data)
        data.clear()
        if payload == '[DONE]':
            report['stream_done'] = True
            return
        event = json.loads(payload)
        report['events'] += 1
        for key in ('id', 'provider', 'usage'):
            if event.get(key) is not None:
                report['response_id' if key == 'id' else key] = event[key]
        if event.get('error'):
            report['error'] = event['error']
        for choice in event.get('choices') or []:
            content = (choice.get('delta') or {}).get('content')
            if isinstance(content, str):
                report['reply'] += content
            if choice.get('finish_reason'):
                report['finish_reason'] = choice['finish_reason']
    for raw in response:
        line = raw.decode('utf-8').rstrip('\r\n')
        if not line:
            consume()
            if report['stream_done']:
                break
        elif line.startswith('data:'):
            data.append(line[5:].lstrip(' '))
    consume()
    report['status'] = ('provider_error' if report['error'] else
                        'response_received' if report['stream_done'] and report['reply'] else 'incomplete_stream')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--stream', action='store_true', help='Use streaming, as Pi does; this does not run Pi or Docker.')
    args = parser.parse_args()
    payload = {'model': 'qwen/qwen3-coder', 'messages': [{'role': 'user', 'content': 'Reply with OK.'}],
               'max_tokens': 16, 'stream': args.stream}
    if args.stream:
        payload['stream_options'] = {'include_usage': True}
    if not args.execute:
        print('OFFLINE PREVIEW. No request sent:', json.dumps(payload))
        return
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        raise SystemExit('OPENROUTER_API_KEY missing.')
    root = Path(__file__).resolve().parent
    if (root / 'search.lock').exists():
        raise SystemExit('Search is active; do not mix diagnostic and benchmark billing.')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = root / ('provider_probe_' + stamp + '.json')
    report = {'phase': 'provider_diagnostic_not_benchmark', 'model': payload['model'],
              'max_output_tokens': 16, 'request_attempts': 1, 'stream': args.stream,
              'note': 'May incur API cost. No retries. Does not modify search state or prove Pi/ACP health.',
              'status': 'started'}
    def save():
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    save()
    request = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            report['http_status'] = response.status
            if args.stream:
                read_stream(response, report)
            else:
                body = json.load(response)
                report['response_id'] = body.get('id')
                report['provider'] = body.get('provider')
                report['usage'] = body.get('usage')
                report['error'] = body.get('error')
                choices = body.get('choices') or []
                content = (choices[0].get('message') or {}).get('content') if choices else None
                report['reply'] = content
                report['status'] = 'response_received' if choices and not body.get('error') else 'provider_error'
    except urllib.error.HTTPError as exc:
        report['status'] = 'http_error'
        report['http_status'] = exc.code
        report['error_body'] = exc.read(8192).decode('utf-8', errors='replace')
    except Exception as exc:
        report['status'] = 'transport_or_parse_error'
        report['error_type'] = type(exc).__name__
        report['error_message'] = str(exc)
    finally:
        # Never persist a credential even if an upstream error happens to echo it.
        report = json.loads(json.dumps(report).replace(key, '[REDACTED]'))
        save()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('Saved:', path)
    print('No benchmark task started. Search state unchanged.')


if __name__ == '__main__':
    main()
