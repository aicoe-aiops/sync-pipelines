"""Test suite for solgate/utils/io.py."""
import datetime
import importlib
from dataclasses import dataclass
from json import dumps
from pathlib import Path

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


def test__read_yaml_file(fixture_dir):
    """Should parse config file."""
    config = io._read_yaml_file(fixture_dir / "sample_config.yaml")

    assert len(config["destinations"]) == 3
    assert len(config.keys()) == 6


def test__read_yaml_file_empty(mocker):
    """Should raise exception when config file is empty."""
    mocked_open = mocker.mock_open()
    mocker.patch("builtins.open", mocked_open)
    with pytest.raises(EnvironmentError):
        io._read_yaml_file("")


@pytest.mark.parametrize(
    "config,loaded_creds,call_count",
    [
        (dict(name="a"), dict(aws_access_key_id="b", aws_secret_access_key="c"), 1),
        (dict(name="a", aws_access_key_id="b", aws_secret_access_key="c"), None, 0),
        (dict(name="a", aws_access_key_id="b"), dict(aws_secret_access_key="c"), 1),
    ],
)
def test__fetch_creds(config, loaded_creds, mocker, call_count):
    """Should result in properly loaded credentials."""
    mocked = mocker.patch("solgate.utils.io._read_creds_file", return_value=loaded_creds)
    io._fetch_creds(Path(""), config)

    assert config == dict(name="a", aws_access_key_id="b", aws_secret_access_key="c")
    assert mocked.call_count == call_count


@pytest.mark.parametrize("loaded_creds", [{}, dict(aws_access_key_id="b"), dict(aws_secret_access_key="c")])
def test__fetch_creds_negative(mocker, loaded_creds):
    """Should raise when credentials are incomplete."""
    config = dict(name="a")
    mocker.patch("solgate.utils.io._read_creds_file", return_value=loaded_creds)

    with pytest.raises(IOError):
        io._fetch_creds(Path(""), config)


@pytest.mark.parametrize(
    "kind,expected_values",
    [
        ("source", ["SOURCE_KEY_ID", "SOURCE_ACCESS_KEY"]),
        ("destination.0", ["DESTINATION_DEFAULT_KEY_ID", "DESTINATION_DEFAULT_ACCESS_KEY"]),
        ("destination.1", ["DESTINATION_DEFAULT_KEY_ID", "DESTINATION_DEFAULT_ACCESS_KEY"]),
        ("destination.2", ["DESTINATION_CUSTOM_KEY_ID", "DESTINATION_CUSTOM_ACCESS_KEY"]),
    ],
)
def test__read_creds_file(fixture_dir, kind, expected_values):
    """Should load credentials with proper fallbacks."""
    assert list(io._read_creds_file(fixture_dir / "separate_creds_file_config", kind).values()) == expected_values


@pytest.mark.parametrize("kind,call_count", [("source", 1), ("destination", 1), ("destination.0", 2)])
def test__read_creds_file_raises(mocker, kind, call_count):
    """Should raise if the file and fallback are both not available."""
    mocked = mocker.patch("solgate.utils.io._read_yaml_file", side_effect=FileNotFoundError)

    with pytest.raises(FileNotFoundError):
        io._read_creds_file(Path(""), kind)
    assert mocked.call_count == call_count


@pytest.mark.parametrize(
    "config_file,number_of_destinations", [("sample_config.yaml", 3), ("single_destination.yaml", 1)]
)
def test_read_s3_config(fixture_dir, config_file, number_of_destinations):
    """Should parse s3 sections of the config."""
    s3_sections = {section["name"]: section for section in io.read_s3_config(config_file, fixture_dir)}

    assert len(s3_sections.items()) == number_of_destinations + 1
    assert "source" in s3_sections.keys()
    assert sum([k.startswith("destination") for k in s3_sections.keys()], 0) == number_of_destinations

    cred_keys = set(("aws_access_key_id", "aws_secret_access_key"))
    assert all([cred_keys.issubset(v.keys()) for v in s3_sections.values()])


def test_parse_booleans(mocker):
    """Should properly parse boolean values."""
    mocked_open = mocker.mock_open(read_data="true_property: yes\nfalse_property: no")
    mocker.patch("builtins.open", mocked_open)
    section = io.read_general_config("", Path(""))

    assert section["true_property"] is True
    assert section["false_property"] is False


def test_read_general_config(fixture_dir):
    """Should parse s3 sections of the config."""
    config = io.read_general_config("sample_config.yaml", fixture_dir)

    assert len(config.items()) == 4


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
