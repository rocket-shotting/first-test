"""Email notifications via Gmail SMTP (App Password auth)."""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


def send_email(
    *,
    sender_address: str,
    app_password: str,
    to_address: str,
    subject: str,
    body: str,
) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender_address
    msg["To"] = to_address

    with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(sender_address, app_password)
        server.sendmail(sender_address, [to_address], msg.as_string())
