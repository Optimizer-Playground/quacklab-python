"""Binding-level tests for quacklab's optimizer hints (``/*=quack_lab= ... */``).

The hint semantics are covered by the engine's sqllogictests in
``external/duckdb/test/sql/hinting/``. These tests check what the Python client adds on top: that hints reach the
optimizer through every way of running SQL from Python, that hint errors surface as the documented Python exceptions,
and that a failed hint leaves the connection usable.
"""

import re

import pytest

import quacklab

JOIN = "SELECT count(*) FROM t JOIN mi ON t.id = mi.movie_id"
JOIN_RESULT = 5000


@pytest.fixture
def con(duckdb_cursor):
    # ids 0..999, of which only 0..99 have matches in mi (50 each)
    duckdb_cursor.execute("CREATE TABLE t(id INTEGER)")
    duckdb_cursor.execute("CREATE TABLE mi(movie_id INTEGER)")
    duckdb_cursor.execute("INSERT INTO t SELECT range FROM range(1000)")
    duckdb_cursor.execute("INSERT INTO mi SELECT range % 100 FROM range(5000)")
    return duckdb_cursor


def explain(con, sql, params=None):
    query = f"EXPLAIN (FORMAT compact) {sql}"
    result = con.execute(query, params) if params is not None else con.execute(query)
    return result.fetchall()[0][1]


def top_join_estimate(plan):
    """Estimated cardinality of the topmost join, directly below the aggregate."""
    match = re.search(r"\n  HASH_JOIN \(est=(\d+)\)", plan)
    assert match, plan
    return int(match.group(1))


def scan_estimate(plan, table):
    match = re.search(rf"SEQ_SCAN \(est=(\d+)\) [^\n]*Table: memory\.main\.{table};", plan)
    assert match, plan
    return int(match.group(1))


def assert_usable(con):
    assert con.execute(JOIN).fetchall() == [(JOIN_RESULT,)]


class TestCardinalityHints:
    def test_unhinted_baseline(self, con):
        assert top_join_estimate(explain(con, JOIN)) == 5000

    def test_base_table_hint(self, con):
        assert scan_estimate(explain(con, "/*=quack_lab= card(t #42) */ SELECT * FROM t"), "t") == 42

    def test_join_hint(self, con):
        assert top_join_estimate(explain(con, f"/*=quack_lab= card(t mi #7) */ {JOIN}")) == 7

    @pytest.mark.parametrize(
        "hints",
        [
            "card(t #42) card(mi #24) card(t mi #7)",
            "card(t mi #7) card(t #42) card(mi #24)",
            "card(t #42) card(t mi #7)",
        ],
    )
    def test_join_hint_with_base_table_hints(self, con, hints):
        # Regression (quacklab v2.0.0): a base table hint dropped the scan's statistics, the join order optimizer was
        # skipped and the join hint was ignored, leaving the join estimate at the base table hint.
        plan = explain(con, f"/*=quack_lab= {hints} */ {JOIN}")
        assert top_join_estimate(plan) == 7
        assert scan_estimate(plan, "t") == 42

    @pytest.mark.parametrize("prefix", ["/* a note */ ", "-- a note\n"])
    def test_comment_before_hint_block(self, con, prefix):
        # Regression (quacklab v2.0.1): the end of the hint block was searched from the start of the query, so a block
        # comment before it cut the hint block short and failed with a syntax error
        assert scan_estimate(explain(con, f"{prefix}/*=quack_lab= card(t #42) */ SELECT * FROM t"), "t") == 42

    def test_hints_do_not_change_results(self, con):
        hinted = f"/*=quack_lab= card(t #42) card(mi #24) card(t mi #7) */ {JOIN}"
        assert con.execute(hinted).fetchall() == [(JOIN_RESULT,)]
        assert con.sql(hinted).fetchall() == [(JOIN_RESULT,)]


class TestHintsThroughClientApis:
    HINTED = f"/*=quack_lab= card(t #42) card(t mi #7) */ {JOIN}"

    def test_cursor(self, con):
        assert top_join_estimate(explain(con.cursor(), self.HINTED)) == 7

    def test_prepared_statement_with_parameters(self, con):
        plan = explain(con, f"{self.HINTED} WHERE mi.movie_id < ?", [1000])
        assert top_join_estimate(plan) == 7

    def test_relation_result(self, con):
        assert con.sql(self.HINTED).fetchall() == [(JOIN_RESULT,)]


