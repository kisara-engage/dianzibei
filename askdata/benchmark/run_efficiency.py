"""效率实测：对应赛题「系统效率分析」评分点，需两种以上规模的实测数据。

测量三部分：
1. BM25 建索引与查询（不同文档规模）
2. SQL 执行（不同表规模）
3. 端到端问答（拆分各阶段耗时）
"""
import json
import pathlib
import sqlite3
import statistics
import sys
import time

BASE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from askdata import retrieval

OUT = pathlib.Path(__file__).resolve().parent / 'efficiency.json'


# ---------- 1. BM25 规模测试 ----------
def make_chunks(n, chunk_words=60):
    """生成 n 个切片，每个约 chunk_words 个词。"""
    chunks = []
    vocab = ['销售', '数据', '客户', '发票', '曲目', '艺人', '专辑', '安全', '加密', '级别',
             '响应', '故障', '方法论', '冠军', '增长率', '质量', '评审', '晋升', '定价', '套餐']
    for i in range(n):
        words = [vocab[(i * 7 + j * 3) % len(vocab)] for j in range(chunk_words)]
        chunks.append(retrieval.Chunk(f'doc{i % 100}', i, ' '.join(words), f'标题{i}', f'doc{i % 100}'))
    return chunks


def bench_retrieval():
    results = []
    for n in (100, 1000, 10000, 50000):
        chunks = make_chunks(n)
        t0 = time.perf_counter()
        idx = retrieval.BM25Index()
        for c in chunks:
            idx.add(c)
        idx.finalize()
        build_ms = (time.perf_counter() - t0) * 1000

        queries = ['销售冠军的方法论', 'P0故障响应时效', '数据加密标准', '客户发票金额']
        lat = []
        for q in queries * 3:
            t1 = time.perf_counter()
            idx.search(q, top_k=4)
            lat.append((time.perf_counter() - t1) * 1000)
        results.append({
            'chunks': n, 'build_ms': round(build_ms, 1),
            'query_avg_ms': round(statistics.mean(lat), 2),
            'query_p95_ms': round(sorted(lat)[int(len(lat) * 0.95) - 1], 2),
        })
        print(f"  切片 {n:>6}: 建索引 {build_ms:8.1f} ms, 查询均值 {statistics.mean(lat):7.2f} ms")
    return results


# ---------- 2. SQL 规模测试 ----------
def build_test_db(rows):
    """构造含 rows 行记录的表，测 SQL 扫描与聚合耗时。"""
    path = f'/tmp/eff_{rows}.sqlite'
    p = pathlib.Path(path)
    if p.exists():
        p.unlink()
    conn = sqlite3.connect(path)
    conn.execute('create table sales(id integer primary key, city text, amount real, yr text)')
    data = [(i, f'City{i % 50}', (i % 1000) / 3.0, f'{2015 + i % 10}') for i in range(rows)]
    conn.executemany('insert into sales values(?,?,?,?)', data)
    conn.commit()
    conn.execute('create index idx_yr on sales(yr)')
    conn.commit()
    conn.close()
    return path


def bench_sql():
    results = []
    sql = ("select city, sum(amount) as total from sales "
           "where yr='2020' group by city order by total desc limit 5")
    for rows in (1000, 10000, 100000, 500000):
        path = build_test_db(rows)
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        lat = []
        for _ in range(5):
            t0 = time.perf_counter()
            conn.execute(sql).fetchall()
            lat.append((time.perf_counter() - t0) * 1000)
        conn.close()
        results.append({'rows': rows, 'sql_avg_ms': round(statistics.mean(lat), 2)})
        print(f"  表 {rows:>7} 行: 分组聚合 {statistics.mean(lat):7.2f} ms")
    return results


# ---------- 3. 端到端阶段拆分 ----------
def bench_end_to_end():
    from askdata.agent import Agent
    a = Agent(str(BASE / 'data' / 'chinook.sqlite'), str(BASE / 'kb'))

    # 预热（排除首次加载影响）
    a.ask('数据库里有多少首歌曲？', history=None)

    measures = []
    for q in ['数据库里有多少首歌曲？', 'P0级故障的响应时效要求是多少？']:
        stages = {}
        t0 = time.perf_counter()
        # 分阶段测量：路由 / SQL / 检索 / 生成
        t = time.perf_counter(); plan = a.plan(q, None); stages['路由'] = (time.perf_counter() - t) * 1000
        if plan['route'] in ('db', 'hybrid'):
            t = time.perf_counter(); r = a._sql_with_repair(q, plan, None); stages['NL2SQL'] = (time.perf_counter() - t) * 1000
        else:
            stages['NL2SQL'] = 0.0
        t = time.perf_counter(); chunks = a.retrieve(q, top_k=4); stages['检索'] = (time.perf_counter() - t) * 1000
        if chunks:
            t = time.perf_counter()
            try:
                a.answer_from_chunks(q, chunks, None)
            except Exception:
                pass
            stages['生成'] = (time.perf_counter() - t) * 1000
        else:
            stages['生成'] = 0.0
        stages['总计'] = (time.perf_counter() - t0) * 1000
        stages['question'] = q
        measures.append(stages)
        print(f"  «{q[:18]}» 路由 {stages['路由']:.0f} | SQL {stages['NL2SQL']:.0f} | "
              f"检索 {stages['检索']:.1f} | 生成 {stages['生成']:.0f} | 总 {stages['总计']:.0f} ms")
    return measures


if __name__ == '__main__':
    print('=== 1. BM25 检索规模测试 ===')
    ret = bench_retrieval()
    print('\n=== 2. SQL 规模测试 ===')
    sqlr = bench_sql()
    print('=== 3. 端到端阶段耗时 ===')
    e2e = bench_end_to_end()

    report = {'retrieval': ret, 'sql': sqlr, 'end_to_end': e2e}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n已写入 {OUT}')