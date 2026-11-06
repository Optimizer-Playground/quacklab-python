import pytest

import quacklab
import pandas as pd


def closed():
    return pytest.raises(quacklab.ConnectionException, match="Connection already closed")


def closed_relation():
    # Changed: a relation method reports the engine's text for a closed connection.
    return pytest.raises(quacklab.ConnectionException, match="Connection has already been closed")


def no_result_set():
    return pytest.raises(quacklab.InvalidInputException, match="No open result set")


class TestRuntimeError:
    def test_fetch_error(self):
        con = quacklab.connect()
        con.execute("create table tbl as select 'hello' i")
        with pytest.raises(quacklab.ConversionException):
            con.execute("select i::int from tbl").fetchall()

    def test_df_error(self):
        con = quacklab.connect()
        con.execute("create table tbl as select 'hello' i")
        with pytest.raises(quacklab.ConversionException):
            con.execute("select i::int from tbl").df()

    def test_arrow_error(self):
        pytest.importorskip("pyarrow")

        con = quacklab.connect()
        con.execute("create table tbl as select 'hello' i")
        with pytest.raises(quacklab.ConversionException):
            con.sql("select i::int from tbl").to_arrow_table()

    def test_register_error(self):
        con = quacklab.connect()
        py_obj = "this is a string"
        with pytest.raises(quacklab.InvalidInputException, match='Python Object "this is a string" of type "str"'):
            con.register(py_obj, "v")

    def test_relation_cache_fetchall(self):
        conn = quacklab.connect()
        df_in = pd.DataFrame(
            {
                "numbers": [1, 2, 3, 4, 5],
            }
        )
        conn.execute("create view x as select * from df_in")
        rel = conn.query("select * from x")
        del df_in
        with pytest.raises(quacklab.ProgrammingError, match="Table with name df_in does not exist"):
            # Even when we preserve ExternalDependency objects correctly, this is not supported
            # Relations only save dependencies for their immediate TableRefs,
            # so the dependency of 'x' on 'df_in' is not registered in 'rel'
            rel.fetchall()

    def test_relation_query_error(self):
        conn = quacklab.connect()
        df_in = pd.DataFrame(
            {
                "numbers": [1, 2, 3, 4, 5],
            }
        )
        conn.execute("create view x as select * from df_in")
        rel = conn.query("select * from x")
        del df_in
        with pytest.raises(quacklab.CatalogException, match="Table with name df_in does not exist"):
            rel.query("bla", "select * from bla")

    def test_conn_broken_statement_error(self):
        conn = quacklab.connect()
        df_in = pd.DataFrame(
            {
                "numbers": [1, 2, 3, 4, 5],
            }
        )
        conn.execute("create view x as select * from df_in")
        del df_in
        with pytest.raises(quacklab.CatalogException, match="Table with name df_in does not exist"):
            conn.execute("select 1; select * from x; select 3;")

    def test_conn_prepared_statement_error(self):
        conn = quacklab.connect()
        conn.execute("create table integers (a integer, b integer)")
        with pytest.raises(
            quacklab.InvalidInputException,
            match="Values were not provided for the following parameters: 2",
        ):
            conn.execute("select * from integers where a =? and b=?", [1])

    def test_closed_conn_exceptions(self):
        conn = quacklab.connect()
        conn.close()
        df_in = pd.DataFrame(
            {
                "numbers": [1, 2, 3, 4, 5],
            }
        )

        with closed():
            conn.register("bla", df_in)

        with closed_relation():
            conn.from_query("select 1")

        with closed_relation():
            conn.table("bla")

        with closed_relation():
            conn.table("bla")

        with closed_relation():
            conn.view("bla")

        with closed_relation():
            conn.values("bla")

        with closed_relation():
            conn.table_function("bla")

        with closed_relation():
            conn.from_df(df_in)

        with closed_relation():
            conn.from_csv_auto("bla")

        with closed_relation():
            conn.from_parquet("bla")

        with closed_relation():
            conn.from_arrow("bla")

    def test_missing_result_from_conn_exceptions(self):
        conn = quacklab.connect()

        with no_result_set():
            conn.fetchone()

        with no_result_set():
            conn.fetchall()

        with no_result_set():
            conn.fetchnumpy()

        with no_result_set():
            conn.fetchdf()

        with no_result_set():
            conn.fetch_df_chunk()
