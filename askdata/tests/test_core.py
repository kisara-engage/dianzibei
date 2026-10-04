"""回归测试：覆盖 SQL 安全、检索、路由判定、文档解析。不依赖外网。"""
import pathlib
import sqlite3
import sys
import unittest

BASE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from askdata import db, docparse, retrieval
from askdata.agent import _asks_identity_or_method

DB = str(BASE / 'data' / 'chinook.sqlite')
KB = str(BASE / 'kb')


class TestSQLSafety(unittest.TestCase):
    """SQL 安全是本题最关键的防线，必须全部拒绝。"""

    def test_accepts_select_and_with(self):
        self.assertTrue(db.validate_sql('select 1').lower().startswith('select'))
        self.assertTrue(db.validate_sql('WITH t AS (select 1) select * from t'))

    def test_rejects_write_operations(self):
        for bad in ['insert into Track values(1)',
                    'update Track set Name="x"',
                    'delete from Track',
                    'drop table Track',
                    'alter table Track add c int',
                    'create table x(a int)',
                    'pragma table_info(Track)',
                    'attach database "x" as y',
                    'vacuum']:
            with self.subTest(sql=bad):
                self.assertRaises(db.SQLRejected, db.validate_sql, bad)

    def test_rejects_multiple_statements(self):
        self.assertRaises(db.SQLRejected, db.validate_sql, 'select 1; select 2')

    def test_rejects_comments(self):
        self.assertRaises(db.SQLRejected, db.validate_sql, 'select 1 -- comment')
        self.assertRaises(db.SQLRejected, db.validate_sql, 'select /* x */ 1')

    def test_rejects_empty(self):
        self.assertRaises(db.SQLRejected, db.validate_sql, '')
        self.assertRaises(db.SQLRejected, db.validate_sql, None)

    def test_write_rejected_actually_does_not_modify(self):
        """不只校验，还要确认数据库真的没被改。"""
        conn = sqlite3.connect(DB)
        before = conn.execute('select count(*) from Track').fetchone()[0]
        conn.close()
        self.assertRaises(db.SQLRejected, db.run_sql, DB, 'delete from Track')
        conn = sqlite3.connect(DB)
        after = conn.execute('select count(*) from Track').fetchone()[0]
        conn.close()
        self.assertEqual(before, after)

    def test_real_query_returns_rows(self):
        cols, rows, sql = db.run_sql(DB, 'select count(*) from Track')
        self.assertEqual(rows[0][0], 3503)


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.index = retrieval.BM25Index()
        self.index.add(retrieval.Chunk('d1', 0, '公司的销售冠军是 Margaret Park，方法论是三步破冰法。', '冠军', 'd1'))
        self.index.add(retrieval.Chunk('d2', 1, 'P0 级故障要求 15 分钟内响应，4 小时内恢复。', '服务', 'd2'))
        self.index.add(retrieval.Chunk('d3', 2, '数据分为 L1 至 L4 四个级别，L4 使用 AES-256。', '安全', 'd3'))
        self.index.finalize()

    def test_finds_relevant_chunk(self):
        hits = self.index.search('销售冠军的方法论是什么')
        self.assertTrue(hits)
        self.assertEqual(hits[0][0].doc_id, 'd1')

    def test_finds_second_topic(self):
        hits = self.index.search('P0 故障响应时间')
        self.assertTrue(hits)
        self.assertEqual(hits[0][0].doc_id, 'd2')

    def test_returns_hit_keywords_for_explainability(self):
        hits = self.index.search('数据级别的加密')
        self.assertTrue(hits)
        self.assertTrue(hits[0][2], '必须返回命中关键词以支持可解释性')

    def test_empty_query_returns_nothing(self):
        self.assertEqual(self.index.search(''), [])

    def test_real_kb_index(self):
        index, stats = retrieval.build_index(KB)
        self.assertEqual(stats['documents'], 12)
        self.assertGreater(stats['chunks'], 12)
        hits = index.search('销售冠军是谁')
        self.assertTrue(hits)
        self.assertEqual(hits[0][0].doc_id, '销售冠军方法论')


class TestDocParse(unittest.TestCase):
    def test_supported_markdown(self):
        text = docparse.extract_text(pathlib.Path(KB) / '01-company-profile.md')
        self.assertIn('云海音乐数据服务', text)

    def test_docx_roundtrip(self):
        """手工构造一个最小 DOCX（zip 结构），验证解析器不依赖 python-docx。"""
        import zipfile
        p = pathlib.Path('/tmp/_parsetest.docx')
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:r><w:t>第一段测试内容</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>第二段测试内容</w:t></w:r></w:p>'
            '</w:body></w:document>'
        )
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('[Content_Types].xml',
                       '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr('word/document.xml', doc_xml)
        text = docparse.extract_text(p)
        self.assertIn('第一段测试内容', text)
        self.assertIn('第二段测试内容', text)
        p.unlink()

    def test_unsupported_suffix_raises(self):
        self.assertRaises(ValueError, docparse.extract_text, pathlib.Path('/tmp/x.xyz'))


class TestRoutingHeuristic(unittest.TestCase):
    """身份/方法类问题需要跨源补检索，这个判定不能退化。"""

    def test_identity_or_method_questions_trigger_supplement(self):
        for q in ['2024年销售冠军是谁？', '他的方法论是什么', '请总结他的成功经验']:
            with self.subTest(q=q):
                self.assertTrue(_asks_identity_or_method(q))

    def test_pure_metric_questions_do_not_trigger(self):
        # 这些答案只在数据库里，知识库没有对应内容，不该触发补检索
        for q in ['数据库里有多少首歌曲？', '2024年销售额是多少？', '谁销量最高']:
            with self.subTest(q=q):
                self.assertFalse(_asks_identity_or_method(q))


class TestSchemaReading(unittest.TestCase):
    def test_schema_has_expected_tables_and_fks(self):
        schema, fks = db.get_schema(DB)
        self.assertEqual(len(schema), 11)
        self.assertIn('Invoice', schema)
        self.assertIn('Track', schema)
        self.assertTrue(fks.get('InvoiceLine'), '外键信息用于跨源关联，必须能读到')

    def test_schema_text_contains_rowcount(self):
        schema, fks = db.get_schema(DB)
        text = db.schema_to_text(schema, fks)
        self.assertIn('Invoice', text)
        self.assertIn('->', text, '应包含外键关联路径')


if __name__ == '__main__':
    unittest.main(verbosity=2)
