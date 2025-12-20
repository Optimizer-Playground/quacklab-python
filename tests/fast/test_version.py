import sys

import quacklab


def test_version():
    assert quacklab.__version__ != "0.0.0"


def test_formatted_python_version():
    formatted_python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert quacklab.__formatted_python_version__ == formatted_python_version
