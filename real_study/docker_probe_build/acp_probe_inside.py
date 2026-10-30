"""Minimal ACP client inside a disposable diagnostic container."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    output = Path('/out')
    output.mkdir(exist_ok=True)
    home = Path.home() / '.pi/agent'
    home.mkdir(parents=True, exist_ok=True)
    (home / 'settings.json').write_text(json.dumps({'retry': {'enabled': False, 'provider': {'maxRetries': 0}}}))
    key = os.environ['BENCHFLOW_PROVIDER_API_KEY']
    mock_requests = []
    if os.environ.get('PE6203_OFFLINE_SELF_TEST') == '1':
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                mock_requests.append({'model': request.get('model'), 'stream': request.get('stream'),
                                      'max_tokens': request.get('max_tokens'), 'max_completion_tokens': request.get('max_completion_tokens')})
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                for chunk in ({'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': 'OK'}, 'finish_reason': None}]},
                              {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                               'usage': {'prompt_tokens': 12, 'completion_tokens': 2, 'total_tokens': 14}}):
                    chunk.update(id='offline-test', object='chat.completion.chunk', created=1, model='qwen/qwen3-coder')
                    self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        os.environ['BENCHFLOW_PROVIDER_BASE_URL'] = f'http://127.0.0.1:{server.server_port}/v1'
    def clean(text):
        return text.replace(key, '[REDACTED]')
    process = subprocess.Popen(['/opt/benchflow/bin/pi-acp-launcher'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    events = queue.Queue()
    def drain(stream, filename, is_stdout):
        with (output / filename).open('w') as log:
            for line in stream:
                log.write(clean(line)); log.flush()
                if is_stdout:
                    try:
                        events.put(json.loads(line))
                    except ValueError:
                        pass
        if is_stdout:
            events.put({'_eof': True})
    threads = [threading.Thread(target=drain, args=(process.stdout, 'acp-stdout.jsonl', True), daemon=True),
               threading.Thread(target=drain, args=(process.stderr, 'acp-stderr.txt', False), daemon=True)]
    for thread in threads:
        thread.start()
    report = {'phase': 'docker_pi_acp_diagnostic_not_benchmark', 'status': 'started',
              'pi': '0.81.0', 'pi_acp': '0.0.34', 'prompt_requests': 0,
              'model': 'qwen/qwen3-coder', 'maxTokens': 16,
              'note': 'Isolated minimal prompt; not the task image or full benchmark. Tools and retries disabled.'}
    sequence = 0
    messages = []
    def send(value):
        process.stdin.write(json.dumps(value) + '\n'); process.stdin.flush()
    def rpc(method, params):
        nonlocal sequence
        sequence += 1
        wanted = sequence
        send({'jsonrpc': '2.0', 'id': wanted, 'method': method, 'params': params})
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            try:
                event = events.get(timeout=min(1, max(.01, deadline-time.monotonic())))
            except queue.Empty:
                continue
            if event.get('_eof'):
                raise RuntimeError('ACP process exited before response')
            if event.get('method') and 'id' in event:
                send({'jsonrpc': '2.0', 'id': event['id'], 'error': {'code': -32601, 'message': 'Tools disabled for diagnosis'}})
            update = (event.get('params') or {}).get('update') or {}
            if update.get('sessionUpdate') == 'agent_message_chunk':
                content = update.get('content') or {}
                if content.get('type') == 'text':
                    messages.append(content.get('text', ''))
            if event.get('id') == wanted and not event.get('method'):
                if 'error' in event:
                    raise RuntimeError(json.dumps(event['error']))
                return event.get('result') or {}
        raise TimeoutError('ACP response timeout: ' + method)
    try:
        report['initialize'] = rpc('initialize', {'protocolVersion': 1, 'clientCapabilities': {},
                                               'clientInfo': {'name': 'pe6203-diagnostic', 'version': '1'}})
        session = rpc('session/new', {'cwd': '/work', 'mcpServers': []})
        report['session_created'] = bool(session.get('sessionId'))
        session_id = session['sessionId']
        report['selected_model'] = (session.get('models') or {}).get('currentModelId')
        if report['selected_model'] != 'benchflow-qwen/qwen/qwen3-coder':
            raise RuntimeError('Session did not select the only configured diagnostic model')
        startup = ((session.get('_meta') or {}).get('piAcp') or {}).get('startupInfo', '')
        report['prompt_requests'] = 1
        report['prompt_result'] = rpc('session/prompt', {'sessionId': session_id,
              'prompt': [{'type': 'text', 'text': 'Reply with exactly OK. Do not use tools.'}]})
        report['status'] = 'prompt_finished'
    except Exception as exc:
        report['status'] = 'diagnostic_error'
        report['error_type'] = type(exc).__name__
        report['error_message'] = clean(str(exc))
    finally:
        report['reply'] = ''.join(messages)
        if 'startup' in locals() and startup and report['reply'].startswith(startup):
            report['reply'] = report['reply'][len(startup):]
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
        for thread in threads:
            thread.join(timeout=3)
        raw = output / 'pi-rpc.jsonl'
        errors = []
        if raw.exists():
            for line in raw.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                message = event.get('message') or {}
                if message.get('errorMessage'):
                    errors.append(message['errorMessage'])
                if event.get('success') is False or event.get('type') == 'auto_retry_end' and event.get('success') is False:
                    errors.append(event)
        report['pi_errors'] = errors
        if os.environ.get('PE6203_OFFLINE_SELF_TEST') == '1':
            report['offline_mock_requests'] = mock_requests
        if errors:
            report['status'] = 'pi_error'
        elif report['status'] == 'prompt_finished':
            report['status'] = 'ok' if report['reply'].strip() == 'OK' else 'unexpected_reply'
        text = clean(json.dumps(report, ensure_ascii=False, indent=2))
        (output / 'summary.json').write_text(text + '\n')
        print(text, flush=True)


if __name__ == '__main__':
    main()
