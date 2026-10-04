# 学习路线与任务清单

> 目标：从"会 C 语言、Linux 零基础"到能独立承担赛题八的开发与答辩
> 原则：**先能跑，再懂原理，最后讲清楚**

## 零、你现在的位置（已实测）

| 项目 | 状态 |
|---|---|
| Linux 基础命令 | 已学：目录导航、文件操作、权限、重定向、管道、grep |
| 编程语言 | 会 C；Python 尚未系统学 |
| 数据库 | 未接触 SQL |
| Web | 已理解 HTML/CSS/JS 三者如何组成网页 |
| 赛题 Demo | **已跑通**（我搭的，含 12 题 NL2SQL、12 题 RAG、4 题跨源） |

**关键判断：你现在的瓶颈不是"能不能做"，而是"能不能讲清楚"。** 答辩时评委会问"为什么这么做"，这需要真懂。

## 一、四条并行学习线

### 线 1：Python（最高优先级，1~2 周）
你已经会 C，Python 主要是**心智切换**，不是从零学。

| 天数 | 内容 | 对应 C 概念 |
|---|---|---|
| 1 | 变量、类型、if/for/while | 语法去掉分号和花括号，靠缩进 |
| 2 | 列表、字典、元组 | 相当于动态数组和哈希表 |
| 3 | 函数、默认参数、`*args` | 函数指针与可变参数 |
| 4 | 字符串、f-string 格式化 | `printf` 的现代版 |
| 5 | 文件读写、异常 `try/except` | `fopen` + 错误码，但改用异常 |
| 6 | 模块与 `import` | `#include`，但没有头文件分离 |
| 7 | 类与对象（够用即可） | `struct` + 挂在里面的函数 |

**练手项目**：把之前那个 C 计算器改写成 Python 版。

### 线 2：SQL（第二优先级，3~5 天）
**这是赛题的核心，必须懂，不能只靠模型生成。**

| 天 | 内容 |
|---|---|
| 1 | `SELECT ... FROM ... WHERE`，理解"表=行+列" |
| 2 | `COUNT / SUM / AVG / MAX / MIN` 聚合函数 |
| 3 | `GROUP BY` + `HAVING`（分组统计） |
| 4 | `JOIN` 内连接（**重点**，赛题多表关联必用） |
| 5 | `LEFT JOIN`、子查询、窗口函数入门 |

**练手**：用项目里的 `data/chinook.sqlite`，手写查出"销量最高的艺人"。
```bash
sqlite3 data/chinook.sqlite
```
```sql
SELECT ar.Name, SUM(il.Quantity) AS qty
FROM InvoiceLine il
JOIN Track t  ON t.TrackId = il.TrackId
JOIN Album al ON al.AlbumId = t.AlbumId
JOIN Artist ar ON ar.ArtistId = al.ArtistId
GROUP BY ar.ArtistId ORDER BY qty DESC LIMIT 3;
```

### 线 3：HTTP / JSON / API（3 天）
理解"浏览器和服务器怎么对话"，你上次问过网页原理，这是延续。

| 天 | 内容 |
|---|---|
| 1 | 请求/响应、方法（GET/POST）、状态码（200/404/500） |
| 2 | JSON 格式（就是 Python 字典的文本形式） |
| 3 | 用 `requests` 调一个公开 API，再用 Flask 写一个自己的 API |

**练手**：读 `askdata/app.py`，找出所有路由，用 `curl` 逐个调一遍：
```bash
curl -s http://127.0.0.1:8788/health
curl -s -X POST http://127.0.0.1:8788/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"哪个音乐流派的歌曲数量最多？"}'
```

### 线 4：大模型应用（边做边学）
- **提示词工程**：把任务讲清楚、约束输出格式（看 `askdata/agent.py` 里的 prompt）
- **RAG 原理**：切片 → 建索引 → 检索 → 塞进提示词 → 生成（看 `retrieval.py`）
- **Agent 原理**：规划 → 调工具 → 观察结果 → 再规划（看 `agent.py` 的 `ask` 方法）
- **可解释性**：为什么要留步骤记录（这是本赛题的得分核心）

## 二、按周任务清单

### 第 1 周：读懂自己的 Demo
- [ ] 把 `askdata/` 下 6 个 Python 文件读一遍，逐个写注释
- [ ] 能画出"问题 → 路由 → SQL/检索 → 答案"的完整数据流
- [ ] 用 `sqlite3` 命令行手写 10 条查询
- [ ] 跑通 `benchmark/run_benchmark.py`，看懂每一项为什么对/错

### 第 2 周：中级任务 ①③（要素识别 + 语义澄清）
- [ ] 建别名词典（如"帝都→北京""销量→售出数量"），写 `alias.py`
- [ ] 在路由阶段加缺失维度检测，返回澄清话术
- [ ] 设计 5 个模糊问题做测试，记录澄清成功率

### 第 3 周：中级任务 ④（Schema Linking）
- [ ] 用 BM25 对表名/列名/取值建索引，做候选表召回
- [ ] 量化指标：候选表从 11 张减少到几张，准确率多少
- [ ] 对比"全 schema 提示"与"只给候选表"的准确率差异

### 第 4 周：鲁棒性 + 效率
- [ ] 造 10 个错别字/口语化问题，测容错率
- [ ] 做 1 千行 / 1 万行两种规模的响应时间实测
- [ ] 写复杂度分析（各模块时间复杂度）

### 第 5 周：文档
- [ ] 设计报告 ≤20 页（**第 1-2 页必须是核心亮点预览页**）
- [ ] 技术实现说明书 ≤30 页
- [ ] 录制 3 分钟演示视频

### 第 6 周：提交
- [ ] 打包 ZIP（源码 + schema + ≥10 份文档 + 依赖 + 启动脚本）
- [ ] 检查所有指标是否在文档中给出**真实数字**

## 三、答辩必背的三个问题

1. **"你怎么保证不编造答案？"**
   → 只依据检索到的片段回答；检索不到就说"未检索到"；每条答案附来源，可核对。

2. **"跨源问题你是怎么做到多跳的？"**
   → 先用 SQL 拿到事实实体（Margaret Park），把实体拼进检索词再去文档库找方法论，不是两次查询简单拼接。

3. **"生成的 SQL 出错怎么办？"**
   → 把数据库报错回灌给模型让它自我修正，最多 3 次；还失败就如实报错，不返回假数据。

## 四、避坑提醒

- **别跳过去学 Vue**：赛题说"建议"用 Vue，不是必须。当前页面已够用，把时间花在准确率上更划算。
- **别一上来就上向量数据库**：BM25 已能跑通，向量库是优化项而非必需项。
- **别选 OCR 类中级任务**：工程量远超预期。
- **文档边做边写**：20+30 页最后补会非常痛苦。

## 五、可用资源

| 用途 | 地址 |
|---|---|
| Chinook 数据库文档 | https://github.com/lerocha/chinook-database |
| OHR-Bench（赛题推荐） | https://hf-mirror.com/datasets/opendatalab/OHR-Bench |
| SQL 教程 | https://www.runoob.com/sql/sql-tutorial.html |
| Python 教程 | https://www.runoob.com/python3/python3-tutorial.html |
| SQLite 在线练习 | https://sqliteonline.com/ |
