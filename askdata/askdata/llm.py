"""LLM 调用封装：只用标准库 urllib，避免依赖额外 SDK。

配置读取交给 config.py，它优先用 PyYAML（若已安装），
没有时用内置的极简 YAML 解析器——所以本模块零第三方依赖。
"""
import json
import os
import urllib.error
import urllib.request

from .config import load_model_config, is_placeholder_key


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, base_url=None, api_key=None, model=None, timeout=90):
        cfg_base, cfg_key, cfg_model = load_model_config()
        self.base_url = (base_url or cfg_base or '').rstrip('/')
        self.api_key = api_key or cfg_key or ''
        self.model = model or cfg_model
        self.timeout = timeout
        if not self.base_url or not self.model:
            raise LLMError(
                '缺少 LLM 配置：请在 llm_config.yaml 里填写 base_url 和 default（模型名）')
        if is_placeholder_key(self.api_key):
            raise LLMError(
                'llm_config.yaml 里的 api_key 还是模板占位符。\n'
                '请打开该文件，把 api_key 换成你自己的密钥后重新启动。')

    def chat(self, messages, temperature=0.0, max_tokens=1500, retries=2):
        """调用 LLM；对空回复自动重试（实测上游偶发返回空内容）。"""
        last_empty = None
        for attempt in range(retries + 1):
            content = self._chat_once(messages, temperature, max_tokens)
            if content and content.strip():
                return content
            last_empty = content
        raise LLMError(f'LLM 连续 {retries + 1} 次返回空内容: {last_empty!r}')

    def _chat_once(self, messages, temperature, max_tokens):
        payload = json.dumps({
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }).encode('utf-8')
        req = urllib.request.Request(
            self.base_url + '/chat/completions',
            data=payload,
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer ' + self.api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise LLMError(f'LLM HTTP {exc.code}: {exc.read()[:200]!r}') from None
        except Exception as exc:
            raise LLMError(f'LLM 调用失败: {type(exc).__name__}: {exc}') from None
        try:
            content = data['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise LLMError(f'LLM 返回格式异常: {str(data)[:200]}') from None
        return content if content is not None else ''

    def chat_json(self, messages, **kw):
        """要求模型只返回 JSON，并容错解析 ```json 代码块。"""
        text = self.chat(messages, **kw).strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text.strip())


if __name__ == '__main__':
    llm = LLM()
    print('model:', llm.model)
    print('reply:', llm.chat([{'role': 'user', 'content': '只回复: 可用'}]))
