"""Email actions — send and check email via SMTP/IMAP."""

import asyncio
import smtplib
import imaplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from utils.config import load_config


async def send_email(recipient: str, subject: str, body: str) -> dict:
    """
    Send email via SMTP.

    Args:
        recipient: Email address to send to
        subject: Email subject line
        body: Email body text

    Returns:
        {"status": "ok"/"error", "result": str}
    """
    try:
        # Load email config from settings.yaml
        config = load_config("configs/settings.yaml").get("email", {})
        smtp_server = config.get("smtp_server", "smtp.gmail.com")
        smtp_port = config.get("smtp_port", 587)
        sender_email = config.get("sender_email")
        sender_password = config.get("sender_password")

        if not sender_email or not sender_password:
            logger.error("Email credentials not configured (sender_email, sender_password)")
            return {
                "status": "error",
                "result": "Email not configured. Add credentials to configs/settings.yaml"
            }

        # Validate recipient
        recipient = recipient.strip()
        if "@" not in recipient:
            return {"status": "error", "result": f"Invalid email address: {recipient}"}

        logger.debug(f"Sending email to {recipient} via {smtp_server}:{smtp_port}")

        # Create message
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Send async via executor (SMTP blocks)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _send_smtp,
            smtp_server,
            smtp_port,
            sender_email,
            sender_password,
            recipient,
            msg.as_string()
        )

        logger.info(f"Email sent to {recipient}")
        return {
            "status": "ok",
            "result": f"Email sent to {recipient}"
        }

    except Exception as e:
        logger.error(f"send_email error: {e}")
        return {"status": "error", "result": str(e)}


async def check_email() -> dict:
    """
    Check unread email count and latest subject.

    Returns:
        {"status": "ok"/"error", "result": str with count and latest subject}
    """
    try:
        # Load email config from settings.yaml
        config = load_config("configs/settings.yaml").get("email", {})
        imap_server = config.get("imap_server", "imap.gmail.com")
        receiver_email = config.get("receiver_email")
        receiver_password = config.get("receiver_password")

        if not receiver_email or not receiver_password:
            logger.error("Email credentials not configured for IMAP")
            return {
                "status": "error",
                "result": "Email not configured. Add IMAP credentials to configs/settings.yaml"
            }

        logger.debug(f"Checking email on {imap_server}")

        # Check async via executor (IMAP blocks)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _check_imap,
            imap_server,
            receiver_email,
            receiver_password
        )

        logger.info(f"Email check: {result}")
        return {
            "status": "ok",
            "result": result
        }

    except Exception as e:
        logger.error(f"check_email error: {e}")
        return {"status": "error", "result": str(e)}


def _send_smtp(smtp_server: str, smtp_port: int, sender: str, password: str, recipient: str, message: str):
    """Blocking SMTP send. Run in executor."""
    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, message)


def _check_imap(imap_server: str, email: str, password: str) -> str:
    """Blocking IMAP check. Run in executor."""
    with imaplib.IMAP4_SSL(imap_server, timeout=10) as imap:
        imap.login(email, password)
        imap.select("INBOX")

        # Count unread
        _, unread_ids = imap.search(None, "UNSEEN")
        unread_count = len(unread_ids[0].split())

        # Get latest subject
        _, latest = imap.search(None, "ALL")
        if latest[0]:
            latest_id = latest[0].split()[-1]
            _, msg_data = imap.fetch(latest_id, "(BODY[HEADER.FIELDS (SUBJECT)])")
            subject = msg_data[0][1].decode().split("Subject: ")[-1].strip()
        else:
            subject = "(no emails)"

        return f"You have {unread_count} unread emails. Latest: {subject}"
