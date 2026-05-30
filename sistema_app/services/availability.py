"""Calcula la disponibilidad de hospedajes en un rango de fechas.
"""

from __future__ import annotations
from datetime import date
from typing import Iterable
from django.db.models import Sum

from ..models import Lodging, Park, Reservation


class AvailabilityService:
    """Servicio que determina cuántos lugares quedan libres en un hospedaje.

    Una reserva existente A se considera traslapada con un rango de
    fechas que va de s a e cuando A inicia antes de e y termina después
    de s.
    """

    @staticmethod
    def _overlap(qs, start_date: date, end_date: date):
        """Filtra del conjunto las reservas activas que se traslapan con el rango."""
        return qs.filter(
            status=Reservation.Status.ACTIVE,
            start_date__lt=end_date,
            end_date__gt=start_date,
        )

    @classmethod
    def people_booked(
        cls, lodging: Lodging, start_date: date, end_date: date
    ) -> int:
        """
        Devuelve la cantidad total de personas reservadas en el rango.

        Args:
            lodging: Hospedaje a consultar.
            start_date: Día de inicio del rango.
            end_date: Día de fin del rango.

        Returns:
            Suma de personas en reservas activas que cubren el rango. Si
            no hay reservas, devuelve cero.
        """
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
        """
        Devuelve cuántos lugares libres tiene el hospedaje en el rango.

        Para una cabaña, devuelve cero si existe cualquier reserva
        traslapada. Para una parcela de camping, devuelve la capacidad
        menos las personas ya reservadas, sin pasar nunca de cero.
        """
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
        """
        Devuelve los hospedajes del tipo indicado que admiten al menos n personas.

        Args:
            park: Parque del cual buscar hospedajes.
            kind: Tipo de hospedaje a filtrar, cabaña o camping.
            start_date: Día de inicio del rango deseado.
            end_date: Día de fin del rango deseado.
            n_people: Cantidad mínima de personas que el hospedaje debe
                poder recibir.

        Returns:
            Lista de hospedajes que satisfacen el filtro, ordenados por
            capacidad ascendente y luego por nombre. A cada elemento se
            le agrega el atributo available_capacity con los lugares
            libres calculados.
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
        """Indica si caben n personas en el hospedaje durante el rango."""
        return cls.remaining_capacity(lodging, start_date, end_date) >= n_people
