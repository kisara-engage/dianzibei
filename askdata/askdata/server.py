"""最小 HTTP 服务器：只用标准库 http.server，不依赖 Flask。

支持的接口与原来一致：
    GET  /              页面
    GET  /health        健康检查
    GET  /api/schema    数据库结构
    POST /api/ask       问答
    POST /api/reset     清空对话历史
"""
import json
import os
import pathlib
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .agent import Agent

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / 'data' / 'chinook.sqlite'
DEFAULT_KB = BASE_DIR / 'kb'

_agent = None
_lock = threading.Lock()
_history = []  # 简单会话历史，用于多轮上下文


def get_agent():
    global _agent
    with _lock:
        if _agent is None:
            _agent = Agent(
                os.environ.get('ASKDATA_DB', str(DEFAULT_DB)),
                os.environ.get('ASKDATA_KB', str(DEFAULT_KB)),
            )
        return _agent


def _render_index():
    """读取模板并替换 4 个占位变量（不引入模板引擎）。"""
    agent = get_agent()
    html = (BASE_DIR / 'templates' / 'index.html').read_text(encoding='utf-8')
    for key, val in (('tables', len(agent.schema)),
                     ('docs', agent.kb_stats['documents']),
                     ('chunks', agent.kb_stats['chunks']),
                     ('model', agent.llm.model)):
        html = re.sub(r'\{\{\s*' + key + r'\s*\}\}', str(val), html)
    return html


MIME = {
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
}


class Handler(BaseHTTPRequestHandler):
    server_version = 'askdata/1.0'

    def log_message(self, fmt, *args):
        # 静音默认逐请求日志，保持终端清爽
        pass

    # ---------- 工具 ----------
    def _send(self, code, body, ctype='application/json; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _read_json(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return {}
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            return {}

    # ---------- 路由 ----------
    def do_GET(self):
        path = self.path.split('?', 1)[0]
        try:
            if path in ('/', '/index.html'):
                self._send(200, _render_index(), 'text/html; charset=utf-8')
            elif path == '/health':
                a = get_agent()
                self._json({'status': 'ok', 'tables': len(a.schema),
                            'documents': a.kb_stats['documents']})
            elif path == '/api/schema':
                a = get_agent()
                self._json({'tables': {t: {'rowcount': i['rowcount'],
                                           'columns': [c for c, _ in i['columns']]}
                                       for t, i in a.schema.items()},
                            'foreign_keys': a.fks, 'kb': a.kb_stats})
            elif path.startswith('/static/'):
                self._serve_static(path)
            else:
                self._json({'error': 'not found'}, 404)
        except BrokenPipeError:
            pass
        except Exception as exc:
            self._json({'error': f'{type(exc).__name__}: {exc}'}, 500)

    def do_POST(self):
        path = self.path.split('?', 1)[0]
        try:
            if path == '/api/ask':
                payload = self._read_json()
                question = (payload.get('question') or '').strip()
                if not question:
                    return self._json({'error': '问题不能为空'}, 400)
                if len(question) > 500:
                    return self._json({'error': '问题过长'}, 400)
                keep = payload.get('history')
                history = _history if keep is None else None
                try:
                    result = get_agent().ask(question, history=history)
                except Exception as exc:
                    return self._json({'error': f'{type(exc).__name__}: {exc}'}, 500)
                if keep is None:
                    _history.append({'q': question, 'a': result.get('answer', '')})
                    del _history[:-5]
                return self._json(result)
            elif path == '/api/reset':
                _history.clear()
                return self._json({'status': 'ok'})
            else:
                return self._json({'error': 'not found'}, 404)
        except BrokenPipeError:
            pass
        except Exception as exc:
            self._json({'error': f'{type(exc).__name__}: {exc}'}, 500)

    def _serve_static(self, path):
        rel = path[len('/static/'):]
        # 防目录穿越：只允许 static 目录下的文件
        target = (BASE_DIR / 'static' / rel).resolve()
        if not str(target).startswith(str((BASE_DIR / 'static').resolve())) or not target.is_file():
            return self._json({'error': 'not found'}, 404)
        ctype = MIME.get(target.suffix.lower(), 'application/octet-stream')
        self._send(200, target.read_bytes(), ctype)


def run(host='127.0.0.1', port=8788):
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


def main():
    host = os.environ.get('ASKDATA_HOST', '127.0.0.1')
    port = int(os.environ.get('ASKDATA_PORT', '8788'))
    # 启动前先初始化 Agent，配置有问题就立刻报错，而不是等第一次提问
    get_agent()
    httpd = run(host, port)
    print(f' * Serving on http://{host}:{port}')
    print(' * Press Ctrl+C to stop')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n * Stopped')
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
