"""基准测试集：覆盖 NL2SQL 与 RAG 两类，用于客观评估准确率。

每题的 expected 由人工核对真实数据库/文档得出，不是模型生成的。
"""
import pathlib
import sqlite3

BASE = pathlib.Path(__file__).resolve().parent.parent
DB = str(BASE / 'data' / 'chinook.sqlite')
KB = BASE / 'kb'

# ---------- NL2SQL 测试集（12 题）----------
# check: 期望结果的形式化断言
NL2SQL_CASES = [
    {
        'id': 'sql-01', 'question': '数据库里一共有多少首歌曲？',
        'tag': '单表计数', 'expect_desc': '3503',
        'check': lambda cols, rows: len(rows) == 1 and rows[0][0] == 3503,
    },
    {
        'id': 'sql-02', 'question': '平台上一共有多少位艺人？',
        'tag': '单表计数', 'expect_desc': '275',
        'check': lambda cols, rows: len(rows) == 1 and rows[0][0] == 275,
    },
    {
        'id': 'sql-03', 'question': '一共收录了多少张专辑？',
        'tag': '单表计数', 'expect_desc': '347',
        'check': lambda cols, rows: len(rows) == 1 and rows[0][0] == 347,
    },
    {
        'id': 'sql-04', 'question': '一共有多少家注册客户？',
        'tag': '单表计数', 'expect_desc': '59',
        'check': lambda cols, rows: len(rows) == 1 and rows[0][0] == 59,
    },
    {
        'id': 'sql-05', 'question': '哪个音乐流派的歌曲数量最多？',
        'tag': '聚合排序', 'expect_desc': 'Rock',
        'check': lambda cols, rows: rows and any('Rock' in str(v) for v in rows[0]),
    },
    {
        'id': 'sql-06', 'question': '曲目数量排名前三的音乐流派分别是什么？',
        'tag': '聚合排序 limit', 'expect_desc': 'Rock, Latin, Metal',
        'check': lambda cols, rows: len(rows) >= 3 and 'Rock' in str(rows[0]) and 'Latin' in str(rows[1]),
    },
    {
        'id': 'sql-07', 'question': '按发票金额统计，销售额最高的三个国家是哪些？',
        'tag': '多表聚合', 'expect_desc': 'USA, Canada, France',
        'check': lambda cols, rows: len(rows) >= 3 and 'USA' in str(rows[0]) and 'Canada' in str(rows[1]),
    },
    {
        'id': 'sql-08', 'question': '销量（售出曲目数量）最高的艺人是哪一位？',
        'tag': '两表关联聚合', 'expect_desc': 'Iron Maiden',
        'check': lambda cols, rows: rows and 'Iron Maiden' in ' '.join(str(v) for v in rows[0]),
    },
    {
        'id': 'sql-09', 'question': '2024年开出了多少张发票？',
        'tag': '条件筛选', 'expect_desc': '83',
        'check': lambda cols, rows: len(rows) == 1 and rows[0][0] == 83,
    },
    {
        'id': 'sql-10', 'question': '2024年的总销售额是多少？',
        'tag': '条件聚合', 'expect_desc': '477.53',
        'check': lambda cols, rows: len(rows) == 1 and abs(float(rows[0][0]) - 477.53) < 0.01,
    },
    {
        'id': 'sql-11', 'question': '2024年销售额最高的客户支持专员是谁？',
        'tag': '多表关联+分组', 'expect_desc': 'Margaret Park',
        'check': lambda cols, rows: rows and 'Margaret' in ' '.join(str(v) for v in rows[0]),
    },
    {
        'id': 'sql-12', 'question': '平台历史累计总销售额是多少？',
        'tag': '单表聚合', 'expect_desc': '2328.6',
        'check': lambda cols, rows: len(rows) == 1 and abs(float(rows[0][0]) - 2328.6) < 0.01,
    },
]

