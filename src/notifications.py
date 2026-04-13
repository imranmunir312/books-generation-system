import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv


def email_notifications_enabled() -> bool:
    load_dotenv(override=True)
    return os.getenv("EMAIL_NOTIFICATIONS_ENABLED", "false").lower() == "true"


def send_email_notification(subject: str, body: str) -> None:
    load_dotenv(override=True)

    if not email_notifications_enabled():
        print("Email notification skipped: EMAIL_NOTIFICATIONS_ENABLED is not true.")
        return

    required_settings = {
        "SMTP_HOST": os.getenv("SMTP_HOST"),
        "SMTP_PORT": os.getenv("SMTP_PORT"),
        "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
        "SMTP_FROM_EMAIL": os.getenv("SMTP_FROM_EMAIL"),
        "SMTP_TO_EMAIL": os.getenv("SMTP_TO_EMAIL"),
    }
    missing_settings = [
        key for key, value in required_settings.items() if not value
    ]

    if missing_settings:
        print(
            "Email notification skipped: missing "
            + ", ".join(missing_settings)
            + "."
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = required_settings["SMTP_FROM_EMAIL"]
    message["To"] = required_settings["SMTP_TO_EMAIL"]
    message.set_content(body)

    smtp_port = int(required_settings["SMTP_PORT"])
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    with smtplib.SMTP(required_settings["SMTP_HOST"], smtp_port) as server:
        if use_tls:
            server.starttls()

        server.login(
            required_settings["SMTP_USERNAME"],
            required_settings["SMTP_PASSWORD"],
        )
        server.send_message(message)

    print("Email notification sent.")
