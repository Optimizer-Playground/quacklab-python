import pytest

import quacklab
import pandas as pd


class TestParameterList:
    def test_bool(self, duckdb_cursor):
        conn = quacklab.connect()
        conn.execute("create table bool_table (a bool)")
        conn.execute("insert into bool_table values (TRUE)")
        res = conn.execute("select count(*) from bool_table where a =?", [True])
        assert res.fetchone()[0] == 1

    def test_exception(self, duckdb_cursor):
        conn = quacklab.connect()
        df_in = pd.DataFrame(
            {
                "numbers": [1, 2, 3, 4, 5],
            }
        )
        conn.execute("create table bool_table (a bool)")
        conn.execute("insert into bool_table values (TRUE)")
        with pytest.raises(quacklab.NotImplementedException, match="Unable to transform"):
            conn.execute("select count(*) from bool_table where a =?", [df_in])

    def test_explicit_nan_param(self):
        con = quacklab.default_connection()
        res = con.execute("select isnan(cast(? as double))", (float("nan"),))
        assert res.fetchone()[0]

    @pytest.mark.parametrize(
        ("param", "query"),
        [
            ([float("nan")], "select isnan(?[1])"),
            ({"a": float("nan")}, "select isnan(?.a)"),
            ({"key": ["k"], "value": [float("nan")]}, "select isnan(?['k'])"),
            ([[1.0, float("nan")]], "select isnan(?[1][2])"),
            ([{"a": [float("nan")]}], "select isnan(?[1].a[1])"),
        ],
    )
    def test_nested_nan_param(self, param, query):
        con = quacklab.connect()
        assert con.execute(query, [param]).fetchone() == (True,)

    @pytest.mark.parametrize(
        ("value", "query"),
        [
            (quacklab.Value(float("nan"), quacklab.sqltype("DOUBLE")), "select isnan(?)"),
            (quacklab.Value({"k": float("nan")}, quacklab.sqltype("MAP(VARCHAR, DOUBLE)")), "select isnan(?['k'])"),
            (quacklab.Value({"a": float("nan")}, quacklab.sqltype("STRUCT(a DOUBLE)")), "select isnan(?.a)"),
            (quacklab.Value([float("nan"), 1.0], quacklab.sqltype("DOUBLE[2]")), "select isnan(?[1])"),
            (
                quacklab.Value({float("nan"): 1}, quacklab.sqltype("MAP(DOUBLE, INTEGER)")),
                "select isnan(map_keys(?)[1])",
            ),
            (
                quacklab.Value((float("nan"), [float("nan")]), quacklab.sqltype("STRUCT(a DOUBLE, b DOUBLE[])")),
                "select isnan(?.b[1])",
            ),
        ],
    )
    def test_nan_typed_value_param(self, value, query):
        con = quacklab.connect()
        assert con.execute(query, [value]).fetchone() == (True,)

    def test_nested_nan_typed_param(self):
        con = quacklab.connect()
        value = quacklab.Value((float("nan"), 1.0), quacklab.sqltype("STRUCT(a DOUBLE, b DOUBLE)"))
        assert con.execute("select isnan(?.a)", [value]).fetchone() == (True,)

    def test_string_parameter(self, duckdb_cursor):
        conn = quacklab.connect()
        conn.execute("create table orders (o_orderdate date)")
        conn.execute("insert into orders values (date '1992-01-01'), (date '1994-01-01')")
        conn.execute(
            """
            SELECT COUNT(*)
            FROM ORDERS
            WHERE O_ORDERDATE BETWEEN ? AND ?
            """,
            ["1994-01-01", "1996-01-01"],
        )
        res = conn.fetchall()
        assert res == [(1,)]
