"""Agent 核心：意图路由 -> NL2SQL / RAG / 融合 -> 可解释答案。

设计目标（对齐赛题评分）：
1. 自主规划：先判断问题需要查库、查文档，还是两者都要。
2. 可解释：全程记录 steps（推理链）、SQL、检索片段、数据来源。
3. 不做假：任何一步失败都如实返回错误，不编造答案。
"""
import json
import re
import time

from . import db, retrieval
from .llm import LLM, LLMError

MIN_SQL_CONFIDENCE = 0.55
MIN_RETRIEVAL_SCORE = 0.5

# 问"是谁/什么方法"时，答案可能同时存在于数据库与知识库，需要跨源补全
_IDENTITY_HINTS = ('是谁', '哪位', '是谁？', '的名字', '叫什么', '方法论', '方法', '经验',
                   '怎么做到', '如何做到', '成功之道', '心得', '总结他的', '总结她的')


def _asks_identity_or_method(question):
    return any(h in question for h in _IDENTITY_HINTS)


class Agent:
    def __init__(self, db_path, kb_dir, llm=None):
        self.db_path = db_path
        self.kb_dir = kb_dir
        self.llm = llm or LLM()
        self.schema, self.fks = db.get_schema(db_path)
        self.schema_text = db.schema_to_text(self.schema, self.fks)
        self.index, self.kb_stats = retrieval.build_index(kb_dir)
        self.sample_values = self._collect_sample_values()

    # ---------- 辅助 ----------
    def _collect_sample_values(self, limit_per_table=12):
        """抽取若干真实取值，帮助模型识别'销售冠军'这类需要查数据的实体。"""
        samples = {}
        for table, info in self.schema.items():
            cols = [c for c, _ in info['columns']]
            if 'Name' not in cols:
                continue
            try:
                rows = db.run_sql(self.db_path,
                                  f'select distinct "Name" from "{table}" limit {limit_per_table}',
                                  max_rows=limit_per_table)[1]
            except db.SQLRejected:
                continue
            vals = [r[0] for r in rows if r and r[0]]
            if vals:
                samples[table] = vals
        return samples

    def _samples_text(self):
        return '\n'.join(f'{t}: ' + '、'.join(v[:30] for v in vals)
                         for t, vals in self.sample_values.items())

    # ---------- 第一步：意图路由 ----------
    def plan(self, question, history=None):
        history_text = ''
        if history:
            history_text = '\n历史对话：\n' + '\n'.join(
                f'用户：{h["q"]}\n助手：{str(h["a"])[:200]}' for h in history[-3:])

        prompt = f"""你是企业数据问答智能体的规划模块。请判断用户问题需要走哪些数据源。

数据源说明：
- sql：结构化数据库（Chinook 音乐商店库），表结构：
{self.schema_text}
  表中真实取值示例：
{self._samples_text()}
- kb：企业知识库文档，共 {self.kb_stats['documents']} 份，主题包括公司简介、销售报告、销售方法论、服务章程、数据安全、研发流程、产品定价、市场分析、数据质量、培训晋升、平台建设、客户案例。

判定规则：
- 只需要查表得出结论 -> db
- 只涉及制度、方法、经验等文字知识 -> kb
- 问题包含多个子问题，其中**任何一个子问题需要查数据库**（数量、金额、排名、统计、谁最多/最高） -> hybrid
- 问题先要从数据库找到某个实体（如"销售冠军是谁"），再去文档中查这个实体的相关信息 -> hybrid
- "销售额""发票数""客户数""艺人销量""曲目数"等指标只能来自数据库，不是文档知识；只要问句里出现这类指标，就必须为 hybrid

示例：
- "公司对P0级故障的响应时效是多少？" -> kb（纯制度）
- "数据库里有多少首歌曲？" -> db（纯计数）
- "2024年开出了多少张发票？同期市场报告预计2025年增长多少？" -> hybrid（发票数要查库，增长率在文档）
- "哪个艺人销量最高？公司对这类数据有什么保护要求？" -> hybrid
{history_text}

只输出 JSON，不要任何解释：
{{"route": "db|kb|hybrid", "intent": "一句话概括用户意图", "missing": "缺少的关键信息，没有则填空字符串", "reason": "判断理由，20字内"}}

用户问题：{question}"""
        try:
            data = self.llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=300)
        except (LLMError, json.JSONDecodeError) as exc:
            return {'route': 'kb', 'intent': question, 'missing': '', 'reason': f'规划失败降级检索: {exc}'[:40]}
        route = data.get('route')
        if route not in ('db', 'kb', 'hybrid'):
            route = 'kb' if 'sql' not in str(data).lower() else 'db'
        data['route'] = route
        return data

    # ---------- 第二步 A：NL2SQL ----------
    def text_to_sql(self, question, plan, history=None):
        history_text = ''
        if history:
            history_text = '\n历史对话（可参考用户指代）：\n' + '\n'.join(
                f'用户：{h["q"]}' for h in history[-3:])
        prompt = f"""你是 SQLite 专家。根据表结构写出**一条** SELECT 语句回答用户问题。

表结构（含行数与外键路径）：
{self.schema_text}

关键提示：
- 表名和列名区分大小写，必须与上面完全一致，中文别名需自己匹配到英文列。
- 金额、销售额等通常看 Invoice.Total 或 InvoiceLine.UnitPrice * Quantity。
- "销量最好""卖得最多"通常统计 InvoiceLine 中 Quantity 之和最大的 Track。
- 日期范围可用 Invoice.InvoiceDate（形如 '2024-01-01 00:00:00'）。
- 只返回 SQL，不要解释，不要 markdown 代码块，不要以分号结尾。
{history_text}

用户问题：{question}"""
        raw = self.llm.chat([{'role': 'user', 'content': prompt}], max_tokens=600)
        sql = raw.strip()
        if sql.startswith('```'):
            parts = sql.split('```')
            sql = parts[1] if len(parts) > 1 else sql
            sql = re.sub(r'^sql\s*', '', sql, flags=re.I)
        sql = sql.strip().rstrip(';').strip()
        return sql

    def _sql_with_repair(self, question, plan, history=None, max_attempts=3):
        """生成 SQL 并执行；失败时把数据库报错回灌给模型修正（鲁棒性评分点）。"""
        attempts = []
        sql = self.text_to_sql(question, plan, history)
        last_error = ''
        for i in range(max_attempts):
            attempts.append(sql)
            try:
                columns, rows, safe_sql = db.run_sql(self.db_path, sql)
                return {'ok': True, 'sql': safe_sql, 'columns': columns, 'rows': rows,
                        'attempts': attempts, 'error': None}
            except db.SQLRejected as exc:
                last_error = str(exc)
            if i == max_attempts - 1:
                break
            fix_prompt = f"""上一条 SQL 执行失败，请修正。

表结构：
{self.schema_text}

用户问题：{question}
失败的 SQL：{sql}
数据库报错：{last_error}

只输出修正后的 SQL，不要解释，不要代码块，不要分号。"""
            sql = self.llm.chat([{'role': 'user', 'content': fix_prompt}], max_tokens=600).strip()
            if sql.startswith('```'):
                parts = sql.split('```')
                sql = parts[1] if len(parts) > 1 else sql
            sql = re.sub(r'^sql\s*', '', sql, flags=re.I).strip().rstrip(';').strip()
        return {'ok': False, 'sql': attempts[-1] if attempts else '', 'columns': [], 'rows': [],
                'attempts': attempts, 'error': last_error}

    # ---------- 第二步 B：RAG ----------
    def retrieve(self, query, top_k=4):
        return self.index.search(query, top_k=top_k)

    def answer_from_chunks(self, question, chunks, sql_context=None):
        context_parts = []
        for i, (chunk, score, _hits) in enumerate(chunks, 1):
            context_parts.append(f'【片段{i}｜来源：{chunk.doc_id}｜第{chunk.seq + 1}段】\n{chunk.text}')
        context = '\n\n'.join(context_parts)
        sql_part = ''
        if sql_context:
            sql_part = ('\n查询到的结构化数据（来自数据库）：\n'
                        f'SQL: {sql_context["sql"]}\n'
                        f'结果: {json.dumps(sql_context["rows"][:10], ensure_ascii=False)}\n')
        prompt = f"""你是企业知识助手。请**只依据给定资料**回答问题，不得编造。

要求：
- 资料中没有的信息，明确说"资料中未提及"。
- 回答后附上依据，格式：依据：片段1、片段3
- 语言简洁，先给结论。
{sql_part}
资料：
{context}

用户问题：{question}"""
        return self.llm.chat([{'role': 'user', 'content': prompt}], max_tokens=1200)

    # ---------- 主流程 ----------
    def ask(self, question, history=None):
        t0 = time.time()
        steps = []
        plan = self.plan(question, history)
        steps.append({'name': '意图路由', 'detail': f"路线={plan['route']}；意图={plan['intent']}；理由={plan.get('reason', '')}"})

        result = {'question': question, 'route': plan['route'], 'intent': plan.get('intent', ''),
                  'missing': plan.get('missing', ''), 'steps': steps, 'sql': None, 'sources': [],
                  'answer': '', 'error': None, 'elapsed': 0.0}

        chunks = []
        sql_context = None

        # 需要查库
        if plan['route'] in ('db', 'hybrid'):
            sql_result = self._sql_with_repair(question, plan, history)
            result['sql'] = {'text': sql_result['sql'], 'ok': sql_result['ok'],
                             'columns': sql_result['columns'], 'rows': sql_result['rows'][:50],
                             'attempts': len(sql_result['attempts']), 'error': sql_result['error']}
            if sql_result['ok']:
                steps.append({'name': 'NL2SQL 生成与执行',
                              'detail': f"SQL 已执行，返回 {len(sql_result['rows'])} 行"
                                        + (f"（第 {len(sql_result['attempts'])} 次尝试成功）" if len(sql_result['attempts']) > 1 else '')})
                sql_context = {'sql': sql_result['sql'], 'rows': sql_result['rows']}
            else:
                steps.append({'name': 'NL2SQL 生成与执行',
                              'detail': f"执行失败：{sql_result['error']}（已尝试 {len(sql_result['attempts'])} 次）"})

        # 需要查文档；纯 db 路线下若问题问"是谁/什么方法"，补一次检索做跨源补全
        needs_docs = plan['route'] in ('kb', 'hybrid')
        if plan['route'] == 'db' and sql_context and sql_context['rows'] and _asks_identity_or_method(question):
            needs_docs = True
            steps.append({'name': '补充检索',
                          'detail': '问题同时询问实体身份或方法，除 SQL 结果外再检索知识库补充'})
        if needs_docs:
            if sql_context and sql_context['rows']:
                # 把数据库查到的事实拼进检索词，实现跨源推理
                facts = ' '.join(str(v) for row in sql_context['rows'][:5] for v in row if isinstance(v, str))
                query = f'{question} {facts}'
                steps.append({'name': '跨源检索词构造',
                              'detail': f'用数据库查得的事实增强检索：{facts[:80]}'})
            else:
                query = question
            ranked = self.retrieve(query, top_k=4)
            chunks = ranked
            if ranked:
                result['sources'] = [{
                    'doc': c.doc_id, 'title': c.title, 'chunk': c.seq + 1,
                    'score': round(s, 4), 'hits': hits, 'snippet': c.text[:180],
                    'path': c.path,
                } for c, s, hits in ranked]
                steps.append({'name': '知识库检索',
                              'detail': '命中 ' + '、'.join(f'{c.doc_id}({s:.2f})' for c, s, _ in ranked)})
            else:
                steps.append({'name': '知识库检索', 'detail': '未命中任何片段'})

        # 生成答案
        if result['error'] is None:
            # 有检索片段时优先做融合生成：即使主路线是 db，
            # 只要做了补充检索，也要把文档知识合成进答案，而不是只丢一个 SQL 结果。
            if chunks:
                try:
                    result['answer'] = self.answer_from_chunks(question, chunks, sql_context)
                except LLMError as exc:
                    # 合成失败时退回结构化结果，不能让已有事实丢失
                    if sql_context and sql_context['rows']:
                        result['answer'] = f"查询结果：{json.dumps(sql_context['rows'][:10], ensure_ascii=False)}"
                        result['error'] = f'文档融合生成失败，已退回结构化结果：{exc}'
                    else:
                        result['error'] = f'答案生成失败：{exc}'
            elif result['route'] == 'db' and sql_context and sql_context['rows']:
                if len(sql_context['rows']) == 1 and len(sql_context['rows'][0]) == 1:
                    result['answer'] = f"查询结果：**{sql_context['rows'][0][0]}**"
                else:
                    preview = json.dumps(sql_context['rows'][:10], ensure_ascii=False)
                    result['answer'] = f"查询返回 {len(sql_context['rows'])} 行结果：{preview}"
            elif result['route'] == 'db':
                result['answer'] = '数据库查询没有返回结果，请确认问题中的条件。'
            elif result['route'] == 'hybrid' and sql_context:
                result['answer'] = f"数据库部分结果：{json.dumps(sql_context['rows'][:10], ensure_ascii=False)}"
            else:
                result['error'] = '知识库中未检索到相关内容，无法回答。'

        result['elapsed'] = round(time.time() - t0, 2)
        return result
