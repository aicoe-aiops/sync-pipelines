"""Test suite for solgate/utils/io.py."""
import datetime
import importlib
from dataclasses import dataclass
from json import dumps

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
        ("2000-01-01/second/file.csv.gz", "{date}/{b}/{rest}", "{b}/{date}/{rest}", "second/2000-01-01/file.csv.gz"),
    ],
)
def test_key_formatter(mocker, key, source_format, destination_format, result):
    """Test parsing and usage of default attributes."""
    importlib.reload(io)
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


def test__read_config(fixture_dir):
    """Should parse config file."""
    config = io._read_config(fixture_dir / "sample_config.ini")

    assert len(config.sections()) == 5
    assert "solgate" in config.sections()


def test__read_config_default_location(fixture_dir, mocker):
    """Should read config from default location if no path is given."""
    mocked_open = mocker.mock_open(read_data="[solgate]\n")
    mocker.patch("builtins.open", mocked_open)
    io._read_config()

    mocked_open.assert_called_once()
    assert mocked_open.call_args[0][0] == io.DEFAULT_CONFIG_LOCATION


def test__read_config_empty(mocker):
    """Should raise exception when config file is empty."""
    mocked_open = mocker.mock_open()
    mocker.patch("builtins.open", mocked_open)
    with pytest.raises(EnvironmentError):
        io._read_config()


@pytest.mark.parametrize(
    "config_file,number_of_destinations", [("sample_config.ini", 3), ("single_destination.ini", 1)]
)
def test_read_s3_config(fixture_dir, config_file, number_of_destinations):
    """Should parse s3 sections of the config."""
    s3_sections = {k: v for k, v in io.read_s3_config(fixture_dir / config_file)}

    assert len(s3_sections.items()) == number_of_destinations + 1
    assert "source" in s3_sections.keys()
    assert sum([k.startswith("destination") for k in s3_sections.keys()], 0) == number_of_destinations

    cred_keys = set(("aws_access_key_id", "aws_secret_access_key"))
    assert all([cred_keys.issubset(v.keys()) for v in s3_sections.values()])


def test_parse_booleans(mocker):
    """Should properly parse boolean values."""
    mocked_open = mocker.mock_open(read_data="[solgate]\ntrue_property = yes\nfalse_property = no")
    mocker.patch("builtins.open", mocked_open)
    section = io.read_general_config()

    assert section["true_property"] is True
    assert section["false_property"] is False


def test_read_general_config(fixture_dir):
    """Should parse s3 sections of the config."""
    config = io.read_general_config(fixture_dir / "sample_config.ini")

    assert len(config.items()) == 4


def test_read_general_config_negative(mocker):
    """Should raise exception when general section is missing from the config file."""
    mocked_open = mocker.mock_open(read_data="[some]\nother = sections\n\n[but]\nnot = the\nones = we need")
    mocker.patch("builtins.open", mocked_open)
    with pytest.raises(EnvironmentError):
        io.read_general_config()


def test_deserialize(mocker):
    """Should deserialize from JSON."""
    mocked_open = mocker.mock_open(read_data='{"a":"b"}')
    mocker.patch("builtins.open", mocked_open)
    assert io.deserialize("file.json") == dict(a="b")


def test_serialize(mocker):
    """Should serialize to JSON."""
    mocked_open = mocker.patch("builtins.open")
    io.serialize(dict(a="b"), "file.json")

    mocked_open.assert_called_once_with("file.json", "w")
    calls = mocked_open.return_value.__enter__.return_value.write.call_args_list
    args = "".join(c.args[0] for c in calls)
    assert args == '{"a": "b"}'


@pytest.mark.parametrize(
    "input,output",
    [
        pytest.param(range(2), "[0, 1]", id="generator"),
        pytest.param(datetime.datetime(2020, 1, 1), '"2020-01-01T00:00:00"', id="datetime"),
    ],
)
def test_custom_encoder(input, output):
    """Should dump custom types to JSON."""
    assert output == dumps(input, cls=io.CustomEncoder)


def test_custom_encoder_default():
    """Should raise default TypeError when unserializable."""
    # pydocstyle: D202
    @dataclass
    class Something:
        something: str

    with pytest.raises(TypeError):
        dumps(Something("abc"), cls=io.CustomEncoder)
