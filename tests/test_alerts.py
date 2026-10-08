from email import message_from_string
from unittest import mock

from orchestration.alerts import alert_settings, build_alert, send_alert


def test_no_alert_settings_without_host_sender_and_recipient():
    assert alert_settings({}) is None
    assert alert_settings({"ALERT_SMTP_HOST": "smtp.example.com"}) is None


def test_settings_read_from_environment():
    settings = alert_settings({
        "ALERT_SMTP_HOST": "smtp.example.com",
        "ALERT_SMTP_PORT": "2525",
        "ALERT_FROM": "pipeline@example.com",
        "ALERT_TO": "me@example.com",
    })
    assert settings["port"] == 2525
    assert settings["user"] is None


def test_alert_names_job_run_steps_and_error():
    msg = build_alert(
        job_name="daily_pipeline",
        run_id="abcdef1234567890",
        failed_steps=["raw_tables"],
        error="Failed to load VBAK_20260101.csv",
        sender="pipeline@example.com",
        recipient="me@example.com",
    )
    parsed = message_from_string(msg.as_string())
    assert parsed["To"] == "me@example.com"
    assert "daily_pipeline failed (run abcdef12)" in parsed["Subject"]
    body = parsed.get_payload()
    assert "raw_tables" in body and "VBAK_20260101.csv" in body


def test_send_uses_starttls_and_login_when_configured():
    settings = {"host": "smtp.example.com", "port": 587, "user": "u", "password": "p"}
    msg = build_alert("j", "r", [], "e", "a@example.com", "b@example.com")
    with mock.patch("orchestration.alerts.smtplib.SMTP") as smtp:
        send_alert(msg, settings)
    server = smtp.return_value.__enter__.return_value
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("u", "p")
    server.send_message.assert_called_once_with(msg)