class TestHintsOnRelations:
    """A relation re-runs its query text on every read, so the hint block must stay part of that text.

    Regression (quacklab v2.0.1): the parser cuts a statement's text at its first keyword, so the relation lost the
    leading hint block and planned every read unhinted.
    """

    HINTED = f"/*=quack_lab= card(t #42) card(t mi #7) */ {JOIN}"

    def test_sql_query_keeps_hint(self, con):
        assert con.sql(self.HINTED).sql_query().startswith("/*=quack_lab= card(t #42) card(t mi #7) */")

    def test_explain(self, con):
        plan = con.sql(self.HINTED).explain()
        assert "~7 rows" in plan
        assert "~42 rows" in plan

    def test_execution(self, con):
        con.execute("CREATE TABLE ci(movie_id INTEGER)")
        rel = con.sql(f"/*=quack_lab= JoinOrder((t mi)) */ {JOIN} JOIN ci ON t.id = ci.movie_id")
        # an incomplete join order is only rejected when the optimizer applies the hint
        with pytest.raises(quacklab.InvalidInputException, match="missing: ci"):
            rel.fetchall()

    def test_hint_survives_other_queries(self, con):
        # quacklab keeps the hints of the latest query per thread, so the relation must bring its own on every read
        rel = con.sql(self.HINTED)
        con.execute("SELECT 42").fetchall()
        assert "~7 rows" in rel.explain()

    @pytest.mark.parametrize(
        "prefix",
        [
            "CREATE TABLE other(i INTEGER); ",
            "-- a line comment\n",
            "CREATE TABLE other(i INTEGER); -- a line comment\n",
        ],
    )
    def test_hint_after_other_text(self, con, prefix):
        # Only statements that read no tables before the hinted one: the engine applies a script's hint block to every
        # statement of the script, so an earlier SELECT fails on the hint's relation names (also with execute()).
        assert "~7 rows" in con.sql(prefix + self.HINTED).explain()

    def test_with_query(self, con):
        rel = con.sql("/*=quack_lab= card(t #42) */ WITH x AS (SELECT * FROM t) SELECT * FROM x")
        assert "~42 rows" in rel.explain()
        assert rel.filter("id < 5").aggregate("count(*)").fetchall() == [(5,)]

    def test_derived_relation_keeps_hints(self, con):
        # a relation built on a hinted one embeds its text, hint block included, as the equivalent SQL would
        rel = con.sql("/*=quack_lab= card(t #42) */ SELECT * FROM t").filter("id > 0")
        assert "~42 rows" in rel.explain()

    def test_derived_join_order_covers_new_relations(self, con):
        # A JoinOrder hint names every relation of the join; joining the hinted relation with another relation adds
        # one it does not name. This fails exactly as the equivalent SQL does through execute().
        con.execute("CREATE TABLE ci(movie_id INTEGER)")
        hinted = con.sql("/*=quack_lab= JoinOrder((t mi)) */ SELECT t.id FROM t JOIN mi ON t.id = mi.movie_id")
        joined = hinted.join(con.sql("SELECT movie_id FROM ci"), "id = movie_id")
        with pytest.raises(quacklab.InvalidInputException, match="missing: ci"):
            joined.fetchall()
        with pytest.raises(quacklab.InvalidInputException, match="missing: ci"):
            con.execute(joined.sql_query()).fetchall()


class TestJoinOrderHints:
    @pytest.fixture
    def con3(self, duckdb_cursor):
        # all tables share the key domain 0..99, so every scan sits directly below its join in the plan
        duckdb_cursor.execute("CREATE TABLE t(id INTEGER)")
        duckdb_cursor.execute("CREATE TABLE mi(movie_id INTEGER)")
        duckdb_cursor.execute("CREATE TABLE ci(movie_id INTEGER)")
        duckdb_cursor.execute("INSERT INTO t SELECT range FROM range(100)")
        duckdb_cursor.execute("INSERT INTO mi SELECT range % 100 FROM range(5000)")
        duckdb_cursor.execute("INSERT INTO ci SELECT range % 100 FROM range(300)")
        return duckdb_cursor

    QUERY = "SELECT count(*) FROM t JOIN mi ON t.id = mi.movie_id JOIN ci ON t.id = ci.movie_id"

    @pytest.mark.parametrize(("join_order", "joined_last"), [("((mi ci) t)", "t"), ("((t ci) mi)", "mi")])
    def test_join_order_is_enforced(self, con3, join_order, joined_last):
        plan = explain(con3, f"/*=quack_lab= JoinOrder({join_order}) */ {self.QUERY}")
        # in a three-way left-deep plan, the scan directly below the top join is the relation joined last
        assert re.search(rf"\n  HASH_JOIN [^\n]*\n(    [^\n]*\n)*    SEQ_SCAN [^\n]*main\.{joined_last};", plan), plan

    def test_join_order_does_not_change_results(self, con3):
        assert con3.execute(f"/*=quack_lab= JoinOrder(((mi ci) t)) */ {self.QUERY}").fetchall() == [(15000,)]


class TestInvalidHints:
    @pytest.mark.parametrize(
        "sql",
        [
            "/*=quack_lab= card(t 42) */ SELECT * FROM t",
            "/*=quack_lab= card(#42) */ SELECT * FROM t",
            f"/*=quack_lab= JoinOrder(t mi) */ {JOIN}",
            f"/*=quack_lab= JoinOrder((t mi) */ {JOIN}",
        ],
    )
    def test_syntax_error(self, con, sql):
        # used to segfault: ANTLR recovered from the error and handed on a partial parse tree
        with pytest.raises(quacklab.InvalidInputException, match="Syntax error in quack_lab hint block"):
            con.execute(sql)
        assert_usable(con)

    @pytest.mark.parametrize(
        ("hint", "message"),
        [
            ("JoinOrder(((t t) mi))", "references the same relation more than once"),
            ("JoinOrder((t mi))", "must reference every relation of the join, missing: ci"),
        ],
    )
    def test_invalid_join_order(self, con, hint, message):
        # used to raise an InternalException or dereference a NULL plan
        con.execute("CREATE TABLE ci(movie_id INTEGER)")
        query = f"{JOIN} JOIN ci ON t.id = ci.movie_id"
        with pytest.raises(quacklab.InvalidInputException, match=re.escape(message)):
            con.execute(f"/*=quack_lab= {hint} */ {query}")
        assert_usable(con)

    def test_unknown_relation(self, con):
        # Regression (quacklab v2.0.1): raised as the generic quacklab.Error
        with pytest.raises(quacklab.InvalidInputException, match="Relation name not found: nope"):
            con.execute("/*=quack_lab= card(nope #42) */ SELECT * FROM t")
        assert_usable(con)
