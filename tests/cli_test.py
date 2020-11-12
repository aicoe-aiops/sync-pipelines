"""Test suite for solgate/cli.py."""

from pathlib import Path
from click.testing import CliRunner
import pytest

from solgate.cli import cli, logger


@pytest.fixture
def run():
    """Run CLI command from within the solgate command context."""
    runner = CliRunner()
    return lambda args, env={}: runner.invoke(cli, args, env=env)


def test_version(run):
    """Should return someting for version command."""
    assert "Solgate version" in run(["version"]).output


def context(**kwargs):
    """Dynamic fixture for parametrized tests updating default config."""
    defaults = dict(filename="config.yaml", path=Path("/etc/solgate"))
    defaults.update(kwargs)
    return defaults


@pytest.mark.parametrize(
    "cli_args,func_args,file_output",
    [
        (["list"], [context()], False),
        (["-c", ".", "list"], [context(path=Path("."))], False),
        (["list", "-o", "output.json"], [context()], True),
    ],
)
def test_list(run, mocker, cli_args, func_args, file_output):
    """Should call proper functions on list command."""
    mocked_list_source = mocker.patch("solgate.cli.list_source", return_value=["list", "of", "files"])
    mocked_serialize = mocker.patch("solgate.cli.serialize")

    result = run(cli_args)

    assert result.exit_code == 0
    mocked_list_source.assert_called_once_with(*func_args)

    if file_output:
        mocked_serialize.assert_called_once_with(["list", "of", "files"], "output.json")
    else:
        mocked_serialize.assert_not_called()
        assert "['list', 'of', 'files']\n" in result.output


def test_list_negative(run, mocker):
    """Should fail on list command."""
    mocker.patch("solgate.cli.list_source", side_effect=EnvironmentError)

    result = run("list")

    assert result.exit_code == 1


@pytest.mark.parametrize(
    "cli_args,func_args",
    [
        (["send", "key"], [[dict(relpath="key")], context()]),
        (["send", "-l", "."], [[dict(relpath="file/key")], context()]),
        (["-c", ".", "send", "key"], [[dict(relpath="key")], context(path=Path("."))]),
    ],
)
def test_send(run, mocker, cli_args, func_args):
    """Should call proper functions on sync command."""
    mocked_send = mocker.patch("solgate.cli.send")
    mocker.patch("solgate.cli.deserialize", return_value=[dict(relpath="file/key")])

    result = run(cli_args)

    assert result.exit_code == 0
    mocked_send.assert_called_once_with(*func_args)


@pytest.mark.parametrize(
    "kwargs,cli_args",
    [
        (dict(side_effect=RuntimeError), ["send", "key"]),
        (dict(return_value=False), ["send", "key"]),
        (dict(), ["send"]),
    ],
)
def test_send_negative(run, mocker, kwargs, cli_args):
    """Should fail on sync failure."""
    mocker.patch("solgate.cli.send", **kwargs)

    result = run(cli_args)

    assert result.exit_code == 1


context_keys = ["name", "namespace", "status", "host", "timestamp"]


@pytest.mark.parametrize(
    "cli_args,func_args,env",
    [
        (["report"], [[None, None, None, None, None], "", {}], dict()),
        (
            (
                "report "
                "-n name --failures failures --namespace namespace -s status --host host -t timestamp "
                "--from nobody@example.com --to somebody@example.com --smtp smtp.example.com"
            ).split(),
            [
                context_keys,
                "failures",
                dict(
                    alerts_from="nobody@example.com",
                    alerts_to="somebody@example.com",
                    alerts_smtp_server="smtp.example.com",
                ),
            ],
            dict(),
        ),
        (
            ["report"],
            [
                context_keys,
                "failures",
                dict(
                    alerts_from="nobody@example.com",
                    alerts_to="somebody@example.com",
                    alerts_smtp_server="smtp.example.com",
                ),
            ],
            dict(
                WORKFLOW_NAME="name",
                WORKFLOW_FAILURES="failures",
                WORKFLOW_NAMESPACE="namespace",
                WORKFLOW_STATUS="status",
                ARGO_UI_HOST="host",
                WORKFLOW_TIMESTAMP="timestamp",
                ALERT_SENDER="nobody@example.com",
                ALERT_RECIPIENT="somebody@example.com",
                SMTP_SERVER="smtp.example.com",
            ),
        ),
        (
            ["-c", "REPLACED_WITH_FIXTURE_DIR", "--config-filename", "general_section_only.yaml", "report"],
            [
                [None, None, None, None, None],
                "",
                dict(
                    alerts_from="solgate@example.com",
                    alerts_to="sre@example.com",
                    alerts_smtp_server="smtp.example.com",
                ),
            ],
            dict(),
        ),
    ],
)
def test_report(run, mocker, cli_args, func_args, fixture_dir, env):
    """Should call send_report on report reprot command."""
    mocked_report = mocker.patch("solgate.cli.send_report")

    logger_spy = None
    if cli_args[0] == "-c":
        cli_args[1] = fixture_dir
    else:
        # If config wasn't specified, spy for a warning
        logger_spy = mocker.spy(logger, "warn")

    run(cli_args, env)

    func_args[0] = {k: v for k, v in zip(context_keys, func_args[0])}
    mocked_report.assert_called_once_with(*func_args)

    if logger_spy:
        logger_spy.assert_called_once_with(
            "Config file is not present or not valid, alerting to/from default email address."
        )
