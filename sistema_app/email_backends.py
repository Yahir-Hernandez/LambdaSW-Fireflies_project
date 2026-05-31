from __future__ import annotations

import base64
import json
import logging
import mimetypes
from email.mime.base import MIMEBase
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)


def _address(value: str) -> dict[str, str]:
    name, email = parseaddr(value)
    payload = {"email": email or value.strip()}
    if name:
        payload["name"] = name
    return payload


def _header_value(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().strip("<>")


def _attachment_extension(mimetype: str) -> str:
    return mimetypes.guess_extension(mimetype or "") or ""


class SendGridEmailBackend(BaseEmailBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = getattr(settings, "SENDGRID_API_KEY", "")
        self.api_url = getattr(
            settings,
            "SENDGRID_API_URL",
            "https://api.sendgrid.com/v3/mail/send",
        )
        self.timeout = getattr(settings, "SENDGRID_TIMEOUT", 10)
        self.sandbox_mode = getattr(settings, "SENDGRID_SANDBOX_MODE", False)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            logger.error("SENDGRID_API_KEY no está configurada.")
            if self.fail_silently:
                return 0
            raise ValueError("SENDGRID_API_KEY no está configurada.")

        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _send(self, message) -> bool:
        payload = self._build_payload(message)
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            self.api_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                logger.info(
                    "SendGrid aceptó el correo. status=%s subject=%s recipient_count=%s",
                    response.status,
                    message.subject,
                    len(getattr(message, "to", []) or []),
                )
                return 200 <= response.status < 300
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if isinstance(exc, HTTPError):
                response_body = b""
                try:
                    response_body = exc.read() or b""
                except Exception:
                    response_body = b""

                logger.warning(
                    "SendGrid rechazó el envío. status=%s reason=%s subject=%s recipient_count=%s body=%s",
                    exc.code,
                    exc.reason,
                    message.subject,
                    len(getattr(message, "to", []) or []),
                    response_body.decode("utf-8", errors="replace")[:1000],
                )
            else:
                logger.warning(
                    "Fallo de red al enviar correo por SendGrid. subject=%s recipient_count=%s error=%s",
                    message.subject,
                    len(getattr(message, "to", []) or []),
                    exc,
                )

            if not self.fail_silently:
                raise
            return False

    def _build_payload(self, message) -> dict:
        personalizations = [{"to": [_address(addr) for addr in message.to]}]
        if message.cc:
            personalizations[0]["cc"] = [_address(addr) for addr in message.cc]
        if message.bcc:
            personalizations[0]["bcc"] = [_address(addr) for addr in message.bcc]

        payload = {
            "personalizations": personalizations,
            "from": _address(message.from_email),
            "subject": message.subject,
            "content": self._content(message),
        }

        attachments = self._attachments(message)
        if attachments:
            payload["attachments"] = attachments

        if message.reply_to:
            payload["reply_to"] = _address(message.reply_to[0])

        if self.sandbox_mode:
            payload["mail_settings"] = {"sandbox_mode": {"enable": True}}

        return payload

    def _content(self, message) -> list[dict[str, str]]:
        content = [{"type": "text/plain", "value": message.body or ""}]
        for alternative_body, mimetype in self._iter_alternatives(message):
            content.append({"type": mimetype, "value": alternative_body})
        return content

    @staticmethod
    def _iter_alternatives(message):
        for alternative in getattr(message, "alternatives", []):
            if hasattr(alternative, "content"):
                yield alternative.content, alternative.mimetype
            else:
                yield alternative[0], alternative[1]

    def _attachments(self, message) -> list[dict[str, str]]:
        attachments = []
        for index, attachment in enumerate(getattr(message, "attachments", []), start=1):
            payload = self._attachment_payload(attachment, index)
            if payload:
                attachments.append(payload)
        return attachments

    def _attachment_payload(self, attachment, index: int) -> dict[str, str] | None:
        if isinstance(attachment, MIMEBase):
            raw_content = attachment.get_payload(decode=True)
            if raw_content is None:
                payload = attachment.get_payload()
                raw_content = payload.encode("utf-8") if isinstance(payload, str) else payload

            mimetype = attachment.get_content_type()
            content_id = _header_value(attachment.get("Content-ID"))
            disposition_header = (attachment.get("Content-Disposition") or "").lower()
            disposition = "inline" if content_id or "inline" in disposition_header else "attachment"
            filename = attachment.get_filename()
            if not filename and content_id:
                filename = f"{content_id}{_attachment_extension(mimetype)}"
            if not filename:
                filename = f"attachment-{index}{_attachment_extension(mimetype)}"
        else:
            filename = getattr(attachment, "filename", None)
            raw_content = getattr(attachment, "content", None)
            mimetype = getattr(attachment, "mimetype", None)
            if isinstance(attachment, tuple):
                filename, raw_content, mimetype = attachment
            content_id = ""
            disposition = "attachment"
            filename = filename or f"attachment-{index}{_attachment_extension(mimetype)}"

        if raw_content is None:
            return None
        if isinstance(raw_content, str):
            raw_content = raw_content.encode("utf-8")

        encoded = base64.b64encode(raw_content).decode("ascii")
        payload = {
            "content": encoded,
            "filename": filename,
            "type": mimetype or "application/octet-stream",
            "disposition": disposition,
        }
        if content_id:
            payload["content_id"] = content_id
        return payload
