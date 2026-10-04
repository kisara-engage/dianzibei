#!/usr/bin/env bash
# 一键启动（Mac / Linux）。可不装任何第三方依赖，纯标准库也能跑。
cd "$(dirname "$0")"
set -u

PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "[ERROR] 没有找到 python3，请先安装 Python 3.10 或更高版本"
  exit 1
fi

echo "============================================"
echo "  可解释问数 / 问答智能体 - 本地启动"
echo "============================================"
echo

if "$PY" -c 'import jieba, flask, yaml' 2>/dev/null; then
  echo "[1/3] 可选依赖已就绪"
else
  echo "[1/3] 可选依赖未装，尝试安装（失败也不影响运行）..."
  "$PY" -m pip install -q -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 15 --retries 1 2>/dev/null \
    || "$PY" -m pip install -q -r requirements.txt --timeout 15 --retries 1 2>/dev/null \
    || echo "      [提示] 连不上 PyPI，改用标准库模式运行（检索质量略降）"
fi

[ -f llm_config.yaml ] || cp llm_config.example.yaml llm_config.yaml 2>/dev/null

echo "[2/3] 检查配置..."
if ! "$PY" -c 'import sys;sys.path.insert(0,".");from askdata.config import load_model_config,is_placeholder_key;b,k,m=load_model_config();sys.exit(0 if (b and m and not is_placeholder_key(k)) else 1)' 2>/dev/null; then
  echo
  echo "  [需要操作] 还没有配置大模型密钥"
  echo "  请编辑 llm_config.yaml，把 api_key 换成你自己的密钥："
  echo "      $PWD/llm_config.yaml"
  echo "  免费申请：https://platform.deepseek.com/"
  exit 1
fi

echo "[3/3] 配置通过"
echo
echo "启动中... 浏览器访问 http://127.0.0.1:${ASKDATA_PORT:-8788}"
echo "按 Ctrl+C 可停止服务"
echo

"$PY" -m askdata.server
