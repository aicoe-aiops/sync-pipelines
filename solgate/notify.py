"""Email alerting and notifications from Argo."""

import os
import smtplib
from email.message import EmailMessage
from json import loads
from jinja2 import Template

from .utils import logger

SMTP_SERVER = os.getenv("ALERT_EMAIL_SMTP_SERVER", "")
FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL")
TO_EMAIL_LIST = os.getenv("ALERT_TO_EMAIL_LIST", "").replace(";", ",").split(",")

FAILURES = os.getenv("WORKFLOW_FAILURES", "")
NAME = os.getenv("WORKFLOW_NAME")
NAMESPACE = os.getenv("WORKFLOW_NAMESPACE")
STATUS = os.getenv("WORKFLOW_STATUS")
TIMESTAMP = os.getenv("WORKFLOW_TIMESTAMP")
ARGO_UI_HOST = os.getenv("ARGO_UI_HOST")

TEMPLATE_HTML = "utils/email_alert_template.html"
TEMPLATE_PLAINTEXT = "utils/email_alert_template.txt"


def render_from_template(template_filename, failures) -> str:
    """Render email content via a template."""
    with open(template_filename) as f:
        template = Template(f.read())

    return template.render(
        name=NAME,
        namespace=NAMESPACE,
        status=STATUS,
        timestamp=TIMESTAMP,
        argo_ui_host=ARGO_UI_HOST,
        failures=failures,
    )


def notify() -> None:
    """Send an email notification."""
    if not all((SMTP_SERVER, FROM_EMAIL, TO_EMAIL_LIST)):
        logger.error("Alert email service not set up properly")
        exit(1)

    if not all((FAILURES, NAME, NAMESPACE, STATUS, TIMESTAMP)):
        logger.error("Alert content is not passed properly")

    logger.info("Sending email alert")

    msg = EmailMessage()
    msg["Subject"] = f"[{NAMESPACE}][{NAME}] Argo workflow failed"
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL_LIST

    try:
        failures = loads(FAILURES)
    except (ValueError, TypeError):
        failures = []

    msg.set_content(render_from_template(TEMPLATE_PLAINTEXT, failures))
    msg.add_alternative(render_from_template(TEMPLATE_HTML, failures), subtype="html")

    with smtplib.SMTP(SMTP_SERVER) as smtp:
        smtp.send_message(msg)

    logger.info("Done")
