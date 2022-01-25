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
        (["list"], [context(), False], False),
        (["list", "--backfill", "false"], [context(), False], False),
        (["list", "--backfill", "true"], [context(), True], False),
        (["-c", ".", "list"], [context(path=Path(".")), False], False),
        (["list", "-o", "output.json"], [context(), False], True),
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
        calls = [mocker.call(f, "output.json") for f in ("list", "of", "files")]
        mocked_serialize.assert_has_calls(calls)
    else:
        mocked_serialize.assert_not_called()
        assert "list\nof\nfiles\n" in result.output


@pytest.mark.parametrize(
    "side_effect,errno", [(RuntimeError, 1), (ValueError("msg"), 2), (FileNotFoundError("msg"), 3),],
)
def test_list_negative(run, mocker, side_effect, errno):
    """Should fail on list command."""
    mocker.patch("solgate.cli.list_source", side_effect=side_effect)

    result = run("list")

    assert result.exit_code == errno


@pytest.mark.parametrize(
    "cli_args,func_args",
    [
        (["send", "key"], [[dict(key="key")], context(), 1, False]),
        (["send", "-l", "."], [[dict(key="file/key")], context(), 1, False]),
        (["-c", ".", "send", "key"], [[dict(key="key")], context(path=Path(".")), 1, False]),
        (["send", "key", "--dry-run"], [[dict(key="key")], context(), 1, True]),
        (["send", "key", "-n"], [[dict(key="key")], context(), 1, True]),
    ],
)
def test_send(run, mocker, cli_args, func_args):
    """Should call proper functions on sync command."""
    mocked_send = mocker.patch("solgate.cli.send")
    mocker.patch("solgate.cli.deserialize", return_value=([dict(key="file/key")], 1))

    result = run(cli_args)

    assert result.exit_code == 0
    mocked_send.assert_called_once_with(*func_args)


@pytest.mark.parametrize(
    "side_effect,cli_args,errno",
    [
        (RuntimeError, ["send", "key"], 1),
        (ValueError("msg"), ["send"], 2),
        (FileNotFoundError("msg"), ["send", "key"], 3),
        (IOError("msg"), ["send", "key"], 4),
    ],
)
def test_send_negative(run, mocker, side_effect, cli_args, errno):
    """Should fail on sync failure."""
    mocker.patch("solgate.cli.send", side_effect=side_effect)

    result = run(cli_args)

    assert result.exit_code == errno


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
        logger_spy = mocker.spy(logger, "warning")

    run(cli_args, env)

    func_args[0] = {k: v for k, v in zip(context_keys, func_args[0])}
    mocked_report.assert_called_once_with(*func_args)

    if logger_spy:
        logger_spy.assert_called_once_with(
            "Config file is not present or not valid, alerting to/from default email address."
        )


def test_report_negative(run, mocker):
    """Should fail on list command."""
    mocker.patch("solgate.cli.list_source", side_effects=ValueError("msg"))

    result = run("report")

    assert result.exit_code == 2
