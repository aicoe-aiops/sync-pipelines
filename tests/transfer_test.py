"""Test suite for solgate/transfer.py."""

from pathlib import Path
import pytest

from solgate import transfer
from solgate.utils import S3File


@pytest.mark.parametrize(
    "file_list", ([dict(relpath="a/b/file.csv")], [dict(relpath="a/b/file1.csv"), dict(relpath="a/b/file2.csv")])
)
def test_send(mocker, file_list, mocked_solgate_s3_file_system):
    """Should request files to be sent to clients."""
    mocked_transfer_single_file = mocker.patch("solgate.transfer._transfer_single_file")

    transfer.send(file_list, {})

    for f in file_list:
        mocked_transfer_single_file.assert_any_call(f["relpath"], [mocked_solgate_s3_file_system])


@pytest.mark.parametrize("file_list", ([], [dict()], [dict(not_a_key="a/b/file.csv")], [dict(key="file.csv"), dict()]))
def test_send_no_key(mocker, file_list, mocked_solgate_s3_file_system):
    """Should fail to transfer files where the key is missing."""
    mocker.patch("solgate.transfer._transfer_single_file")

    assert transfer.send(file_list, {}) is False


def test_send_not_configured_properly(mocker):
    """Should fail without config file."""
    mocker.patch("builtins.open", side_effect=FileNotFoundError)

    assert transfer.send([], dict(filename="this.yaml", path=Path("/doesnt/exist"))) is False


def test_send_unable_to_transfer(mocker, mocked_solgate_s3_file_system):
    """Should log failures."""
    mocker.patch("solgate.transfer._transfer_single_file", return_value=False)

    spy_send = mocker.spy(transfer.logger, "error")
    assert transfer.send([dict(relpath="a/b/file.csv")], {}) is False
    spy_send.assert_called_with(mocker.ANY, dict(failed_files=[dict(relpath="a/b/file.csv")]))


@pytest.mark.parametrize("mocked_s3", ["sample_config.yaml"], indirect=["mocked_s3"])
def test_calc_s3_files(mocked_s3):
    """Should return parsed object keys for source and all destinations with formatter."""
    gen = lambda: transfer.calc_s3_files("2020-01-01/collection_name.csv.gz", mocked_s3)  # noqa

    assert [(f.client.name, f.key) for f in gen()] == [
        ("source", "2020-01-01/collection_name.csv.gz"),
        ("destination.0", "collection_name/historic/2020-01-01-collection_name.csv"),
        ("destination.1", "collection_name/latest/full_data.csv"),
        ("destination.2", "2020-01-01/collection_name.csv.gz"),
    ]


@pytest.mark.parametrize("mocked_s3", ["without_source_formatter.yaml"], indirect=["mocked_s3"])
def test_calc_s3_files_without_formatter(mocked_s3):
    """Should return parsed object keys for source and all destinations without formatter."""
    gen = lambda: transfer.calc_s3_files("2020-01-01/collection_name.csv.gz", mocked_s3)  # noqa
    assert [f.key for f in gen()] == ["2020-01-01/collection_name.csv.gz"] * 4
    assert [f.client.name for f in gen()] == ["source", "destination.0", "destination.1", "destination.2"]


@pytest.mark.parametrize("mocked_s3", ["sample_config.yaml"], indirect=["mocked_s3"])
def test__transfer_single_file(mocked_s3):
    """Should transfer and verify file."""
    mocked_s3[0].s3fs.touch("DH-PLAYPEN/storage/input/2020-01-01/collection_name.csv.gz")

    files = [
        "2020-01-01/collection_name.csv.gz",
        "collection_name/historic/2020-01-01-collection_name.csv",
        "collection_name/latest/full_data.csv",
        "2020-01-01/collection_name.csv.gz",
    ]

    assert transfer._transfer_single_file("2020-01-01/collection_name.csv.gz", mocked_s3)
    assert all([mocked_s3[idx].info(f) for idx, f in enumerate(files)])


@pytest.mark.parametrize("mocked_s3", ["same_client.yaml", "same_flags.yaml"], indirect=["mocked_s3"])
def test__transfer_single_file_same_client(mocked_s3):
    """Should transfer faster between the same clients."""
    mocked_s3[0].s3fs.touch("BUCKET/a/b.csv")
    files = ["a/b.csv", "a-copy/b.csv"]

    assert transfer._transfer_single_file("a/b.csv", mocked_s3)
    assert all([mocked_s3[idx].info(f) for idx, f in enumerate(files)])


@pytest.mark.parametrize("mocked_s3", ["sample_config.yaml"], indirect=["mocked_s3"])
def test__transfer_single_file_unable_to_verify(mocked_s3, mocker):
    """Should return False on verification failure."""
    mocked_s3[0].s3fs.touch("DH-PLAYPEN/storage/input/2020-01-01/collection_name.csv.gz")
    mocker.patch("solgate.transfer.verify", return_value=False)

    assert transfer._transfer_single_file("2020-01-01/collection_name.csv.gz", mocked_s3) is False


@pytest.mark.parametrize("mocked_s3", ["sample_config.yaml"], indirect=["mocked_s3"])
def test__transfer_single_file_fails(mocked_s3):
    """Should return False if unable to transfer."""
    mocked_s3[0].s3fs.touch("DH-PLAYPEN/storage/input/2020-01-01/collection_name.csv.gz")
    destination_client = mocked_s3[1]
    destination_client._S3FileSystem__base_path = "BUCKET-DOESNT-EXIST"

    assert transfer._transfer_single_file("2020-01-01/collection_name.csv.gz", mocked_s3) is False


@pytest.mark.parametrize("mocked_s3", ["same_client.yaml"], indirect=["mocked_s3"])
def test_copy_same_client(mocked_s3, mocker):
    """Should use client.copy when the clients are the same."""
    mocked_s3[0].s3fs.touch("BUCKET/a/b.csv")
    spies_copy = [mocker.spy(client, "copy") for client in mocked_s3]
    spies_open = [mocker.spy(client, "open") for client in mocked_s3]

    transfer.copy([S3File(client, "a/b.csv") for client in mocked_s3])

    [spy.assert_not_called() for spy in spies_open]
    spies_copy[0].assert_called_once_with("a/b.csv", "a/b.csv")
    spies_copy[1].assert_not_called()


@pytest.mark.parametrize("mocked_s3", ["same_flags.yaml"], indirect=["mocked_s3"])
def test_copy_same_flags(mocked_s3, mocker):
    """Should open the files with equal settings if the client differs but the flags are the same."""
    mocked_s3[0].s3fs.touch("BUCKET/a/b.csv")
    spies = [mocker.spy(client, "open") for client in mocked_s3]

    transfer.copy([S3File(client, "a/b.csv") for client in mocked_s3])

    spies[0].assert_called_once_with("a/b.csv", "rb")
    spies[1].assert_called_once_with("a/b.csv", "wb")


@pytest.mark.parametrize("mocked_s3", ["different_clients.yaml"], indirect=["mocked_s3"])
def test_copy_different_clients(mocked_s3, mocker):
    """Should pass on flags if the client flags differ."""
    mocked_s3[0].s3fs.touch("BUCKET/a/b.csv.gz")
    spies = [mocker.spy(client, "open") for client in mocked_s3]
    files = [S3File(mocked_s3[0], "a/b.csv.gz"), S3File(mocked_s3[1], "a/b.csv")]

    transfer.copy(files)
    spies[0].assert_called_once_with("a/b.csv.gz", "rb", unpack=True)
    spies[1].assert_called_once_with("a/b.csv", "wb")
