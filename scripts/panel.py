"""Loopback-only Uyghur voice panel. Runs one offline synthesis job at a time."""
import argparse
from datetime import datetime
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
from urllib.parse import quote, unquote, urlsplit
import uuid
from common import MAX_CHARS, SKILL, root, status, voice, write_json


class App:
    def __init__(self, data, port):
        self.data, self.port = data, port
        self.token = secrets.token_urlsafe(32)
        self.jobs, self.current = {}, None
        self.mutex = threading.Lock()
        for folder in ('outputs', 'jobs', 'logs'):
            (data / folder).mkdir(parents=True, exist_ok=True)

    def history(self):
        items = []
        for path in sorted((self.data / 'outputs').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            audio = path.with_suffix('.wav')
            if path.is_symlink() or audio.is_symlink() or not audio.is_file():
                continue
            try:
                value = json.loads(path.read_text(encoding='utf-8'))
                items.append({'name': audio.name, 'text': value.get('text', ''),
                              'voice_name': value.get('voice_name', '早期试听'),
                              'duration_seconds': value.get('duration_seconds'),
                              'url': '/outputs/' + quote(audio.name)})
            except (ValueError, OSError):
                continue
            if len(items) == 50:
                break
        return items

    def job(self, key):
        with self.mutex:
            value = dict(self.jobs[key])
        if value['state'] == 'running':
            log = self.data / 'logs' / (key + '.log')
            if log.exists():
                for line in log.read_text(encoding='utf-8', errors='replace').splitlines():
                    if line.startswith('PROGRESS '):
                        try:
                            value['stage'] = json.loads(line[9:])['stage']
                        except (ValueError, KeyError):
                            pass
        return value

    def submit(self, text, selected):
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_CHARS:
            raise ValueError('请输入 1–2000 字符的维语文案。')
        if selected is not None and not isinstance(selected, str):
            raise ValueError('音色选择无效。')
        selected, item = voice(self.data, selected)
        if status(self.data)['missing']:
            raise ValueError('本地环境不完整，请让 Codex 检查模型和运行环境。')
        with self.mutex:
            if self.current:
                raise BlockingIOError('已有配音正在生成，请完成后再试。')
            key = uuid.uuid4().hex
            filename = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + key[:8] + '.wav'
            job = {'id': key, 'state': 'running', 'stage': 'starting', 'voice_name': item['name'],
                   'text': text.strip(), 'filename': filename, 'url': '/outputs/' + quote(filename)}
            self.jobs[key], self.current = job, key
        try:
            text_path = self.data / 'jobs' / (key + '.txt')
            text_path.write_text(text.strip(), encoding='utf-8')
            write_json(self.data / 'jobs' / (key + '.json'), job)
            threading.Thread(target=self.run, args=(key, selected, text_path), daemon=True).start()
        except BaseException:
            with self.mutex:
                self.current = None
                self.jobs.pop(key, None)
            raise
        return dict(job)

    def run(self, key, selected, text_path):
        job = self.jobs[key]
        log_path = self.data / 'logs' / (key + '.log')
        try:
            command = [str(self.data / '.venv/bin/python'), str(SKILL / 'scripts/synthesize.py'),
                       '--data-dir', str(self.data), '--text-file', str(text_path), '--voice', selected,
                       '--output', str(self.data / 'outputs' / job['filename'])]
            env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
            with log_path.open('w', encoding='utf-8') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
                try:
                    returncode = process.wait(timeout=1200)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise RuntimeError('生成超过 20 分钟，已停止。请缩短文案后重试。')
            if returncode:
                lines = log_path.read_text(encoding='utf-8', errors='replace').strip().splitlines()
                raise RuntimeError(lines[-1][:500] if lines else '生成失败，请检查本地日志。')
            metadata = json.loads((self.data / 'outputs' / job['filename']).with_suffix('.json').read_text(encoding='utf-8'))
            job.update(state='done', stage='done', duration_seconds=metadata['duration_seconds'])
        except Exception as exc:
            job.update(state='error', error=str(exc))
        finally:
            try:
                write_json(self.data / 'jobs' / (key + '.json'), job)
            finally:
                with self.mutex:
                    self.current = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    @property
    def app(self):
        return self.server.app

    def trusted(self):
        allowed = {f'127.0.0.1:{self.app.port}', f'localhost:{self.app.port}'}
        return self.headers.get('Host') in allowed

    def respond(self, code, payload, mime='application/json; charset=utf-8', headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8') if mime.startswith('application/json') else payload
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'nonce-" + self.app.token + "'; style-src 'self' 'unsafe-inline'; media-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.trusted():
            return self.respond(403, {'error': '仅允许本机访问。'})
        path = urlsplit(self.path).path
        if path == '/':
            html = (SKILL / 'assets/panel.html').read_text(encoding='utf-8').replace('__NONCE__', self.app.token)
            return self.respond(200, html.encode('utf-8'), 'text/html; charset=utf-8')
        if path == '/api/status':
            return self.respond(200, dict(status(self.app.data), token=self.app.token, current_job=self.app.current))
        if path == '/api/history':
            return self.respond(200, self.app.history())
        if path.startswith('/api/jobs/'):
            key = path.rsplit('/', 1)[-1]
            try:
                return self.respond(200, self.app.job(key))
            except KeyError:
                return self.respond(404, {'error': '任务已失效，请查看历史作品。'})
        if path.startswith('/outputs/'):
            return self.audio(unquote(path[len('/outputs/'):]))
        return self.respond(404, {'error': '未找到。'})

    def audio(self, name):
        if not name or Path(name).name != name or not name.endswith('.wav'):
            return self.respond(404, {'error': '无效音频。'})
        path = self.app.data / 'outputs' / name
        if path.is_symlink() or not path.is_file():
            return self.respond(404, {'error': '未找到音频。'})
        size, start = path.stat().st_size, 0
        end = size - 1
        partial = self.headers.get('Range')
        if partial:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', partial)
            if not match or not any(match.groups()):
                return self.respond(416, {}, headers={'Content-Range': f'bytes */{size}'})
            first, last = match.groups()
            if first:
                start, end = int(first), min(int(last), end) if last else end
            else:
                start = max(0, size - int(last))
            if start > end or start >= size:
                return self.respond(416, {}, headers={'Content-Range': f'bytes */{size}'})
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type', 'audio/wav')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Disposition', "inline; filename*=UTF-8''" + quote(name))
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command == 'HEAD':
            return
        with path.open('rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = stream.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if (not self.trusted() or self.headers.get('X-Voice-Token') != self.app.token
                or (origin and origin != 'http://' + self.headers.get('Host', ''))):
            return self.respond(403, {'error': '请从本地面板提交请求。'})
        if urlsplit(self.path).path != '/api/generate':
            return self.respond(404, {'error': '未找到。'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 20000:
                return self.respond(413, {'error': '文案过长或请求为空。'})
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError('无效请求。')
            return self.respond(202, self.app.submit(value.get('text'), value.get('voice_id')))
        except BlockingIOError as exc:
            return self.respond(409, {'error': str(exc)})
        except (ValueError, TypeError) as exc:
            return self.respond(400, {'error': str(exc)})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir')
    p.add_argument('--port', type=int, default=8767)
    args = p.parse_args()
    os.umask(0o077)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.app = App(root(args.data_dir), server.server_port)
    print(f'扎提维语 skill：http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
