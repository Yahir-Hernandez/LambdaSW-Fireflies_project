"""Envío de correos transaccionales (HTML + texto plano).

El cuerpo de los correos vive en sistema_app/templates/emails/
PARA EDITAR EL CUERPO DE LOS CORREOS EDITA LAS PLANTILLAS,
NO ESTE ARCHIVO!!!!!
Cualquier error de envío se loguea y se ignora.
"""

from __future__ import annotations

import logging
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from ..models import Reservation
from ..utils import generate_qr_png

logger = logging.getLogger(__name__)


# Logo embebido en todos los correos.
_LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo_b.png"


def _read_logo_bytes() -> bytes:
    """Lee el logo de luciérnaga del directorio static. Cached por proceso."""
    if not hasattr(_read_logo_bytes, "_cache"):
        try:
            _read_logo_bytes._cache = _LOGO_PATH.read_bytes()
        except OSError:
            logger.warning("No se pudo leer el logo en %s.", _LOGO_PATH)
            _read_logo_bytes._cache = b""
    return _read_logo_bytes._cache


class NotificationService:
    """Envío de correos."""

    DEFAULT_FROM = getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@luciernagas2026.mx"
    )

    # Helpers privados

    @classmethod
    def _build_reservation_context(cls, reservation: Reservation) -> dict:
        """Contexto que las plantillas de reserva esperan."""
        lodging = reservation.lodging
        return {
            "user_name": (
                reservation.user.username
            ),
            "park_name": reservation.park.name,
            "kind_display": lodging.get_kind_display(),
            "lodging_name": lodging.name,
            "start_date": reservation.start_date.isoformat(),
            "end_date": reservation.end_date.isoformat(),
            "people": reservation.people,
            "reservation_id": reservation.pk,
        }

    @staticmethod
    def _attach_inline_image(msg: EmailMultiAlternatives, cid: str, png_bytes: bytes) -> None:
        """Adjunta una imagen inline con Content-ID dado."""
        if not png_bytes:
            return
        image = MIMEImage(png_bytes, _subtype="png")
        image.add_header("Content-ID", f"<{cid}>")
        image.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
        msg.attach(image)

    @classmethod
    def _deliver(
        cls,
        subject: str,
        text_body: str,
        html_body: str | None,
        recipient: str,
        inline_images: list[tuple[str, bytes]] | None = None,
    ) -> bool:
        """Construye y envía un Email multi alterantivas. Retorna false ante errores."""
        if not recipient:
            return False
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=cls.DEFAULT_FROM,
            to=[recipient],
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")
            msg.mixed_subtype = "related"  # necesario para que los CID resuelvan
        for cid, png in (inline_images or []):
            cls._attach_inline_image(msg, cid, png)
        try:
            msg.send(fail_silently=False)
            return True
        except Exception:
            logger.exception("Fallo enviando correo a %s.", recipient)
            return False

    @classmethod
    def _send_to(cls, subject: str, body: str, recipient: str) -> bool:
        """Backward-compat: envía un texto plano a un destinatario libre."""
        return cls._deliver(
            subject=subject,
            text_body=body,
            html_body=None,
            recipient=recipient,
        )

    
    @classmethod
    def send_confirmation_email(cls, reservation: Reservation) -> bool:
        """Confirma una reservación e incluye QR de check-in."""
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            logger.info(
                "Reserva #%s sin email de destino; correo omitido.", reservation.pk
            )
            return False

        ctx = cls._build_reservation_context(reservation)

        # URL absoluta del endpoint de check-in 
        checkin_path = reverse(
            "admin:sistema_app_reservation_checkin_data",
            args=[reservation.checkin_token],
        )
        checkin_url = f"{settings.SITE_URL.rstrip('/')}{checkin_path}"
        qr_png = generate_qr_png(checkin_url)

        ctx_html = {**ctx, "qr_cid": "qr", "logo_cid": "logo"}
        text_body = render_to_string("emails/reservation_confirmation.txt", ctx)
        html_body = render_to_string("emails/reservation_confirmation.html", ctx_html)

        return cls._deliver(
            subject=f"Confirmación de reserva #{reservation.pk} — Festival de las Luciérnagas",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient,
            inline_images=[
                ("qr", qr_png),
                ("logo", _read_logo_bytes()),
            ],
        )

    @classmethod
    def send_cancellation_email(cls, reservation: Reservation) -> bool:
        """Notifica la cancelación de una reservación."""
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            logger.info(
                "Reserva #%s sin email de destino; correo omitido.", reservation.pk
            )
            return False

        ctx = cls._build_reservation_context(reservation)
        ctx_html = {**ctx, "logo_cid": "logo"}
        text_body = render_to_string("emails/reservation_cancellation.txt", ctx)
        html_body = render_to_string("emails/reservation_cancellation.html", ctx_html)

        return cls._deliver(
            subject=f"Cancelación de reserva #{reservation.pk}",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient,
            inline_images=[("logo", _read_logo_bytes())],
        )

    @classmethod
    def send_verification_email(
        cls, recipient_email: str, code: str, recipient_name: str = ""
    ) -> bool:
        """Envía el código de 5 dígitos durante el alta de cuenta."""
        ctx = {"code": code, "name": recipient_name}
        ctx_html = {**ctx, "logo_cid": "logo"}
        text_body = render_to_string("emails/verification_code.txt", ctx)
        html_body = render_to_string("emails/verification_code.html", ctx_html)

        return cls._deliver(
            subject="Tu código de verificación - Festival de las Luciérnagas",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient_email or "",
            inline_images=[("logo", _read_logo_bytes())],
        )
