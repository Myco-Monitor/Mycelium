"""
Email Notification Service for Mycelium

Sends email alerts for critical events using Python's built-in smtplib.
Triggered by the alert service for events like device offline, CO2 spike,
or relay failure.

SMTP configuration is stored in user_settings.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any


class EmailService:
    """Sends email notifications for critical alerts."""

    def __init__(self):
        self.logger = logging.getLogger("api.EmailService")
        # Reason for the most recent send failure (server response or a hint),
        # so callers like the Settings "Send Test Email" button can surface it.
        self.last_error: Optional[str] = None

    def _get_smtp_config(self, user_id: int = 1) -> Optional[Dict[str, Any]]:
        """
        Load SMTP configuration from user settings.

        Expected user_settings fields:
        - smtp_server: SMTP server hostname
        - smtp_port: SMTP port (587 for TLS, 465 for SSL)
        - smtp_from: Sender email address
        - smtp_to: Recipient email address
        - smtp_password: SMTP password/app password
        - smtp_use_tls: Whether to use STARTTLS (default True)
        """
        try:
            from storage.tables.user_settings import get_user_setting

            settings = get_user_setting(user_id)
            if not settings:
                return None

            server = settings.get("smtp_server")
            if not server:
                return None

            return {
                "server": server,
                "port": int(settings.get("smtp_port", 587)),
                "from_addr": settings.get("smtp_from", ""),
                "to_addr": settings.get("smtp_to", ""),
                "password": settings.get("smtp_password", ""),
                "use_tls": bool(settings.get("smtp_use_tls", True)),
            }
        except Exception as e:
            self.logger.error(f"Failed to load SMTP config: {e}")
            return None

    def send_alert_email(
        self,
        subject: str,
        body: str,
        alert_type: str = "info",
        user_id: int = 1,
        device_name: str = "",
        to_override: Optional[str] = None,
    ) -> bool:
        """
        Send an alert email.

        Args:
            subject: Short description of the alert (used as error_description).
            body: Plain text email body with details.
            alert_type: Alert severity ('info', 'warning', 'critical').
            user_id: User ID to load SMTP config from.
            device_name: Device name for subject line. If empty, omitted.

        Subject format: [Mycelium] [device_name] subject
                    or: [Mycelium] subject (when no device_name)

        Returns:
            True if sent successfully, False otherwise.
        """
        self.last_error = None

        config = self._get_smtp_config(user_id)
        if not config:
            self.last_error = "SMTP is not configured in Settings."
            self.logger.debug("SMTP not configured, skipping email notification")
            return False

        # Recipient: an explicit override (e.g. an alert rule's target) wins;
        # otherwise fall back to the configured smtp_to address.
        recipient = (to_override or "").strip() or config["to_addr"]
        if not config["from_addr"] or not recipient:
            self.last_error = "Missing sender (From) or recipient address in Settings."
            self.logger.debug("SMTP from address or recipient not configured")
            return False

        # Build email
        msg = MIMEMultipart("alternative")
        if device_name:
            msg["Subject"] = f"[Mycelium] [{device_name}] {subject}"
        else:
            msg["Subject"] = f"[Mycelium] {subject}"
        msg["From"] = config["from_addr"]
        msg["To"] = recipient

        # Alert severity colors and labels
        severity_config = {
            "critical": {"color": "#d32f2f", "bg": "#fde8e8", "label": "CRITICAL"},
            "warning": {"color": "#f57c00", "bg": "#fff3e0", "label": "WARNING"},
            "info": {"color": "#1976d2", "bg": "#e3f2fd", "label": "INFO"},
        }
        sev = severity_config.get(alert_type, severity_config["info"])

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Plain text body
        device_line = f"Device: {device_name}\n" if device_name else ""
        plain_text = (
            f"Mycelium\n"
            f"A Myco-Monitor Farm Monitoring System\n"
            f"{'=' * 50}\n\n"
            f"Alert Type: {sev['label']}\n"
            f"{device_line}"
            f"Subject: {subject}\n"
            f"Time: {timestamp}\n\n"
            f"{body}\n\n"
            f"{'=' * 50}\n"
            f"This is an automated notification from Mycelium.\n"
            f"Manage alert settings at your Mycelium dashboard.\n"
        )
        text_part = MIMEText(plain_text, "plain")
        msg.attach(text_part)

        # Branded HTML email
        html_body = f"""
        <html>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; background-color: #f4f4f4;">
            <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
                <!-- Header -->
                <tr>
                    <td style="background-color: #333333; padding: 20px 30px; text-align: center;">
                        <h1 style="margin: 0; color: #a500a5; font-size: 24px; letter-spacing: 1px;">Mycelium</h1>
                        <p style="margin: 6px 0 0 0; color: #cccccc; font-size: 12px;">A Myco-Monitor Farm Monitoring System</p>
                    </td>
                </tr>

                <!-- Alert Badge -->
                <tr>
                    <td style="padding: 20px 30px 10px 30px;">
                        <table cellpadding="0" cellspacing="0">
                            <tr>
                                <td style="background-color: {sev["color"]}; color: #ffffff; padding: 4px 12px; border-radius: 4px; font-size: 11px; font-weight: bold; letter-spacing: 1px;">
                                    {sev["label"]}
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <!-- Subject -->
                <tr>
                    <td style="padding: 10px 30px 5px 30px;">
                        {'<p style="margin: 0 0 4px 0; color: #a500a5; font-size: 13px; font-weight: bold;">' + device_name + "</p>" if device_name else ""}
                        <h2 style="margin: 0; color: #333333; font-size: 18px;">{subject}</h2>
                        <p style="margin: 4px 0 0 0; color: #999999; font-size: 12px;">{timestamp}</p>
                    </td>
                </tr>

                <!-- Body -->
                <tr>
                    <td style="padding: 15px 30px;">
                        <div style="background-color: {sev["bg"]}; border-left: 4px solid {sev["color"]}; padding: 15px 20px; border-radius: 0 6px 6px 0;">
                            <pre style="white-space: pre-wrap; font-family: 'SF Mono', Consolas, monospace; font-size: 13px; color: #333333; margin: 0; line-height: 1.5;">{body}</pre>
                        </div>
                    </td>
                </tr>

                <!-- Footer -->
                <tr>
                    <td style="background-color: #4d4d4d; padding: 15px 30px; text-align: center;">
                        <p style="margin: 0; color: #999999; font-size: 11px;">
                            This is an automated notification from Mycelium.
                        </p>
                        <p style="margin: 4px 0 0 0; color: #777777; font-size: 11px;">
                            Manage alert preferences in your Mycelium dashboard under Settings.
                        </p>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)

        # Present our sending domain in the EHLO/HELO greeting. Google Workspace's
        # SMTP relay identifies the sender by the HELO/EHLO domain (or a registered
        # IP / SMTP AUTH); the default smtplib greeting is the local machine name,
        # which the relay rejects with 5.7.1 "Invalid credentials for relay".
        helo_domain = config["from_addr"].split("@")[-1].strip() or None

        # Gmail/Workspace app passwords are displayed in 4-char groups; the spaces
        # are presentation only and must be stripped before AUTH.
        password = (config["password"] or "").replace(" ", "")

        # Send
        try:
            if config["use_tls"]:
                server = smtplib.SMTP(
                    config["server"],
                    config["port"],
                    local_hostname=helo_domain,
                    timeout=10,
                )
                server.ehlo(helo_domain)
                server.starttls()
                server.ehlo(helo_domain)  # re-greet after STARTTLS with our domain
            else:
                server = smtplib.SMTP_SSL(
                    config["server"],
                    config["port"],
                    local_hostname=helo_domain,
                    timeout=10,
                )
                server.ehlo(helo_domain)

            if password:
                server.login(config["from_addr"], password)

            server.sendmail(config["from_addr"], recipient, msg.as_string())
            server.quit()

            self.logger.info(f"Alert email sent: {subject}")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"Failed to send email: {e}")
            return False

    def send_device_offline_alert(self, device_name: str, device_type: str, ip: str):
        """Send alert when a device goes offline."""
        self.send_alert_email(
            subject=f"{device_type.capitalize()} Device Offline: {device_name}",
            body=f"Device '{device_name}' ({device_type}) at {ip} is not responding.\n\n"
            f"Check the device's power supply and network connection.",
            alert_type="critical",
        )

    def send_threshold_alert(
        self, device_name: str, metric: str, value: float, threshold: float
    ):
        """Send alert when a reading exceeds a threshold."""
        self.send_alert_email(
            subject=f"Threshold Exceeded: {metric} on {device_name}",
            body=f"Device '{device_name}' reported {metric} = {value}\n"
            f"Threshold: {threshold}\n\n"
            f"Check the grow room conditions.",
            alert_type="warning",
        )

    def send_relay_failure_alert(self, device_name: str, relay_num: int, error: str):
        """Send alert when a relay operation fails."""
        self.send_alert_email(
            subject=f"Relay Failure on {device_name}",
            body=f"Relay {relay_num} on '{device_name}' failed:\n{error}",
            alert_type="critical",
        )
