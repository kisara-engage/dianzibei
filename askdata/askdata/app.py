"""兼容入口：有 Flask 就用 Flask，没有就用内置 http.server。

两个入口功能完全一致（同样的路由、同样的 JSON 结构）。
    python -m askdata.app      自动选择
    python -m askdata.server   强制用标准库版本
"""
import os


def _has_flask():
    try:
        import flask  # noqa: F401
        return True
    except ImportError:
        return False


if _has_flask():
    import json
    import pathlib
    import time

    from flask import Flask, jsonify, render_template, request

    from .agent import Agent

    BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
    DEFAULT_DB = BASE_DIR / 'data' / 'chinook.sqlite'
    DEFAULT_KB = BASE_DIR / 'kb'

    _agent = None
    _history = []

    def get_agent():
        global _agent
        if _agent is None:
            _agent = Agent(os.environ.get('ASKDATA_DB', str(DEFAULT_DB)),
                           os.environ.get('ASKDATA_KB', str(DEFAULT_KB)))
        return _agent

    def create_app():
        app = Flask(__name__, template_folder=str(BASE_DIR / 'templates'),
                    static_folder=str(BASE_DIR / 'static'))

        @app.get('/')
        def index():
            a = get_agent()
            return render_template('index.html', tables=len(a.schema),
                                   docs=a.kb_stats['documents'],
                                   chunks=a.kb_stats['chunks'], model=a.llm.model)

        @app.get('/health')
        def health():
            a = get_agent()
            return jsonify({'status': 'ok', 'tables': len(a.schema),
                            'documents': a.kb_stats['documents']})

        @app.post('/api/ask')
        def ask():
            payload = request.get_json(silent=True) or {}
            question = (payload.get('question') or '').strip()
            if not question:
                return jsonify({'error': '问题不能为空'}), 400
            if len(question) > 500:
                return jsonify({'error': '问题过长'}), 400
            keep = payload.get('history')
            history = _history if keep is None else None
            try:
                result = get_agent().ask(question, history=history)
            except Exception as exc:
                return jsonify({'error': f'{type(exc).__name__}: {exc}'}), 500
            if keep is None:
                _history.append({'q': question, 'a': result.get('answer', '')})
                del _history[:-5]
            return jsonify(result)

        @app.post('/api/reset')
        def reset():
            _history.clear()
            return jsonify({'status': 'ok'})

        @app.get('/api/schema')
        def schema():
            a = get_agent()
            return jsonify({'tables': {t: {'rowcount': i['rowcount'],
                                           'columns': [c for c, _ in i['columns']]}
                                       for t, i in a.schema.items()},
                            'foreign_keys': a.fks, 'kb': a.kb_stats})

        return app

    def main():
        port = int(os.environ.get('ASKDATA_PORT', '8788'))
        host = os.environ.get('ASKDATA_HOST', '127.0.0.1')
        get_agent()
        create_app().run(host=host, port=port, debug=False, threaded=True)

else:
    from .server import main  # 标准库实现


if __name__ == '__main__':
    main()
