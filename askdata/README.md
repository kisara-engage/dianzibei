# 可解释问数 / 问答智能体

多模态数据驱动的**可解释精准问数/问答智能体** Demo 实现，对应「中国电子杯」第三届高校 ICT 产教融合创新大赛**赛题八**。

系统接收自然语言问题，自主判断该查**结构化数据库**、查**非结构化知识库**，还是**两者融合**，执行后给出**带证据链的答案**。

## 一、快速启动

### Windows（推荐，照做即可）

1. 安装 Python 3.10+（**安装时务必勾选 Add python.exe to PATH**）
2. 解压到纯英文路径，例如 `D:\askdata`
3. 申请模型密钥 → 复制 `llm_config.example.yaml` 为 `llm_config.yaml` → 填入密钥
4. **双击 `START-Windows.bat`**，浏览器自动打开 `http://127.0.0.1:8788`

> 详细步骤见 **[docs/05-windows-setup-guide.md](docs/05-windows-setup-guide.md)**（含常见问题排查）

### Mac / Linux

```bash
bash run.sh
```

### 手动启动

```bash
cp llm_config.example.yaml llm_config.yaml   # 然后填入你的 API 密钥
python3 -m askdata.server                    # 仅需 Python 标准库
```

**模型密钥**（任一即可，都是 OpenAI 兼容接口）：

| 平台 | base_url | 推荐模型 |
|---|---|---|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash`（免费） |
| 阿里通义 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

也可用环境变量覆盖，不必写配置文件：
`ASKDATA_LLM_BASE_URL` / `ASKDATA_LLM_API_KEY` / `ASKDATA_LLM_MODEL`

### 零依赖设计

**不装任何第三方包也能完整运行。** 核心功能只用 Python 标准库：

| 组件 | 标准库实现 | 装了替代品则升级为 |
|---|---|---|
| Web 服务 | `http.server` | `askdata.app` 自动改用 Flask |
| YAML 解析 | `askdata/config.py` 内置解析器 | PyYAML |
| 中文分词 | 1~2 元组切分 | jieba（检索更准） |
| DOCX 解析 | `zipfile` + `xml.etree` | —（始终零依赖） |
| PDF 解析 | 需 pdfplumber 或 pypdf | —（可选） |

网络连不上 PyPI 时程序自动降级，**不影响使用**。

## 二、系统架构

```
用户问题
   │
   ▼
① 意图路由（LLM 规划）──────► db / kb / hybrid
   │
   ├──► ②A NL2SQL  ──► SQL 安全校验 ──► 执行 ──► 失败则回灌报错自动修正
   │                       │
   │                       └──► 产出：SQL 语句 + 结果表
   │
   └──► ②B BM25 检索 ──► 产出：命中片段 + 相关度 + 关键词
                            │
                            ▼
                    ③ 融合生成（答案 + 依据标注）
                            │
                            ▼
                    ④ 可解释性输出（推理链 / SQL / 片段）
```

**混合路线的关键设计**：先用 SQL 从数据库取出事实实体（如"2024 年销售冠军 = Margaret Park"），
再把该实体拼进检索词去知识库找方法论，实现**真正的跨源多跳**，而不是两次独立查询简单拼接。

## 三、目录结构

```
askdata/
├── START-Windows.bat          Windows 双击启动
├── run.sh                     Mac / Linux 启动
├── llm_config.example.yaml    模型配置模板（复制为 llm_config.yaml 后填密钥）
├── requirements.txt
├── askdata/
│   ├── llm.py                 LLM 调用封装（标准库 urllib，无额外 SDK）
│   ├── db.py                  Schema 读取 + SQL 安全校验 + 只读执行
│   ├── retrieval.py           BM25 检索（jieba 分词）
│   ├── docparse.py            文档解析（md/txt/docx/pdf）
│   ├── agent.py               核心：路由 / NL2SQL / RAG / 融合 / 可解释
│   └── app.py                 Flask 交互界面 + API
├── templates/index.html       前端页面
├── static/{style.css,app.js}
├── data/chinook.sqlite        Chinook 样例数据库（11 张表）
├── kb/                        知识库文档（12 份，对齐数据库真实数据）
├── docs/                      项目文档（含 Windows 本地运行指南）
├── benchmark/
│   ├── cases.py               测试集定义（28 题，人工核对期望值）
│   ├── run_benchmark.py       跑测试并输出准确率
│   └── run_efficiency.py      效率实测（两种以上规模）
├── tests/test_core.py         单元测试（19 项）
└── VERIFICATION.md            验证报告（含原始输出）
```

## 四、安全设计

- **SQL 只读**：仅允许单条 `SELECT`/`WITH`；拒绝 `INSERT/UPDATE/DELETE/DROP/ALTER/PRAGMA` 等；禁止注释与多语句；数据库以 `mode=ro` 打开并设 `query_only`。
- **不编造**：任何一步失败都如实返回错误；检索不到就说"未检索到"，不生成猜测答案。
- **来源可点**：每条答案都附 SQL 原文与命中片段，可人工核对。
- **信息不足时澄清**：路由阶段检测缺失关键信息，前端明确提示而不直接猜。

## 五、测试与评估

```bash
.venv/bin/python benchmark/run_benchmark.py
```

覆盖 12 题 NL2SQL + 12 题 RAG + 4 题跨源融合，期望值均人工核对真实数据/文档得出。
结果写入 `benchmark/report.json`。

## 六、环境依赖

**必需：Python 3.10 或更高（开发环境为 3.11）。除此之外无需任何第三方包。**

可选的增强项（不装会自动降级，功能不受影响）：

| 包 | 作用 | 不装时 |
|---|---|---|
| jieba | 中文分词，检索更准 | 用 1~2 元组切分 |
| flask | Web 框架 | 用标准库 `http.server` |
| PyYAML | YAML 解析 | 用内置极简解析器 |
| pdfplumber | 解析 PDF 文档 | 只影响 `.pdf` 知识文档 |

LLM 通过 `llm_config.yaml` 或环境变量配置：
`ASKDATA_LLM_BASE_URL` / `ASKDATA_LLM_API_KEY` / `ASKDATA_LLM_MODEL`

## 七、已知限制

- BM25 为关键词检索，同义改写能力弱于向量检索；如需可将 `retrieval.py` 替换为向量库。
- 知识库为演示数据（12 份文档），与 Chinook 数据库同源，尚未接入 OHR-Bench 等公开真实文档集。
- 多轮对话仅保留最近 5 轮，且仅用于指代消解，未做完整会话状态管理。
