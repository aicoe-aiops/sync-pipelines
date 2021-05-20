"""Test suite for solgate/lookup.py."""

from datetime import datetime, timedelta

import pytest
from moto.s3.models import s3_backend

from solgate import lookup


@pytest.mark.parametrize(
    "input,output",
    [
        ("1d", timedelta(days=1)),
        ("1h", timedelta(hours=1)),
        ("1m", timedelta(minutes=1)),
        ("1s", timedelta(seconds=1)),
        ("1d1h", timedelta(days=1, hours=1)),
        ("1d 1h", timedelta(days=1, hours=1)),
    ],
)
def test_parse_timedelta(input, output):
    """Should parse defined timedelta strings."""
    assert output == lookup.parse_timedelta(input)


def test_parse_timedelta_error():
    """Should raise when unable to parse."""
    with pytest.raises(ValueError):
        lookup.parse_timedelta("1y")


@pytest.mark.parametrize(
    "config,old_object_modified_date,found_objects",
    [
        (dict(), datetime(2020, 1, 1), 1),
        (dict(timedelta="4d"), datetime.today() - timedelta(days=3), 2),
        (dict(timedelta="4d"), datetime.today() - timedelta(days=5), 1),
    ],
)
@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_list_source(mocked_s3, mocker, config, old_object_modified_date, found_objects):
    """Should list correct amount of files."""
    fs = mocked_s3[0]
    mocker.patch("solgate.lookup.read_general_config", return_value=config)
    mocker.patch("solgate.lookup.S3FileSystem.from_config_file", return_value=[fs])

    fs.s3fs.touch("BUCKET/new.csv")
    fs.s3fs.touch("BUCKET/old.csv")
    s3_backend.buckets["BUCKET"].keys["old.csv"].last_modified = old_object_modified_date

    assert len(list(lookup.list_source({}))) == found_objects


def test_list_source_invalid_config(mocker):
    """Should raise when client can't be instantiated."""
    mocker.patch("solgate.lookup.read_general_config", return_value=dict())
    mocker.patch("solgate.lookup.S3FileSystem.from_config_file", side_effect=ValueError)

    with pytest.raises(ValueError):
        list(lookup.list_source({}))


@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_list_source_no_objects(mocked_s3, mocker):
    """Should raise when no files found."""
    fs = mocked_s3[0]
    mocker.patch("solgate.lookup.read_general_config", return_value=dict())
    mocker.patch("solgate.lookup.S3FileSystem.from_config_file", return_value=[fs])

    fs.s3fs.touch("BUCKET/old.csv")
    s3_backend.buckets["BUCKET"].keys["old.csv"].last_modified = datetime(2020, 1, 1)

    with pytest.raises(FileNotFoundError):
        list(lookup.list_source({}))


@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_list_source_backfill(mocked_s3, mocker):
    """Should list all files when backfill is enabled."""
    fs = mocked_s3[0]
    mocker.patch("solgate.lookup.read_general_config", return_value=dict())
    mocker.patch("solgate.lookup.S3FileSystem.from_config_file", return_value=[fs])

    fs.s3fs.touch("BUCKET/old.csv")
    s3_backend.buckets["BUCKET"].keys["old.csv"].last_modified = datetime(2020, 1, 1)

    assert len(list(lookup.list_source({}, True))) == 1
