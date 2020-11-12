"""Test suite for solgate/utils/s3.py."""
import random
from datetime import datetime, timezone
from gzip import GzipFile

import pytest
from moto.s3.models import s3_backend

from solgate.utils import s3


@pytest.mark.parametrize(
    "name,default_endpoints_key,endpoint_url",
    [("source", "source", None), ("anything_else", "destination", None), ("source_y", None, "https://s3.example.com"),],
)
def test_s3_file_system_endpoints(name, default_endpoints_key, endpoint_url):
    """Should select default endpoint url if not specified, leave untouched if specified."""
    fs = s3.S3FileSystem(name, "KEY_ID", "SECRET_KEY", "BUCKET", endpoint_url)
    assert fs.endpoint_url == s3.DEFAULT_ENDPOINTS.get(default_endpoints_key, endpoint_url)


def test_s3_file_system_init():
    """Should parse args on init and pass expected values to S3fs's S3FileSystem."""
    fs = s3.S3FileSystem("source", "KEY_ID", "SECRET_KEY", "BUCKET", formatter="FORMATTER", unpack=True)

    assert fs.is_source
    assert fs.formatter == "FORMATTER"
    assert fs.flags == dict(unpack=True)
    assert fs.s3fs.client_kwargs == dict(endpoint_url=s3.DEFAULT_ENDPOINTS["source"])
    assert fs.s3fs.key == "KEY_ID"
    assert fs.s3fs.secret == "SECRET_KEY"


def test_s3_file_system_from_config_file_multiple_sources(fixture_dir):
    """Should not allow multiple sources in a config file."""
    with pytest.raises(EnvironmentError):
        s3.S3FileSystem.from_config_file(dict(filename="multiple_sources.yaml", path=fixture_dir))


@pytest.mark.parametrize("mocked_s3", ["sample_config.yaml"], indirect=["mocked_s3"])
def test_s3_file_system_from_config_file_order(mocked_s3):
    """Should order clients."""
    assert [str(i) for i in mocked_s3] == ["source", "destination.0", "destination.1", "destination.2"]


@pytest.mark.parametrize(
    "other_fs_params,result",
    [
        (("name2", "KEY_ID_1", "SECRET_KEY_1", "BUCKET", "https://s3.example.com"), True),
        (("name2", "KEY_ID_2", "SECRET_KEY_1", "BUCKET", "https://s3.example.com"), False),
        (("name2", "KEY_ID_1", "SECRET_KEY_2", "BUCKET", "https://s3.example.com"), False),
        (("name2", "KEY_ID_1", "SECRET_KEY_1", "BUCKET", "https://s3.different.example.com"), False),
        (("name2", "KEY_ID_1", "SECRET_KEY_1", "BUCKET", "https://s3.example.com", dict(unpack=True)), False),
    ],
)
def test_s3_file_system_eq(other_fs_params, result):
    """Should compare S3FileSystems."""
    fs = s3.S3FileSystem("name1", "KEY_ID_1", "SECRET_KEY_1", "BUCKET", "https://s3.example.com")
    other_fs = s3.S3FileSystem(*other_fs_params[:5], **next(iter(other_fs_params[5:]), dict()))

    assert (fs == other_fs) == result


def test_s3_file_system_eq_to_different_type():
    """Should not compare to other types."""
    fs = s3.S3FileSystem("name1", "KEY_ID_1", "SECRET_KEY_1", "BUCKET", "https://s3.example.com")

    assert (fs == "a") is False


def test_s3_file_system_str():
    """Name is the string repr of S3FileSystem."""
    fs = s3.S3FileSystem("name1", "KEY_ID_1", "SECRET_KEY_1", "BUCKET", "https://s3.example.com")
    assert str(fs) == "name1"


@pytest.mark.parametrize(
    "dest_base,result",
    [
        (None, "BUCKET/c/d.csv"),
        ("BUCKET/different_base", "BUCKET/different_base/c/d.csv"),
        ("BUCKET/base_with_slash/", "BUCKET/base_with_slash/c/d.csv"),
    ],
)
@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_s3_file_system_copy(dest_base, result, mocked_s3):
    """Should copy within the same S3fs."""
    fs = mocked_s3[0]
    fs.s3fs.touch("BUCKET/a/b.csv")
    fs.copy("a/b.csv", "c/d.csv", dest_base)

    assert fs.s3fs.find(result)