# ---------- RAG 测试集（12 题）----------
# check: 答案中必须命中的关键事实 + 必须来自哪份文档
RAG_CASES = [
    {'id': 'rag-01', 'question': 'P0级故障的响应时效要求是多少？',
     'tag': '制度条款', 'doc': '客户服务章程', 'must': ['15 分钟', '15分钟']},
    {'id': 'rag-02', 'question': 'P1级故障多长时间内要恢复？',
     'tag': '制度条款', 'doc': '客户服务章程', 'must': ['8 小时', '8小时']},
    {'id': 'rag-03', 'question': '2024年公司的销售冠军是谁？',
     'tag': '实体检索', 'doc': '销售冠军方法论', 'must': ['Margaret Park']},
    {'id': 'rag-04', 'question': '销售冠军的核心方法论叫什么？包含哪几步？',
     'tag': '方法总结', 'doc': '销售冠军方法论', 'must': ['三步破冰法']},
    {'id': 'rag-05', 'question': '公司的数据分成几个级别？',
     'tag': '制度条款', 'doc': '数据安全管理制度', 'must': ['4']},
    {'id': 'rag-06', 'question': 'L4核心数据的加密标准是什么？',
     'tag': '技术规范', 'doc': '数据安全管理制度', 'must': ['AES-256', 'AES256']},
    {'id': 'rag-07', 'question': '单元测试覆盖率要求不低于多少？',
     'tag': '技术规范', 'doc': '研发流程规范', 'must': ['70%']},
    {'id': 'rag-08', 'question': '智能问数分析助手的起步套餐多少钱？',
     'tag': '商务信息', 'doc': '产品定价说明', 'must': ['12 万', '12万']},
    {'id': 'rag-09', 'question': '2024年公司的平均数据质量分是多少？',
     'tag': '指标查询', 'doc': '数据质量管理办法', 'must': ['91.3']},
    {'id': 'rag-10', 'question': '申请T4及以上晋升需要经过什么评审？',
     'tag': '制度条款', 'doc': '员工培训与晋升', 'must': ['技术委员会', '答辩']},
    {'id': 'rag-11', 'question': '平台建设遇到的难点有哪些？',
     'tag': '要点罗列', 'doc': '多模态数据平台建设纪要', 'must': ['OCR']},
    {'id': 'rag-12', 'question': '2024年客户满意度全年平均是多少？',
     'tag': '指标查询', 'doc': '客户服务章程', 'must': ['95.7']},
]

# ---------- 跨源融合测试（4 题）----------
HYBRID_CASES = [
    {'id': 'hy-01', 'question': '2024年销售冠军是谁？请结合知识库总结他的成功方法论。',
     'tag': '跨源多跳', 'must': ['Margaret Park', '三步破冰法']},
    {'id': 'hy-02', 'question': '公司目前有多少家客户？客户服务的响应时效是怎么规定的？',
     'tag': '跨源拼接', 'must': ['59', '15']},
    {'id': 'hy-03', 'question': '哪个艺人销量最高？公司的数据安全对这类销售数据有什么保护要求？',
     'tag': '跨源拼接', 'must': ['Iron Maiden', 'L3']},
    {'id': 'hy-04', 'question': '2024年开出了多少张发票？同期市场分析报告预计2025年增长多少？',
     'tag': '跨源对比', 'must': ['83', '29%']},
]


def db_facts():
    conn = sqlite3.connect(DB)
    out = {
        'tracks': conn.execute('select count(*) from Track').fetchone()[0],
        'artists': conn.execute('select count(*) from Artist').fetchone()[0],
        'albums': conn.execute('select count(*) from Album').fetchone()[0],
        'customers': conn.execute('select count(*) from Customer').fetchone()[0],
    }
    conn.close()
    return out


if __name__ == '__main__':
    print('NL2SQL 用例:', len(NL2SQL_CASES))
    print('RAG 用例:', len(RAG_CASES))
    print('跨源用例:', len(HYBRID_CASES))
    print('数据库事实:', db_facts())
    print('知识库文档数:', len(list(KB.glob('*.md'))))
