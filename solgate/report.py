"""Email alerting and notifications from Argo."""

import smtplib
from email.message import EmailMessage
from json import loads
from typing import Dict, Union, Any
from pathlib import Path

from jinja2 import Template

from .utils import logger, read_general_config

TEMPLATE_HTML = Path(__file__).absolute().parent / "utils" / "email_alert_template.html"
TEMPLATE_PLAINTEXT = Path(__file__).absolute().parent / "utils" / "email_alert_template.txt"

DEFAULT_SENDER = "solgate-alerts@redhat.com"
DEFAULT_RECIPIENT = "data-hub-alerts@redhat.com"
DEFAULT_SMTP_SERVER = "smtp.corp.redhat.com"


def render_from_template(template_filename: Union[str, Path], context: Dict[str, Any]) -> str:
    """Render email content via a template.

    Args:
        template_filename ([type]): Filename.
        context (Dict[str, str]): Variables used to render the template.

    Returns:
        str: Rendered template.

    """
    with open(template_filename) as f:
        template = Template(f.read())

    return template.render(**context)


def decode_failures(failures: str) -> list:
    """Deserialize failed nodes list from Argo.

    Argo passess the WORKFLOW_FAILURES as a JSON list serialized into a escaped string. Unfortunately when this list
    is stored in an environment variable it gets escaped twice (the string starts with a " and all quote chars are
    escaped as well...). This decoder solves that by encoding the string back to bytes and then decoding it as an
    `unicode_escape`d string.

    Args:
        failures(str): JSON string representing failed workflow steps

    Raises:
        ValueError: When unable to parse value

    Returns:
        list: Deserialized failures

    """
    try:
        failures = failures.encode().decode("unicode_escape")
        # Argo passes failures as a quoted string '"[...]"', we need to strip them first (first and last letter)
        failures = failures[1:-1] if failures.startswith('"') else failures
        failures_deserialized = loads(failures)

        if not isinstance(failures_deserialized, list):
            raise TypeError("Not a list")

        return failures_deserialized

    except (AttributeError, ValueError, TypeError) as e:
        raise ValueError(e)


def send_report(
    name: str, namespace: str, status: str, host: str, timestamp: str, failures: str, config_file: str = None
) -> None:
    """Send an email notification.

    Args:
        name (str): Workflow instance name.
        namespace (str): Project namespace where the workflow was executed.
        status (str): Current status of the workflow execution.
        host (str): Argo UI external facing route host, which can be used to format hyperlinks to
            given workflow execution.
        timestamp (str): Execution timestamp.
        failures (str): JSON string representing failed workflow steps (listing properties described
            here https://github.com/argoproj/argo/blob/master/docs/variables.md#exit-handler)
        config_file (str, optional): Path to configuration file.

    """
    config = read_general_config(config_file)

    context: Dict[str, Any] = dict(name=name, namespace=namespace, status=status, timestamp=timestamp, host=host)
    if not all(context.values()):
        logger.error("Alert content is not passed properly")
        exit(1)

    try:
        context["failures"] = decode_failures(failures)
    except ValueError:
        logger.error("Unable to parse workflow failures", exc_info=True)
        context["failures"] = []

    logger.info("Sending email alert")

    msg = EmailMessage()
    msg["Subject"] = f"[{namespace}][{name}] Argo workflow failed"
    msg["From"] = config.get("alerts_from", DEFAULT_SENDER)
    msg["To"] = config.get("alerts_to", DEFAULT_RECIPIENT)

    msg.set_content(render_from_template(TEMPLATE_PLAINTEXT, context))
    msg.add_alternative(render_from_template(TEMPLATE_HTML, context), subtype="html")

    with smtplib.SMTP(config.get("alerts_smtp_server", DEFAULT_SMTP_SERVER)) as smtp:
        smtp.send_message(msg)

    logger.info("Done")