@pytest.mark.parametrize(
    "kwargs,expected_object_count",
    [
        pytest.param({}, 4, id="All CSV objects"),
        pytest.param(dict(path="folder1"), 1, id="All CSV objects in folder1"),
        pytest.param(dict(withdirs=True), 8, id="All objects including all folders"),
        pytest.param(dict(maxdepth=1, withdirs=True), 3, id="All objects including all folders in root"),
        pytest.param(dict(maxdepth=2), 2, id="All CSV objects in root + 1st level folder"),
        (dict(constraint=lambda m: m["LastModified"] == datetime(2020, 1, 1, tzinfo=timezone.utc)), 1),
    ],
)
@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_s3_file_system_find(mocked_s3, kwargs, expected_object_count):
    """Should find the right files based on different criteria."""
    fs = mocked_s3[0]
    fs.s3fs.touch("BUCKET/file.csv")
    fs.s3fs.touch("BUCKET/folder1/sub_folder/file.csv")
    fs.s3fs.touch("BUCKET/folder2/file.csv")
    fs.s3fs.touch("BUCKET/folder2/sub_folder/file.csv")

    s3_backend.buckets["BUCKET"].keys["file.csv"].last_modified = datetime(2020, 1, 1)

    assert len(fs.find(**kwargs)) == expected_object_count


@pytest.mark.parametrize(
    "write_wrapper,kwargs",
    [
        pytest.param(lambda f: f, dict(), id="Normal mode"),
        pytest.param(lambda f: GzipFile(fileobj=f, mode="wb"), dict(unpack=True), id="Compressed file"),
    ],
)
@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_s3_file_system_open(mocked_s3, write_wrapper, kwargs):
    """Should open and read files properly."""
    fs = mocked_s3[0]
    with fs.s3fs.open("BUCKET/file.csv", "wb") as f:
        write_wrapper(f).write(b"a,b,c\n")

    with fs.open("file.csv", **kwargs) as f:
        assert f.read() == b"a,b,c\n"


@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_s3_file_system_open_write(mocked_s3):
    """Should allow opening in write mode."""
    fs = mocked_s3[0]
    with fs.open("file.csv", "wb") as f:
        f.write(b"a,b,c\n")

    with fs.s3fs.open("BUCKET/file.csv", "rb") as f:
        assert f.read() == b"a,b,c\n"


@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_s3_file_system_open_write_with_unpack(mocked_s3):
    """Should fail to unpack in write mode."""
    fs = mocked_s3[0]
    with pytest.raises(RuntimeError):
        fs.open("file.csv", "wb", unpack=True).__enter__()


@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_s3_file_system_info(mocked_s3):
    """Should list file metadata within basepath only."""
    fs = mocked_s3[0]
    fs.s3fs.touch("BUCKET/file.csv")

    assert fs.info("file.csv")
    with pytest.raises(FileNotFoundError):
        fs.info("BUCKET/file.csv")


@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_s3_file_system_rm(mocked_s3):
    """Should unlink file."""
    fs = mocked_s3[0]
    fs.s3fs.touch("BUCKET/file.csv")

    fs.info("file.csv")
    fs.rm("file.csv")
    with pytest.raises(FileNotFoundError):
        fs.info("file.csv")


def random_hash():
    """Get random MD5 hash-like value."""
    return f"{random.getrandbits(128):x}"


SAMPLE_HASH = random_hash()
SAMPLE_DIFFERENT_HASH = random_hash()


@pytest.fixture(name="s3file")
def s3file_factory(mocker):
    """S3File factory for indirect fixtures."""
    # pydocstyle: D202
    def s3file(key, metadata, client_flags):
        mocked_client = mocker.Mock(spec=s3.S3FileSystem)
        mocked_client.info.return_value = metadata
        mocked_client.flags = client_flags

        return s3.S3File(mocked_client, key)

    return s3file


@pytest.mark.parametrize(
    "other_file_meta,result",
    [
        (("key/is/ignored.csv", dict(etag=SAMPLE_HASH, size=1), dict()), True),
        (("key/is/ignored.csv", dict(etag="not-a-hash", size=1), dict()), True),
        (("key/is/ignored.csv", dict(etag=SAMPLE_HASH, size=1), dict(flags="differs")), True),
        (("key/is/ignored.csv", dict(etag=SAMPLE_DIFFERENT_HASH, size=1), dict()), False),
        (("key/is/ignored.csv", dict(etag="not-a-hash", size=2), dict()), False),
    ],
)
def test_s3_file_eq(s3file, other_file_meta, result):
    """Should compare S3Files."""
    file = s3file("key/doesnt/matter.csv", dict(etag=SAMPLE_HASH, size=1), dict())
    other_file = s3file(*other_file_meta)

    assert (file == other_file) == result


def test_s3_file_eq_to_different_type(s3file):
    """Should not compare to other types."""
    file = s3file("key/doesnt/matter.csv", dict(etag=SAMPLE_HASH, size=1), dict())

    assert (file == "a") is False


def test_s3_file_info(s3file):
    """S3File info property should call S3 client only once."""
    f = s3file("key", dict(etag="", size=1), dict())

    assert f.info == dict(etag="", size=1)
    f.info
    f.client.info.assert_called_once_with("key")
