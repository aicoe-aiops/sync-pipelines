"""Test suite for solgate/report.py."""

from json import dumps
import pytest

from solgate import report


@pytest.fixture
def context() -> dict:
    """Alert context fixture base."""
    return dict(
        name="instance_name",
        namespace="argo-project",
        status="success",
        host="argo-ui-host.com",
        timestamp="2020-01-01 10:00:00 +0000 UTC",
    )


@pytest.fixture
def smtp(mocker):
    """SMTP fixture as a mock."""
    mocked_smtp = mocker.patch("smtplib.SMTP")

    def _get_sent_message():
        return mocked_smtp.return_value.__enter__.return_value.send_message.call_args.args[0]

    mocked_smtp.get_sent_message = _get_sent_message

    return mocked_smtp


def test_render_from_template(mocker):
    """Should render Jinja2."""
    mocked_open = mocker.mock_open(read_data="{{ variable }}\n")
    mocker.patch("builtins.open", mocked_open)
    assert report.render_from_template("stub_filename", dict(variable="value")) == "value"


def test_send_report_default(context, mocker, smtp):
    """Should use default SMTP and email values if they are not set in the config."""
    render = mocker.spy(report, "render_from_template")
    report.send_report(context, "", {})

    assert render.call_count == 2
    smtp.assert_called_once_with(report.DEFAULT_SMTP_SERVER)
    assert smtp.get_sent_message()["From"] == report.DEFAULT_SENDER
    assert smtp.get_sent_message()["To"] == report.DEFAULT_RECIPIENT

    for p in smtp.get_sent_message().iter_parts():
        content = p.get_content()
        assert all([v in content for v in context.values()])


def test_send_report_custom_config(context, smtp):
    """Should use values from custom config file."""
    config = dict(alerts_from="solgate@example.com", alerts_to="sre@example.com", alerts_smtp_server="smtp.example.com")
    report.send_report(context, "", config)

    smtp.assert_called_once_with("smtp.example.com")
    assert smtp.get_sent_message()["From"] == "solgate@example.com"
    assert smtp.get_sent_message()["To"] == "sre@example.com"


def test_send_report_no_context(smtp):
    """Should fail to send empty message."""
    with pytest.raises(SystemExit):
        report.send_report({}, "", {})


def test_send_report_with_failures(context, smtp):
    """Should render failures."""
    failure = {
        "displayName": "failed-step-name",
        "message": "failed with exit code 1",
        "templateName": "template_x_y_z",
        "podName": "failed-step-name-pod-123456",
        "phase": "Failed",
        "finishedAt": "2020-01-01 10:00:00 +0000 UTC",
    }
    failures = f'"{dumps([failure])}"'
    report.send_report(context, failures, {})

    for p in smtp.get_sent_message().iter_parts():
        content = p.get_content()
        assert "Failures:" in content
        assert all([v in content for v in failure.values()])


@pytest.mark.parametrize(
    "input,output", [('"[]"', []), ('"[{}]"', [dict()]), ('"[{"key":"value"}]"', [dict(key="value")]), ("[]", [])],
)
def test_decode_failures(input, output):
    """Should decode escaped serialized json."""
    assert report.decode_failures(input) == output


@pytest.mark.parametrize("input", [None, "", '""', '"[', '"\\"this is a string\\""', '"2"'])
def test_decode_failures_negative(input):
    """Should raise ValueError when unable to decode serialized json to list of failures."""
    with pytest.raises(ValueError):
        report.decode_failures(input)
