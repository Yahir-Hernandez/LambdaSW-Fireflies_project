"""Valida la capacidad de un hospedaje cuando el administrador lo edita."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import Lodging, Reservation


class LodgingCapacityValidator:
    """Protege las reservas activas cuando un administrador reduce la capacidad.

    Solo se consideran reservas activas con fecha futura. Las reservas
    pasadas, usadas y canceladas se ignoran porque ya no pueden verse
    afectadas por el cambio de capacidad.
    """

    @classmethod
    def validate_capacity_reduction(cls, lodging: Lodging, new_capacity: int) -> None:
        """
        Bloquea reducciones de capacidad incompatibles con reservas existentes.

        Args:
            lodging: Hospedaje que se está editando. Debe estar guardado.
            new_capacity: Nuevo valor de capacidad que el administrador
                intenta aplicar.

        Raises:
            ValidationError: Si al bajar a la nueva capacidad alguna
                reserva activa futura quedara con más personas de las
                permitidas (en cabañas) o si el pico de personas
                concurrentes superara la nueva capacidad (en parcelas).
        """
        if lodging.pk is None:
            return
        try:
            previous_capacity = (
                Lodging.objects.only("capacity").get(pk=lodging.pk).capacity
            )
        except Lodging.DoesNotExist:
            return
        if new_capacity >= previous_capacity:
            return

        today = timezone.localdate()
        future_active = Reservation.objects.filter(
            lodging=lodging,
            status=Reservation.Status.ACTIVE,
            end_date__gt=today,
        )
        if lodging.kind == Lodging.Kind.CABIN:
            cls._validate_cabin(future_active, new_capacity)
        else:
            cls._validate_camping(future_active, new_capacity)

    @staticmethod
    def _validate_cabin(qs, new_capacity: int) -> None:
        """Falla si alguna reserva de la cabaña tiene más personas que la nueva capacidad."""
        offending = (
            qs.filter(people__gt=new_capacity).order_by("start_date").first()
        )
        if offending:
            raise ValidationError({
                "capacity": (
                    f"No puedes reducir la capacidad de la cabaña a {new_capacity}: "
                    f"existe una reserva activa para {offending.people} personas "
                    f"(del {offending.start_date:%d/%m/%Y} al "
                    f"{offending.end_date:%d/%m/%Y})."
                )
            })

    @staticmethod
    def _validate_camping(qs, new_capacity: int) -> None:
        """Falla si el pico de personas concurrentes en la parcela supera la nueva capacidad."""
        # Algoritmo de barrido. La fecha de término es exclusiva, así que
        # los eventos de salida del día se procesan antes que los de
        # entrada para no contar doble.
        events: list[tuple] = []
        for r in qs.values("start_date", "end_date", "people"):
            events.append((r["start_date"], 1, r["people"]))
            events.append((r["end_date"], 0, -r["people"]))
        events.sort(key=lambda e: (e[0], e[1]))

        current = peak = 0
        peak_date = None
        for fecha, _, delta in events:
            current += delta
            if current > peak:
                peak = current
                peak_date = fecha
        if peak > new_capacity:
            raise ValidationError({
                "capacity": (
                    f"No puedes reducir la capacidad del camping a {new_capacity}: "
                    f"a partir del {peak_date:%d/%m/%Y} hay {peak} personas "
                    f"reservadas concurrentemente."
                )
            })
