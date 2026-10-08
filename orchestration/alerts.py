"""Email alert when a pipeline run fails.

Set these environment variables to send alerts:

    ALERT_SMTP_HOST      mail server (required; without it, failures are only logged)
    ALERT_SMTP_PORT      default 587 (STARTTLS)
    ALERT_SMTP_USER      optional login
    ALERT_SMTP_PASSWORD  optional login password
    ALERT_FROM           sender address
    ALERT_TO             recipient address
"""

import os
import smtplib
from collections.abc import Mapping, Sequence
from email.message import EmailMessage


def alert_settings(env: Mapping[str, str] = os.environ) -> dict | None:
    """SMTP settings from the environment, or None if alerts aren't configured."""
    host = env.get("ALERT_SMTP_HOST")
    sender, recipient = env.get("ALERT_FROM"), env.get("ALERT_TO")
    if not (host and sender and recipient):
        return None
    return {
        "host": host,
        "port": int(env.get("ALERT_SMTP_PORT", "587")),
        "user": env.get("ALERT_SMTP_USER"),
        "password": env.get("ALERT_SMTP_PASSWORD"),
        "sender": sender,
        "recipient": recipient,
    }


def build_alert(
    job_name: str,
    run_id: str,
    failed_steps: Sequence[str],
    error: str,
    sender: str,
    recipient: str,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"[sap-o2c-pipeline] {job_name} failed (run {run_id[:8]})"
    message["From"] = sender
    message["To"] = recipient
    steps = ", ".join(failed_steps) or "none reported"
    message.set_content(
        f"Job: {job_name}\nRun: {run_id}\nFailed steps: {steps}\n\nError:\n{error}\n"
    )
    return message


def send_alert(message: EmailMessage, settings: Mapping) -> None:
    with smtplib.SMTP(settings["host"], settings["port"], timeout=30) as smtp:
        smtp.starttls()
        if settings["user"]:
            smtp.login(settings["user"], settings["password"] or "")
        smtp.send_message(message)
