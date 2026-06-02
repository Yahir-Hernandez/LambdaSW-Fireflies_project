"""Valida las reglas de negocio sobre los datos de una posible reservación."""

from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from ..models import Lodging, Park, Reservation

# Constantes que definen la temporada del festival y los límites por reserva.
SEASON_START: date = date(2026, 6, 1)
SEASON_END: date = date(2026, 8, 31)
MIN_PEOPLE: int = 1
MAX_PEOPLE: int = 20
TUESDAY: int = 1
# Estancia máxima permitida por reservación (días), por disponibilidad de los parques.
MAX_DURATION_DAYS: int = 5


class ReservationValidator:
    """Aplica las reglas de negocio sobre una posible reservación.

    Cada regla puede ejecutarse por separado o todas en bloque mediante el
    método validate.
    """

    @classmethod
    def validate_date(cls, start_date: date, end_date: date) -> None:
        """
        Valida que las fechas caigan dentro de la temporada del festival.

        Args:
            start_date: Día en que comienza la estancia.
            end_date: Día en que termina la estancia.

        Raises:
            ValidationError: Si faltan fechas, si la fecha de término no es
                posterior a la de inicio, si la fecha de inicio queda fuera
                de la temporada, o si la fecha de término supera el cierre
                del festival.
        """
        if start_date is None or end_date is None:
            raise ValidationError("Fechas faltantes.")
        if end_date <= start_date:
            raise ValidationError(
                "La fecha de término debe ser posterior a la fecha de inicio."
            )
        if (
            start_date < SEASON_START
            or start_date > SEASON_END
        ):
            raise ValidationError(
                "Las reservaciones solo pueden realizarse entre Junio y Agosto de 2026."
            )
        if end_date > SEASON_END + timedelta(days=1):
            raise ValidationError(
                "La fecha de término no puede exceder el cierre del festival."
            )

    @classmethod
    def validate_max_duration(cls, start_date: date, end_date: date) -> None:
        """Rechaza estancias de más de MAX_DURATION_DAYS días por disponibilidad."""
        if (end_date - start_date).days > MAX_DURATION_DAYS:
            raise ValidationError(
                f"La estancia no puede exceder {MAX_DURATION_DAYS} días."
            )

    @classmethod
    def validate_tuesday(cls, start_date: date) -> None:
        """Rechaza una estancia que comienza un martes."""
        if start_date.weekday() == TUESDAY:
            raise ValidationError(
                "No es posible iniciar una estancia un día martes."
            )

    @classmethod
    def validate_people(cls, n_people: int) -> None:
        """Verifica que el número de personas esté dentro de los límites permitidos."""
        if n_people is None or n_people < MIN_PEOPLE:
            raise ValidationError(
                f"Debe registrarse al menos {MIN_PEOPLE} persona."
            )
        if n_people > MAX_PEOPLE:
            raise ValidationError(
                f"No se permiten más de {MAX_PEOPLE} personas por reservación."
            )

    @classmethod
    def validate_lodging(cls, lodging: Lodging, park: Park, n_people: int) -> None:
        """Comprueba que el hospedaje pertenece al parque y que tiene capacidad suficiente."""
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
        """
        Aplica en orden todas las validaciones.

        Raises:
            ValidationError: Si alguna de las validaciones individuales falla.
        """
        cls.validate_date(start_date, end_date)
        cls.validate_max_duration(start_date, end_date)
        cls.validate_tuesday(start_date)
        cls.validate_people(n_people)
        cls.validate_lodging(lodging, park, n_people)


REVIEW_RATING_MIN = 1
REVIEW_RATING_MAX = 5


class ReviewValidator:
    """Valida las reglas de negocio sobre una reseña de parque."""

    @classmethod
    def validate_rating(cls, rating) -> None:
        if not isinstance(rating, int) or rating < REVIEW_RATING_MIN or rating > REVIEW_RATING_MAX:
            raise ValidationError(
                f"La calificación debe estar entre {REVIEW_RATING_MIN} y {REVIEW_RATING_MAX} estrellas."
            )

    @classmethod
    def validate_reviewable(cls, reservation) -> None:
        if reservation.status != Reservation.Status.USED:
            raise ValidationError(
                "Solo puedes reseñar un parque después de usar tu reservación."
            )

    @classmethod
    def validate(cls, reservation, rating) -> None:
        cls.validate_reviewable(reservation)
        cls.validate_rating(rating)
