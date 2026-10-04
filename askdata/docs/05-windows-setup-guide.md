# Windows 本地运行指南

> 全程照着做即可。程序**不装任何第三方依赖也能跑**，所以网络问题不会卡住你。

---

## 第一步：安装 Python

1. 打开 https://www.python.org/downloads/
2. 点黄色大按钮 **Download Python 3.x.x**
3. **双击安装时，务必勾选最下面那个复选框：**
   ```
   ☑ Add python.exe to PATH
   ```
   > 这一步最关键。不勾选后面会一直提示"找不到 python"。
4. 一路 Next 到完成

**验证：** 按 `Win + R` → 输入 `powershell` → 回车，然后输入：

```powershell
python --version
```

显示 `Python 3.12.x` 之类就成功了。若提示"不是内部或外部命令"，说明第 3 步没勾，重装一次。

---

## 第二步：解压项目

解压到 **`D:\askdata`**（路径别有中文和空格最省事）。

解压后应该长这样：

```
D:\askdata\
├── START-Windows.bat     ← 双击这个启动
├── llm_config.example.yaml
├── requirements.txt
├── askdata\              程序代码
├── data\chinook.sqlite   样例数据库
├── kb\                   12 份知识库文档
├── templates\
├── static\
├── benchmark\
├── tests\
└── README.md
```

---

## 第三步：申请一个模型密钥

程序需要调用大模型来理解问题。**推荐 DeepSeek**，中文好、便宜。

1. 打开 https://platform.deepseek.com/
2. 手机号注册、登录
3. 左侧 **API keys** → **创建 API key** → 复制 `sk-` 开头那串
   > **只显示一次**，先粘到记事本存好
4. 左侧 **充值**，充 **10 元**（一次问答约几分钱）

**不想花钱的替代方案：**

| 平台 | 地址 | 免费模型 |
|---|---|---|
| 智谱 GLM | https://open.bigmodel.cn/ | `glm-4-flash` |
| 阿里通义 | https://dashscope.console.aliyun.com/ | 新用户有额度 |

---

## 第四步：填入密钥

在 `D:\askdata` 里 **Shift + 右键** → 「在此处打开 PowerShell 窗口」：

```powershell
copy llm_config.example.yaml llm_config.yaml
notepad llm_config.yaml
```

记事本打开后，把 `api_key:` 后面那段换成你的密钥：

```yaml
model:
  base_url: https://api.deepseek.com/v1
  api_key: sk-你的密钥粘到这里
  default: deepseek-chat
```

**Ctrl + S 保存**，关闭记事本。

> 用智谱就把 `base_url` 改成 `https://open.bigmodel.cn/api/paas/v4`，
> `default` 改成 `glm-4-flash`。

---

## 第五步：启动

**双击 `START-Windows.bat`**

窗口里会依次显示：

```
[1/3] Python OK
[2/3] Optional dependencies (jieba / flask / PyYAML)...
[3/3] Configuration check...
Starting... browser will open automatically
```

**浏览器会自动打开 `http://127.0.0.1:8788`。**

> ⚠️ **黑窗口不要关**，关了服务就停。想停按 `Ctrl+C`。

### 如果看到这行，是正常的

```
[INFO] Could not reach PyPI. That is fine --
       the app runs on the Python standard library alone.
```

**意思是：连不上外网装不了加速包，但程序照样能跑**（用 Python 自带的库）。
检索质量会略低一点点，功能完全一样。**不用管它，继续用。**

---

## 第六步：试三个问题

| 输入 | 看什么 |
|---|---|
| `数据库里一共有多少首歌曲？` | 自己写 SQL 查库 → 3503 |
| `P0级故障的响应时效要求是多少？` | 去文档找 → 15 分钟内响应 |
| `2024年销售冠军是谁？请结合知识库总结他的成功方法论。` | **跨源**：先查库拿人名，再拿人名找方法论 |

**重点看右栏**：推理链路、SQL 语句、结果表格、检索片段。这是这套系统的价值。

---

## 关于安装路径

**推荐纯英文路径**（如 `D:\askdata`）。

Windows 的「桌面」「下载」「文档」以及中文用户名文件夹都带中文。
**本程序实测在中文路径下也能正常运行**，脚本检测到会提醒但不阻止。

万一遇到奇怪错误，把整个 `askdata` 文件夹剪切到 `D:\` 根目录再试。
程序内部全用相对路径，**移动后不需要改任何配置**。

---

## 常见问题

### 1. `python 不是内部或外部命令`
装 Python 时没勾 **Add python.exe to PATH**。重装并在第一步勾上。

### 2. `Could not find a version that satisfies the requirement flask>=3.0`
**这个不是错误，可以忽略。** 说明连不上 PyPI，程序会自动切到标准库模式。

如果你压根不想看到它，编辑 `requirements.txt` 把四行都注释掉（行首加 `#`）。

想手动装（比如家里网络好、公司网络差）：
```powershell
python -m pip install flask jieba PyYAML -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 窗口一闪就没了
说明出错了。改成看错误信息：
在 `D:\askdata` 里 Shift+右键 → PowerShell → 输入：
```powershell
.\START-Windows.bat
```
错误信息会留在窗口里。

### 4. 提示要填密钥 / 自动打开了记事本
正常。填好 `api_key` 保存，再双击一次 `START-Windows.bat`。

### 5. 网页能开，但提问报错
按顺序检查：
- `llm_config.yaml` 里 `api_key` 填对了吗（有没有多余空格）
- DeepSeek 账户有余额吗
- 窗口里打印的具体错误是什么

### 6. 提问很慢（十几秒到几十秒）
正常。每次问答要调用两三次大模型，延迟主要来自模型服务，且有波动。

### 7. 端口被占用
```powershell
set ASKDATA_PORT=8899
python -m askdata.server
```

### 8. 换个数据库
```powershell
set ASKDATA_DB=D:\mydata.sqlite
python -m askdata.server
```

---

## 想动手改代码？

| 想改什么 | 改哪里 |
|---|---|
| 加自己的知识文档 | 往 `kb\` 丢 `.md` / `.txt` / `.docx`，重启即可（`.pdf` 需装 pdfplumber） |
| 改回答风格 | `askdata\agent.py` 的 `answer_from_chunks` |
| 改路由判断 | `askdata\agent.py` 的 `plan` |
| 换标准库服务器为 Flask | 装了 flask 后自动使用，无需改代码 |

**建议阅读顺序**（由易到难）：

```
1. askdata\config.py     配置解析（最简单）
2. askdata\db.py         数据库访问 + SQL 安全
3. askdata\retrieval.py  检索
4. askdata\llm.py        怎么调模型
5. askdata\agent.py      核心逻辑
6. askdata\server.py     网页服务
```

---

## 跑测试

```powershell
python -m unittest discover -s tests -v
```
应显示 `OK`（19 项通过）。**不需要任何第三方库。**

跑准确率测试（约 4 分钟，消耗模型额度）：
```powershell
python benchmark\run_benchmark.py
```
