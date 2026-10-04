"""Schema 读取与 SQL 安全校验（对应评分点：NL2SQL 正确执行 + 可解释性）。"""
import re
import sqlite3

# 只允许只读查询；任何写操作、DDL、多语句都拒绝
_FORBIDDEN = re.compile(
    r'\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|reindex|grant|revoke)\b',
    re.I,
)
_LIMIT_RE = re.compile(r'\blimit\b', re.I)


class SQLRejected(ValueError):
    """SQL 未通过安全校验。"""


def get_schema(db_path):
    """返回 {表名: {"rowcount": n, "columns": [(列名, 类型), ...]}}"""
    conn = sqlite3.connect(db_path)
    try:
        tables = [r[0] for r in conn.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%' order by name")]
        schema = {}
        for t in tables:
            cols = [(r[1], r[2]) for r in conn.execute(f'pragma table_info("{t}")')]
            count = conn.execute(f'select count(*) from "{t}"').fetchone()[0]
            schema[t] = {'rowcount': count, 'columns': cols}
        # 记录主外键，供提示词里描述关联路径
        fks = {}
        for t in tables:
            try:
                rows = list(conn.execute(f'pragma foreign_key_list("{t}")'))
            except sqlite3.Error:
                rows = []
            if rows:
                fks[t] = [(r[3], r[2], r[4]) for r in rows]  # (本表列, 目标表, 目标列)
        return schema, fks
    finally:
        conn.close()


def schema_to_text(schema, fks, max_tables=None):
    """把 schema 渲染成给 LLM 看的紧凑文本。"""
    lines = []
    for table, info in schema.items():
        if max_tables and table not in max_tables:
            continue
        cols = ', '.join(f'{name} {typ}' for name, typ in info['columns'])
        lines.append(f'表 {table} (共 {info["rowcount"]} 行): {cols}')
        for local, target, target_col in fks.get(table, []):
            lines.append(f'  - {table}.{local} -> {target}.{target_col}')
    return '\n'.join(lines)


def validate_sql(sql):
    """校验生成的 SQL 是否可安全执行。返回清洗后的单条语句。"""
    if not isinstance(sql, str) or not sql.strip():
        raise SQLRejected('SQL 为空')
    text = sql.strip().rstrip(';').strip()
    if ';' in text:
        raise SQLRejected('不允许多条语句')
    if not re.match(r'^(select|with)\b', text, re.I):
        raise SQLRejected('只允许 SELECT 查询')
    if _FORBIDDEN.search(text):
        raise SQLRejected('包含被禁止的写操作或元命令')
    # 防止注释绕过
    if '--' in text or '/*' in text:
        raise SQLRejected('SQL 中不允许注释')
    return text


def run_sql(db_path, sql, max_rows=500):
    """执行只读查询，返回 (列名列表, 行列表) 或抛 SQLRejected。"""
    safe_sql = validate_sql(sql)
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        conn.execute('pragma query_only = on')
        cur = conn.execute(safe_sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows)
        return columns, [list(r) for r in rows], safe_sql
    except sqlite3.Error as exc:
        raise SQLRejected(f'SQL 执行失败: {exc}') from None
    finally:
        conn.close()
