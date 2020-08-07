"""Test suite for solgate/utils/io.py."""

import datetime
import pytest
from solgate.utils import io


@pytest.mark.parametrize(
    "key,source_format,destination_format,result",
    [
        ("first/second/file.csv.gz", "{a}/{b}/{rest}", "{b}/{a}/{rest}", "second/first/file.csv.gz"),
        ("first/second/file.csv.gz", "{a}/{rest}", "{a}/something/{rest}", "first/something/second/file.csv.gz"),
        ("first/second/file.csv.gz", "{a}/{b}/{rest}", "{date}/{b}/{rest}", "2020-01-01/second/file.csv.gz"),
        ("first/second/file.csv.gz", "{a}/{b}/{rest}", "{a}/{a}/{rest}", "first/first/file.csv.gz"),
        ("file.csv.gz", "{rest}", "{date}/{rest}", "2020-01-01/file.csv.gz"),
        ("file.csv.gz", "{rest}", "{year}/{month}/{day}/{rest}", "2020/01/01/file.csv.gz"),
        ("file.csv.gz", "{rest}.{ext}", "{rest}-{date}.{ext}", "file-2020-01-01.csv.gz"),
        ("file.csv.gz", "", "{rest}", "file.csv.gz"),
        ("file.csv.gz", "{rest}", "", "file.csv.gz"),
        ("file.csv.gz", "{filename}.{ext}.{comp}", "{filename}", "file"),
    ],
)
def test_key_formatter(mocker, key, source_format, destination_format, result):
    """Test parsing and usage of default attributes."""
    mocked_datetime = mocker.patch("solgate.utils.io.datetime")
    mocked_datetime.now.return_value = datetime.datetime(2020, 1, 1)
    assert io.key_formatter(key, source_format, destination_format) == result


@pytest.mark.parametrize(
    "args,result",
    [
        (("file.csv.gz",), "file.csv"),
        (("file.csv.gz", "", ""), "file.csv"),
        (("first/file.csv.gz", "{a}/{rest}", "{rest}"), "file.csv"),
        (("file.csv.gz", "{rest}.{ext}", "{rest}-x.{ext}"), "file-x.csv"),
    ],
)
def test_key_formatter_with_unpack(args, result):
    """Should succeed with unpack=True flag."""
    assert io.key_formatter(*args, unpack=True) == result


@pytest.mark.parametrize(
    "key,source_format,destination_format",
    [
        ("file.csv.gz", "{this}/{should}/{not}/{parse}", "{parse}"),
        ("file.csv.gz", "{this}.{should}.{not}.{parse}", "{parse}"),
        ("file.csv.gz", "{rest}", "{unknown}/{rest}"),
    ],
)
def test_key_formatter_negative(key, source_format, destination_format):
    """Should raise exception, since it can't either parse source formatter or format to result."""
    with pytest.raises(KeyError):
        io.key_formatter(key, source_format, destination_format)


def test__default_attributes(mocker):
    """Default attributes should be evaluated only once per run and should return Dict[str, str]."""
    mocked_datetime = mocker.patch("solgate.utils.io.datetime", wraps=datetime.datetime)
    io._default_attributes.cache_clear()
    io._default_attributes()

    assert set(io._default_attributes().keys()) == set(
        ("date", "datetime", "day", "hour", "minute", "month", "weekday", "second", "year")
    )
    assert all(isinstance(v, str) for v in io._default_attributes().values())
    mocked_datetime.now.assert_called_once()


@pytest.mark.parametrize(
    "formatter,result",
    [
        ("{a}", ("a")),
        ("{a}{b}", ("a", "b")),
        ("{ab}{b}", ("ab", "b")),
        ("{{a}}", ()),
        ("{{}}", ()),
        ("{a}text{b}", ("a", "b")),
    ],
)
def test__get_param_names(formatter, result):
    """Parse out formatter string variables."""
    assert io._get_param_names(formatter) == set(result)


@pytest.mark.parametrize(
    "formatter", ["{{}", "{}}", "{", "}", r"{\}}"],
)
def test__get_param_names_negative(formatter):
    """Should raise error for invalid variable names."""
    with pytest.raises(ValueError):
        io._get_param_names(formatter)


@pytest.mark.parametrize(
    "formatter,regex",
    [("{a}", "^(?P<a>.*?)"), ("{a}/{b}", "^(?P<a>.*?)/(?P<b>.*?)"), ("{a}.{b}", "^(?P<a>.*?)\\.(?P<b>.*?)")],
)
def test__create_parser(mocker, formatter, regex):
    """Created parser's regex should match the pattern."""
    mocker.patch.object(io, "_get_param_names").return_value = set()
    assert io._create_parser(formatter).pattern.pattern == regex


def test_read_config(mocker):
    """Should parse config file."""
    mocker.patch("builtins.open", mocker.mock_open(read_data="a"))

    with open("x") as f:
        print(f.read())

    assert False
