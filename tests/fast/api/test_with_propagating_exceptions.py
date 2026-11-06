import pytest

import quacklab


class TestWithPropagatingExceptions:
    def test_with(self):
        # Should propagate exception raised in the 'with quacklab.connect() ..'
        with (
            pytest.raises(quacklab.CatalogException, match="Table with name invalid does not exist"),
            quacklab.connect() as con,
        ):
            con.execute("SELECT * FROM invalid")

        # Does not raise an exception
        with quacklab.connect() as con:
            con.execute("select 1")
