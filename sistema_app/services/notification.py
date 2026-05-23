"""Envío de correos transaccionales.

El cuerpo de los correos vive en sistema_app/templates/emails/ 
PARA EDITAR EL CUERPO DE LOS CORREOS EDITA LAS PLANITLLAS, 
NO ESTE ARCHIVO!!!!!
Cualquier error de envío se loguea y se ignora.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from ..models import Reservation

logger = logging.getLogger(__name__)


class NotificationService:
    """Envío de correos."""

    DEFAULT_FROM = getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@luciernagas2026.mx"
    )

    @classmethod
    def _build_reservation_context(cls, reservation: Reservation) -> dict:
        """Contexto que las plantillas de reserva esperan."""
        lodging = reservation.lodging
        return {
            "park_name": reservation.park.name,
            "kind_display": lodging.get_kind_display(),
            "lodging_name": lodging.name,
            "start_date": reservation.start_date.isoformat(),
            "end_date": reservation.end_date.isoformat(),
            "people": reservation.people,
            "reservation_id": reservation.pk,
        }

    @classmethod
    def _send(cls, subject: str, body: str, reservation: Reservation) -> bool:
        """Envía al reservation.user.email."""
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            logger.info(
                "Reserva #%s sin email de destino, correo omitido.", reservation.pk
            )
            return False
        try:
            send_mail(
                subject, body, cls.DEFAULT_FROM, [recipient], fail_silently=False
            )
            return True
        except Exception:
            logger.exception(
                "Fallo enviando correo de la reserva #%s; la reserva sigue vigente.",
                reservation.pk,
            )
            return False

    @classmethod
    def _send_to(cls, subject: str, body: str, recipient: str) -> bool:
        """Envía a un destinatario libre (no atado a una reserva)."""
        if not recipient:
            return False
        try:
            send_mail(
                subject, body, cls.DEFAULT_FROM, [recipient], fail_silently=False
            )
            return True
        except Exception:
            logger.exception("Fallo enviando correo a %s.", recipient)
            return False

    @classmethod
    def send_confirmation_email(cls, reservation: Reservation) -> bool:
        """Confirma una reservación recién creada."""
        body = render_to_string(
            "emails/reservation_confirmation.txt",
            cls._build_reservation_context(reservation),
        )
        return cls._send(
            subject=f"Confirmación de reserva #{reservation.pk} — Festival de las Luciérnagas",
            body=body,
            reservation=reservation,
        )

    @classmethod
    def send_cancellation_email(cls, reservation: Reservation) -> bool:
        """Notifica la cancelación de una reservación."""
        body = render_to_string(
            "emails/reservation_cancellation.txt",
            cls._build_reservation_context(reservation),
        )
        return cls._send(
            subject=f"Cancelación de reserva #{reservation.pk}",
            body=body,
            reservation=reservation,
        )

    @classmethod
    def send_verification_email(
        cls, recipient_email: str, code: str, recipient_name: str = ""
    ) -> bool:
        """Envía el código de 5 dígitos durante el alta de cuenta."""
        body = render_to_string(
            "emails/verification_code.txt",
            {"code": code, "name": recipient_name},
        )
        return cls._send_to(
            subject="Código de verificación - Festival de las Luciérnagas",
            body=body,
            recipient=recipient_email or "",
        )
