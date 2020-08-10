"""Email alerting and notifications from Argo."""

import smtplib
from email.message import EmailMessage
from json import loads
from typing import Dict, Union
from pathlib import Path

from jinja2 import Template

from .utils import logger, read_general_config

TEMPLATE_HTML = Path(__file__).absolute().parent / "utils" / "email_alert_template.html"
TEMPLATE_PLAINTEXT = Path(__file__).absolute().parent / "utils" / "email_alert_template.txt"

DEFAULT_SENDER = "solgate-alerts@redhat.com"
DEFAULT_RECIPIENT = "data-hub-alerts@redhat.com"
DEFAULT_SMTP_SERVER = "smtp.corp.redhat.com"


def render_from_template(template_filename: Union[str, Path], context: Dict[str, str]) -> str:
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
    # Deserialize 'failures' JSON string
    try:
        failures_deserialized = loads(failures)
    except (ValueError, TypeError):
        failures_deserialized = []

    context = dict(name=name, namespace=namespace, status=status, timestamp=timestamp, host=host)
    if not all(context.values()):
        logger.error("Alert content is not passed properly")
        exit(1)

    context["failures"] = failures_deserialized

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
