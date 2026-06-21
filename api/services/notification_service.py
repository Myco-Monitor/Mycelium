"""
Notification Service for Mycelium

This module provides email and webhook notification functionality for alerts.
"""

import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from storage.tables import notification_log
from storage.db_utils import get_connection


logger = logging.getLogger("services.NotificationService")


class NotificationService:
    """Service for sending alert notifications via email and webhook."""

    def __init__(self, encryption_key: Optional[bytes] = None):
        self.logger = logging.getLogger("services.NotificationService")
        self._encryption_key = encryption_key

    def send_alert_notification(
        self, alert_id: int, rule: Dict[str, Any], device: Dict[str, Any], message: str
    ) -> bool:
        """
        Send notification for an alert based on rule configuration.

        Args:
            alert_id: ID of the triggered alert
            rule: Rule that triggered the alert
            device: Device information
            message: Alert message

        Returns:
            True if notification sent successfully
        """
        method = rule.get("notification_method", "ui")
        target = rule.get("notification_target")

        if method == "ui":
            # UI notifications are handled by the dashboard
            return True

        if method == "email":
            # Consolidated path: send via the Settings SMTP config (user_settings),
            # not the legacy notification_settings table. Recipient is the rule's
            # target, falling back to the configured smtp_to address.
            return self._send_email_via_user_settings(rule, device, message, target)

        if method == "webhook" and target:
            return self.send_webhook_alert(alert_id, target, rule, device, message)

        return False

    def _send_email_via_user_settings(
        self,
        rule: Dict[str, Any],
        device: Dict[str, Any],
        message: str,
        target: Optional[str],
    ) -> bool:
        """Send an alert email through EmailService (user_settings SMTP).

        This is the live email path. The legacy notification_settings-backed
        methods below (send_email_alert, save_email_settings, quiet hours, etc.)
        are kept dormant for now and are not used.
        """
        from api.services.email_service import EmailService

        subject = rule.get("rule_name") or "Environmental alert"
        alert_type = rule.get("severity") or "warning"
        device_name = device.get("device_name", "") or ""
        return EmailService().send_alert_email(
            subject=subject,
            body=message,
            alert_type=alert_type,
            device_name=device_name,
            to_override=target,
        )

    # Email notifications

    def send_email_alert(
        self,
        alert_id: int,
        recipient: str,
        rule: Dict[str, Any],
        device: Dict[str, Any],
        message: str,
    ) -> bool:
        """
        Send alert notification via email.

        Args:
            alert_id: Alert ID
            recipient: Email address
            rule: Rule configuration
            device: Device information
            message: Alert message

        Returns:
            True if sent successfully
        """
        settings = self._get_email_settings_for_recipient(recipient)
        if not settings or not settings.get("email_enabled"):
            self.logger.warning(f"Email not configured for {recipient}")
            return False

        # Check quiet hours
        if self._is_quiet_hours(settings):
            self.logger.info(f"Skipping email during quiet hours for {recipient}")
            return False

        # Build email
        subject = f"[Myco-Monitor Alert] {rule.get('rule_name', 'Alert')}"
        body = self._build_email_body(rule, device, message)

        try:
            self._send_smtp_email(settings, recipient, subject, body)

            notification_log.log_notification(
                alert_id=alert_id,
                notification_method="email",
                recipient=recipient,
                status="sent",
            )

            self.logger.info(f"Email sent to {recipient}")
            return True

        except Exception as e:
            notification_log.log_notification(
                alert_id=alert_id,
                notification_method="email",
                recipient=recipient,
                status="failed",
                error_message=str(e),
            )

            self.logger.error(f"Email failed to {recipient}: {e}")
            return False

    def _send_smtp_email(
        self, settings: Dict[str, Any], recipient: str, subject: str, body: str
    ):
        """Send email via SMTP."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.get("smtp_username", "mycelium@localhost")
        msg["To"] = recipient

        # Plain text version
        text_part = MIMEText(body, "plain")
        msg.attach(text_part)

        # HTML version
        html_body = self._build_html_email(body)
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)

        # Connect and send
        smtp_server = settings["smtp_server"]
        smtp_port = settings.get("smtp_port", 587)
        use_tls = settings.get("smtp_use_tls", 1)

        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            if use_tls:
                server.starttls()
            username = settings.get("smtp_username")
            password = settings.get("smtp_password_encrypted")
            if username and password:
                decrypted_password = self._decrypt_password(password)
                server.login(username, decrypted_password)
            server.send_message(msg)

    def _build_email_body(
        self, rule: Dict[str, Any], device: Dict[str, Any], message: str
    ) -> str:
        """Build plain text email body."""
        return f"""
Myco-Monitor Alert

Alert: {rule.get("rule_name", "Unknown")}
Type: {rule.get("rule_type", "unknown")}
Device: {device.get("device_name", "Unknown")} ({device.get("device_type", "unknown")})
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Message:
{message}

---
This is an automated alert from Myco-Monitor.
Log in to your dashboard to acknowledge or resolve this alert.
        """.strip()

    def _build_html_email(self, text_body: str) -> str:
        """Build HTML email from plain text."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .alert-box {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 20px; }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="alert-box">
        <pre style="white-space: pre-wrap;">{text_body}</pre>
    </div>
