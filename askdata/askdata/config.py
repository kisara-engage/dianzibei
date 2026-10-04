"""配置读取：只用标准库，不依赖 PyYAML。

支持一个极简的 YAML 子集（够本项目用）：
    model:
      base_url: http://...
      api_key: sk-...
      default: deepseek-chat

同时兼容 `key: value` 的平铺写法（不带 model: 缩进）。
"""
import os
import pathlib
import re


def _strip_bom(text):
    return text.lstrip('\ufeff')


def _unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1]
    # 去掉行尾注释（不在引号内的 # ）
    out, in_q = [], None
    for ch in v:
        if in_q:
            if ch == in_q:
                in_q = None
            out.append(ch)
        elif ch in ('"', "'"):
            in_q = ch
            out.append(ch)
        elif ch == '#':
            break
        else:
            out.append(ch)
    return ''.join(out).strip()


def parse_simple_yaml(text):
    """解析极简 YAML：两级缩进映射 + 标量值。

    返回 {'model': {'base_url': ..., 'api_key': ..., 'default': ...}}
    或 {'base_url': ...} 形式（平铺时自动包进 model）。
    """
    result, current = {}, None
    for raw in _strip_bom(text).splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key, val = key.strip(), val.strip()
        if indent == 0:
            if val:
                # 平铺写法：base_url: xxx
                result.setdefault('model', {})[key] = _unquote(val)
                current = None
            else:
                current = key
                result.setdefault(current, {})
        else:
            if current is None:
                result.setdefault('model', {})[key] = _unquote(val)
            else:
                result[current][key] = _unquote(val)
    return result


def load_yaml(path):
    """读 YAML 文件。优先用 PyYAML（若已安装），否则用内置极简解析器。"""
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    raw = path.read_text(encoding='utf-8-sig', errors='replace')
    try:
        import yaml  # 可选，装了就用，语义更完整
        return yaml.safe_load(raw) or {}
    except ImportError:
        return parse_simple_yaml(raw)


def load_model_config(project_root=None):
    """读取 LLM 配置，优先级：环境变量 > 项目根 llm_config.yaml > Hermes 配置。

    首次运行若无 llm_config.yaml，会从 example 模板自动生成一份。
    """
    root = pathlib.Path(project_root) if project_root else pathlib.Path(__file__).resolve().parent.parent
    local_cfg = root / 'llm_config.yaml'
    example = root / 'llm_config.example.yaml'

    # 首次运行：自动从模板复制一份，省得用户手动 copy
    if not local_cfg.exists() and example.exists():
        try:
            local_cfg.write_bytes(example.read_bytes())
        except Exception:
            pass

    model_cfg = {}
    if local_cfg.exists():
        model_cfg = (load_yaml(local_cfg).get('model') or {})

    if not model_cfg.get('api_key'):
        cfg_path = pathlib.Path(
            os.environ.get('ASKDATA_HERMES_CONFIG',
                           str(pathlib.Path.home() / '.hermes' / 'config.yaml')))
        if cfg_path.exists():
            try:
                model_cfg = load_yaml(cfg_path).get('model') or model_cfg
            except Exception:
                pass

    base_url = os.environ.get('ASKDATA_LLM_BASE_URL') or model_cfg.get('base_url')
    api_key = os.environ.get('ASKDATA_LLM_API_KEY') or model_cfg.get('api_key')
    model = os.environ.get('ASKDATA_LLM_MODEL') or model_cfg.get('default')
    return base_url, api_key, model


def is_placeholder_key(api_key):
    """判断密钥是不是还停留在模板里的占位符。"""
    if not api_key:
        return True
    return bool(re.search(r'请替换|换掉|your.?key|xxxx|placeholder', str(api_key), re.I))


if __name__ == '__main__':
    print(load_model_config())
