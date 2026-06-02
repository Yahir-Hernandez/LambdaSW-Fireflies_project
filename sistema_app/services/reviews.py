"""Lógica de negocio para crear y consultar reseñas de parques."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ..models import Reservation, Review
from .validation import ReviewValidator


class ReviewService:
    @classmethod
    @transaction.atomic
    def create_review(cls, user, reservation, rating, comment=""):
        locked = (
            Reservation.objects.select_for_update()
            .select_related("park")
            .get(pk=reservation.pk)
        )
        if locked.user_id != getattr(user, "id", None):
            raise ValidationError("No puedes reseñar una reservación que no es tuya.")
        ReviewValidator.validate(locked, rating)
        if Review.objects.filter(reservation=locked).exists():
            raise ValidationError("Ya enviaste una reseña para esta reservación.")
        try:
            return Review.objects.create(
                user=user,
                park=locked.park,
                reservation=locked,
                rating=rating,
                comment=(comment or "").strip(),
            )
        except IntegrityError:
            raise ValidationError("Ya enviaste una reseña para esta reservación.")