</body>
</html>
        """

    # Webhook notifications

    def send_webhook_alert(
        self,
        alert_id: int,
        webhook_url: str,
        rule: Dict[str, Any],
        device: Dict[str, Any],
        message: str,
    ) -> bool:
        """
        Send alert notification via webhook.

        Args:
            alert_id: Alert ID
            webhook_url: Webhook URL
            rule: Rule configuration
            device: Device information
            message: Alert message

        Returns:
            True if sent successfully
        """
        payload = {
            "event": "alert.triggered",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "alert": {
                "id": alert_id,
                "rule_name": rule.get("rule_name"),
                "rule_type": rule.get("rule_type"),
                "message": message,
            },
            "device": {
                "id": device.get("device_id"),
                "name": device.get("device_name"),
                "type": device.get("device_type"),
                "hostname": device.get("hostname"),
            },
        }

        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            success = response.status_code < 400

            notification_log.log_notification(
                alert_id=alert_id,
                notification_method="webhook",
                recipient=webhook_url,
                status="sent" if success else "failed",
                error_message=None if success else f"HTTP {response.status_code}",
            )

            if success:
                self.logger.info(f"Webhook sent to {webhook_url}")
            else:
                self.logger.warning(f"Webhook returned {response.status_code}")

            return success

        except requests.RequestException as e:
            notification_log.log_notification(
                alert_id=alert_id,
                notification_method="webhook",
                recipient=webhook_url,
                status="failed",
                error_message=str(e),
            )

            self.logger.error(f"Webhook failed to {webhook_url}: {e}")
            return False

    # Settings management

    def _get_email_settings_for_recipient(self, email: str) -> Optional[Dict[str, Any]]:
        """Get email settings for a recipient."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM notification_settings
            WHERE email_address = ?
        """,
            (email,),
        )

        row = cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            result = dict(zip(columns, row))
        else:
            result = None

        conn.close()
        return result

    def get_notification_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get notification settings for a user."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM notification_settings
            WHERE user_id = ?
        """,
            (user_id,),
        )

        row = cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            result = dict(zip(columns, row))
        else:
            result = None

        conn.close()
        return result

    def save_email_settings(
        self,
        user_id: int,
        email_address: str,
        smtp_server: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        use_tls: bool = True,
    ) -> bool:
        """
        Save email notification settings.

        Args:
            user_id: User ID
            email_address: Notification email address
            smtp_server: SMTP server hostname
            smtp_port: SMTP port
            smtp_username: SMTP login username
            smtp_password: SMTP password (will be encrypted)
            use_tls: Whether to use TLS

        Returns:
            True if saved
        """
        encrypted_password = self._encrypt_password(smtp_password)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO notification_settings
            (user_id, email_enabled, email_address, smtp_server, smtp_port,
             smtp_username, smtp_password_encrypted, smtp_use_tls)
            VALUES (?, 1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                email_enabled = 1,
                email_address = excluded.email_address,
                smtp_server = excluded.smtp_server,
                smtp_port = excluded.smtp_port,
                smtp_username = excluded.smtp_username,
                smtp_password_encrypted = excluded.smtp_password_encrypted,
                smtp_use_tls = excluded.smtp_use_tls,
                updated_at = CURRENT_TIMESTAMP
        """,
            (
                user_id,
                email_address,
                smtp_server,
                smtp_port,
                smtp_username,
                encrypted_password,
                1 if use_tls else 0,
            ),
        )

        conn.commit()
        conn.close()
        return True

    def save_quiet_hours(
        self, user_id: int, enabled: bool, start_time: str, end_time: str
    ) -> bool:
        """
        Save quiet hours preferences.

        Args:
            user_id: User ID
            enabled: Whether quiet hours are enabled
            start_time: Start time (HH:MM)
            end_time: End time (HH:MM)

        Returns:
            True if saved
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE notification_settings
            SET quiet_hours_enabled = ?,
                quiet_hours_start = ?,
                quiet_hours_end = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """,
            (1 if enabled else 0, start_time, end_time, user_id),
        )

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        return success

    def disable_email(self, user_id: int) -> bool:
        """Disable email notifications for a user."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE notification_settings
            SET email_enabled = 0, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """,
            (user_id,),
        )

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        return success

    def test_email_settings(
        self, settings: Dict[str, Any], test_recipient: str
    ) -> Dict[str, Any]:
        """
        Test email settings by sending a test message.

        Args:
            settings: Email settings to test
            test_recipient: Email address to send test to

        Returns:
            Dict with success status and message
        """
        try:
            self._send_smtp_email(
                settings=settings,
                recipient=test_recipient,
                subject="[Myco-Monitor] Test Email",
                body="This is a test email from Myco-Monitor.\n\nIf you receive this, your email settings are configured correctly.",
            )
            return {"success": True, "message": "Test email sent successfully"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # Utility methods

    def _is_quiet_hours(self, settings: Dict[str, Any]) -> bool:
        """Check if current time is within quiet hours."""
        if not settings.get("quiet_hours_enabled"):
            return False

        start = settings.get("quiet_hours_start")
        end = settings.get("quiet_hours_end")

        if not start or not end:
            return False

        now = datetime.now().time()
        start_time = datetime.strptime(start, "%H:%M").time()
        end_time = datetime.strptime(end, "%H:%M").time()

        # Handle overnight quiet hours (e.g., 22:00 - 07:00)
        if start_time > end_time:
            return now >= start_time or now <= end_time
        else:
            return start_time <= now <= end_time

    def _encrypt_password(self, password: str) -> str:
        """Encrypt a password for storage."""
        if self._encryption_key:
            from cryptography.fernet import Fernet

            cipher = Fernet(self._encryption_key)
            return cipher.encrypt(password.encode()).decode()
        # Fallback: Base64 encode (not secure, just obfuscation)
        import base64

        return base64.b64encode(password.encode()).decode()

    def _decrypt_password(self, encrypted: str) -> str:
        """Decrypt a stored password."""
        if self._encryption_key:
            from cryptography.fernet import Fernet

            cipher = Fernet(self._encryption_key)
            return cipher.decrypt(encrypted.encode()).decode()
        # Fallback: Base64 decode
        import base64

        return base64.b64decode(encrypted.encode()).decode()
