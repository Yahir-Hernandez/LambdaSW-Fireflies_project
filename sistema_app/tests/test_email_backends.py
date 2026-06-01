"""Pruebas del backend HTTP de SendGrid."""

import base64
import json
from email.mime.image import MIMEImage

import pytest
from django.core.mail import EmailMultiAlternatives

from sistema_app.email_backends import SendGridEmailBackend


pytestmark = pytest.mark.unit


class _Response:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_sendgrid_backend_builds_inline_image_payload(settings, monkeypatch):
    """Construye un correo con imagen inline (CID) y verifica que el payload JSON enviado a SendGrid contiene los campos from, to, HTML y el adjunto en base64 con disposition inline."""
    settings.SENDGRID_API_KEY = "SG.test"
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr("sistema_app.email_backends.urlopen", fake_urlopen)

    msg = EmailMultiAlternatives(
        subject="Prueba",
        body="Texto plano",
        from_email="Festival <noreply@example.com>",
        to=["Ana <ana@example.com>"],
    )
    msg.attach_alternative('<p><img src="cid:logo" alt=""></p>', "text/html")
    image = MIMEImage(b"png-bytes", _subtype="png")
    image.add_header("Content-ID", "<logo>")
    image.add_header("Content-Disposition", "inline")
    msg.attach(image)

    sent = SendGridEmailBackend().send_messages([msg])

    assert sent == 1
    assert captured["authorization"] == "Bearer SG.test"
    payload = captured["payload"]
    assert payload["from"] == {"email": "noreply@example.com", "name": "Festival"}
    assert payload["personalizations"][0]["to"] == [
        {"email": "ana@example.com", "name": "Ana"}
    ]
    assert payload["content"][1] == {
        "type": "text/html",
        "value": '<p><img src="cid:logo" alt=""></p>',
    }
    assert payload["attachments"][0] == {
        "content": base64.b64encode(b"png-bytes").decode("ascii"),
        "filename": "logo.png",
        "type": "image/png",
        "disposition": "inline",
        "content_id": "logo",
    }
