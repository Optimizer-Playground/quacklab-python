import pytest

import quacklab


class TestWithPropagatingExceptions:
    def test_with(self):
        # Should propagate exception raised in the 'with duckdb.connect() ..'
        with pytest.raises(quacklab.ParserException, match=r"syntax error at or near *"), quacklab.connect() as con:
            con.execute("invalid")

        # Does not raise an exception
        with quacklab.connect() as con:
            con.execute("select 1")
