"""Capa de servicios para la lógica de reservaciones.

Servicios disponibles:
    * ReservationValidator: Reglas de negocio sobre los datos de entrada.
    * AvailabilityService:  Disponibilidad de hospedajes.
    * NotificationService:  Envío de correos.
    * ReservationService:   Orquesta los servicios anteriores.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Iterable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum

from .models import Lodging, Park, Reservation

logger = logging.getLogger(__name__)


class ReservationValidator:
    """Reglas RNB-01..04 sobre los datos de una posible reservación."""

    SEASON_START = date(2026, 6, 1)
    SEASON_END = date(2026, 8, 31)
    MIN_PEOPLE = 1
    MAX_PEOPLE = 20
    TUESDAY = 1

    @classmethod
    def validate_date(cls, start_date: date, end_date: date) -> None:
        if start_date is None or end_date is None:
            raise ValidationError("Fechas faltantes.")
        if end_date <= start_date:
            raise ValidationError(
                "La fecha de término debe ser posterior a la fecha de inicio."
            )
        if start_date < cls.SEASON_START or start_date > cls.SEASON_END:
            raise ValidationError(
                "Las reservaciones solo pueden realizarse entre Junio y Agosto de 2026."
            )
        if end_date > cls.SEASON_END + timedelta(days=1):
            raise ValidationError(
                "La fecha de término no puede exceder el cierre del festival."
            )

    @classmethod
    def validate_tuesday(cls, start_date: date) -> None:
        if start_date.weekday() == cls.TUESDAY:
            raise ValidationError(
                "No es posible iniciar una estancia un día martes."
            )

    @classmethod
    def validate_people(cls, n_people: int) -> None:
        if n_people is None or n_people < cls.MIN_PEOPLE:
            raise ValidationError(
                f"Debe registrarse al menos {cls.MIN_PEOPLE} persona."
            )
        if n_people > cls.MAX_PEOPLE:
            raise ValidationError(
                f"No se permiten más de {cls.MAX_PEOPLE} personas por reservación."
            )

    @classmethod
    def validate_lodging(cls, lodging: Lodging, park: Park, n_people: int) -> None:
        if lodging.park_id != park.id:
            raise ValidationError("La opción seleccionada no pertenece a este parque.")
        if n_people > lodging.capacity:
            raise ValidationError(
                f"Esta opción admite máximo {lodging.capacity} personas."
            )

    @classmethod
    def validate(
        cls,
        park: Park,
        lodging: Lodging,
        start_date: date,
        end_date: date,
        n_people: int,
    ) -> None:
        cls.validate_date(start_date, end_date)
        cls.validate_tuesday(start_date)
        cls.validate_people(n_people)
        cls.validate_lodging(lodging, park, n_people)


class AvailabilityService:
    """Disponibilidad de hospedajes.

    Reglas distintas según el kind del lodging:
      * CABIN:   exclusivo. Cualquier reserva activa traslapada lo bloquea.
      * CAMPING: compartible. Una parcela admite varias reservas hasta
                 ``capacity`` personas en total dentro del rango. La capacidad
                 disponible para un nuevo huésped es ``capacity - SUM(people)``
                 de las reservas activas traslapadas.
    """

    @staticmethod
    def _overlap(qs, start_date: date, end_date: date):
        return qs.filter(
            status=Reservation.Status.ACTIVE,
            start_date__lt=end_date,
            end_date__gt=start_date,
        )

    @classmethod
    def people_booked(
        cls, lodging: Lodging, start_date: date, end_date: date
    ) -> int:
        """Suma de personas ya reservadas para ese lodging en el rango."""
        return (
            cls._overlap(
                Reservation.objects.filter(lodging=lodging),
                start_date,
                end_date,
            ).aggregate(total=Sum("people"))["total"]
            or 0
        )

    @classmethod
    def remaining_capacity(
        cls, lodging: Lodging, start_date: date, end_date: date
    ) -> int:
        """Cuántas personas más caben en este lodging para ese rango.

        Para cabaña: capacity si está libre, 0 si tiene cualquier reserva
        traslapada (es exclusiva).
        Para camping: capacity - personas ya reservadas (acotado a 0).
        """
        if lodging.kind == Lodging.Kind.CABIN:
            booked = cls._overlap(
                Reservation.objects.filter(lodging=lodging),
                start_date,
                end_date,
            ).exists()
            return 0 if booked else lodging.capacity
        return max(lodging.capacity - cls.people_booked(lodging, start_date, end_date), 0)

    @classmethod
    def available_lodgings(
        cls,
        park: Park,
        kind: str,
        start_date: date,
        end_date: date,
        n_people: int = 1,
    ) -> Iterable[Lodging]:
        """Lodgings del kind dado que admiten al menos ``n_people`` en el rango.

        Devuelve cada Lodging con un atributo extra ``available_capacity``
        calculado en Python para evitar repetir la consulta en los callers.
        """
        candidates = park.lodgings.filter(kind=kind).order_by("capacity", "name")
        result = []
        for lo in candidates:
            remaining = cls.remaining_capacity(lo, start_date, end_date)
            if remaining >= n_people:
                lo.available_capacity = remaining
                result.append(lo)
        return result

    @classmethod
    def is_lodging_available(
        cls,
        lodging: Lodging,
        start_date: date,
        end_date: date,
        n_people: int = 1,
    ) -> bool:
        return cls.remaining_capacity(lodging, start_date, end_date) >= n_people


class NotificationService:
    """Envío de correos. Cualquier error se ignora y se registra en logs."""

    DEFAULT_FROM = getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@luciernagas2026.mx"
    )

    @classmethod
    def _send(cls, subject: str, body: str, reservation: Reservation) -> bool:
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            logger.info(
                "Reserva #%s sin email de destino; correo omitido.", reservation.pk
            )
            return False
        try:
            send_mail(
                subject,
                body,
                cls.DEFAULT_FROM,
                [recipient],
                fail_silently=False,
            )
            return True
        except Exception:
            logger.exception(
                "Fallo enviando correo de la reserva #%s; la reserva sigue vigente.",
                reservation.pk,
            )
            return False

    @classmethod
    def _format(cls, reservation: Reservation) -> str:
        lodging = reservation.lodging
        return (
            f"Parque: {reservation.park.name}\n"
            f"Tipo: {lodging.get_kind_display()}\n"
            f"Hospedaje: {lodging.name}\n"
            f"Fecha de inicio: {reservation.start_date.isoformat()}\n"
            f"Fecha de término: {reservation.end_date.isoformat()}\n"
            f"Personas: {reservation.people}\n"
            f"Código de reserva: #{reservation.pk}"
        )

    @classmethod
    def send_confirmation_email(cls, reservation: Reservation) -> bool:
        return cls._send(
            subject=f"Confirmación de reserva #{reservation.pk} — Festival de las Luciérnagas",
            body=(
                "¡Tu reservación fue confirmada!\n\n"
                + cls._format(reservation)
            ),
            reservation=reservation,
        )

    @classmethod
    def send_cancellation_email(cls, reservation: Reservation) -> bool:
        return cls._send(
            subject=f"Cancelación de reserva #{reservation.pk}",
            body=(
                "Tu reservación fue cancelada.\n\n"
                + cls._format(reservation)
            ),
            reservation=reservation,
        )


class ReservationService:
    """Orquesta validación, disponibilidad y notificaciones."""

    @classmethod
    @transaction.atomic
    def create_reservation(
        cls,
        user,
        lodging: Lodging,
        start_date: date,
        end_date: date,
        n_people: int,
    ) -> Reservation:
        # Lock por hospedaje: evita doble-booking concurrente del mismo recurso
        # sin bloquear todo el parque.
        locked_lodging = (
            Lodging.objects.select_for_update().select_related("park").get(pk=lodging.pk)
        )
        park = locked_lodging.park
        if park.is_deleted:
            raise ValidationError("Este parque ya no está disponible.")

        ReservationValidator.validate(
            park, locked_lodging, start_date, end_date, n_people
        )

        remaining = AvailabilityService.remaining_capacity(
            locked_lodging, start_date, end_date
        )
        if remaining < n_people:
            if locked_lodging.kind == Lodging.Kind.CABIN:
                raise ValidationError(
                    "Esta cabaña ya está reservada para las fechas seleccionadas."
                )
            if remaining == 0:
                raise ValidationError(
                    "Esta parcela ya está completamente reservada para esas fechas."
                )
            raise ValidationError(
                f"En esta parcela solo quedan {remaining} lugar(es) disponible(s) para esas fechas."
            )

        reservation = Reservation.objects.create(
            user=user,
            park=park,
            lodging=locked_lodging,
            start_date=start_date,
            end_date=end_date,
            people=n_people,
        )

        transaction.on_commit(
            lambda: NotificationService.send_confirmation_email(reservation)
        )
        return reservation

    @classmethod
    def cancel_reservation(cls, user, reservation: Reservation) -> Reservation:
        if reservation.user_id != getattr(user, "id", None) and not user.is_staff:
            raise ValidationError("No tienes permisos para cancelar esta reservación.")
        if not reservation.is_cancellable():
            raise ValidationError(
                "Solo es posible cancelar una reserva activa antes de su fecha de inicio."
            )

        with transaction.atomic():
            reservation.status = Reservation.Status.CANCELLED
            reservation.save(update_fields=["status"])

        transaction.on_commit(
            lambda: NotificationService.send_cancellation_email(reservation)
        )
        return reservation

    @classmethod
    def get_user_reservations(cls, user, only_active: bool = False):
        qs = Reservation.objects.filter(user=user).select_related("park", "lodging")
        if only_active:
            qs = qs.filter(status=Reservation.Status.ACTIVE)
        return qs
