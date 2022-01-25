"""Contest for solgate testsuite."""

from pathlib import Path
from importlib import reload

import pytest
import s3fs
import boto3
from moto import mock_s3
from solgate.utils import S3FileSystem


@pytest.fixture(scope="session")
def fixture_dir():
    """Locate fixtures directory in the test folder."""
    return Path(__file__).absolute().parent / "fixtures"


@pytest.fixture
def mocked_s3(fixture_dir, request):
    """Yield S3FileSystem S3 clients with mocked backend."""
    with mock_s3():
        s3fs_instances = S3FileSystem.from_config_file(dict(path=fixture_dir, filename=request.param))
        for instance in s3fs_instances:
            instance.s3fs = s3fs.S3FileSystem(key=instance.aws_access_key_id, secret=instance.aws_secret_access_key)
            instance.s3fs.s3.create_bucket(Bucket=instance._S3FileSystem__base_path.split("/")[0])
            instance.s3_client = boto3.resource(
                "s3", aws_access_key_id=instance.aws_access_key_id, aws_secret_access_key=instance.aws_secret_access_key
            )
            instance.s3c = boto3.client(
                "s3", aws_access_key_id=instance.aws_access_key_id, aws_secret_access_key=instance.aws_secret_access_key
            )
            instance.boto3 = instance.s3_client.Bucket(instance._S3FileSystem__base_path.split("/")[0])
            instance.s3_client.create_bucket(Bucket=instance._S3FileSystem__base_path.split("/")[0])
        yield s3fs_instances


@pytest.fixture
def mocked_solgate_s3_file_system(mocker):
    """Stub S3FileSystem without mocking S3."""
    mocked_s3_fs = mocker.patch("solgate.transfer.S3FileSystem")
    mocked_s3_fs.from_config_file.return_value = [mocked_s3_fs]
    return mocked_s3_fs


@pytest.fixture
def disable_backoff(mocker, request):
    """Disable backoff retry decorator."""
    mocker.patch("backoff.on_exception", lambda *_, **__: lambda x: x)
    reload(request.param)
