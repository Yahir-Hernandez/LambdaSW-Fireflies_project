"""Disponibilidad de hospedajes en un rango de fechas.

Reglas por tipo:

* **CABIN**: exclusiva. Cualquier reserva ACTIVE traslapada la bloquea.
* **CAMPING**: compartible. Admite varias reservas hasta sumar ``capacity``.
"""

from __future__ import annotations
from datetime import date
from typing import Iterable
from django.db.models import Sum

from ..models import Lodging, Park, Reservation


class AvailabilityService:
    """Disponibilidad de hospedajes según rango y tipo.

    Una reserva A se considera traslapada con el rango de fechas [s, e) si
    (A.start_date < e) ^ (A.end_date > s).
    """

    @staticmethod
    def _overlap(qs, start_date: date, end_date: date):
        """Filtra las reservas activas que se traslapan con el rango."""
        return qs.filter(
            status=Reservation.Status.ACTIVE,
            start_date__lt=end_date,
            end_date__gt=start_date,
        )

    @classmethod
    def people_booked(
        cls, lodging: Lodging, start_date: date, end_date: date
    ) -> int:
        """Suma de n personas de las reservas activas traslapadas.
        0 si no hay."""
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
        """Capacidad residual: 0/capacity para CABIN, resta para CAMPING."""
        if lodging.kind == Lodging.Kind.CABIN:
            booked = cls._overlap(
                Reservation.objects.filter(lodging=lodging),
                start_date,
                end_date,
            ).exists()
            return 0 if booked else lodging.capacity
        return max(lodging.capacity - cls.people_booked(lodging, start_date, end_date),0,)

    @classmethod
    def available_lodgings(
        cls,
        park: Park,
        kind: str,
        start_date: date,
        end_date: date,
        n_people: int = 1,
    ) -> Iterable[Lodging]:
        """Hospedajes del tipo dado que admiten al menos n personas.

        Cada Lodging retornado recibe un atributo dinámico
        available_capacity para evitar repetir la consulta.
        Se ordenan en orden decreciente por capacidad.
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
        """True si caben n personas en el rango."""
        return cls.remaining_capacity(lodging, start_date, end_date) >= n_people
