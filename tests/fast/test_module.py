import quacklab


class TestModule:
    def test_paramstyle(self):
        assert quacklab.paramstyle == "qmark"

    def test_threadsafety(self):
        assert quacklab.threadsafety == 1

    def test_apilevel(self):
        assert quacklab.apilevel == "2.0"
