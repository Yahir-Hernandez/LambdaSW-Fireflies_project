"""
Pruebas unitarias de la capa de servicios (services.py)

Lo que se prueba:
    - generate_verification_code(): formato y aleatoriedad
    - mask_email(): censura correcta de correos
    - ReservationValidator: cada regla de negocio RNB-01..04
    - AvailabilityService: disponibilidad de CABIN y CAMPING
    - NotificationService: envío de correos 
    - ReservationService: crear y cancelar reservas
"""

import pytest

pytestmark = pytest.mark.unit

from datetime import date, timedelta
from unittest.mock import patch
from django.core import mail
from django.core.exceptions import ValidationError

from sistema_app.models import Lodging, Reservation
from sistema_app.services import (
    AvailabilityService,
    NotificationService,
    ReservationService,
    ReservationValidator,
    generate_verification_code,
    mask_email,
)


# ===========================================================================
# generate_verification_code
# ===========================================================================

class TestGenerateVerificationCode:
    def test_returns_five_digits(self):
        code = generate_verification_code()
        assert len(code) == 5
        assert code.isdigit()

    def test_zero_padded(self):
        with patch("sistema_app.services.secrets.randbelow", return_value=0):
            code = generate_verification_code()
        assert code == "00000"

    def test_codes_are_not_always_equal(self):
        codes = {generate_verification_code() for _ in range(20)}
        assert len(codes) > 1


# ===========================================================================
# mask_email
# ===========================================================================

class TestMaskEmail:
    def test_long_local_part(self):
        assert mask_email("saosapis.666@gmail.com") == "sa*********6@gmail.com"

    def test_exactly_4_chars_local(self):
        assert mask_email("abcd@x.com") == "ab*d@x.com"

    def test_short_local_part_unchanged(self):
        assert mask_email("abc@x.com") == "abc@x.com"

    def test_empty_string_returns_empty(self):
        assert mask_email("") == ""

    def test_no_at_sign_returns_unchanged(self):
        assert mask_email("sinArroba") == "sinArroba"

    def test_domain_preserved(self):
        result = mask_email("usuario123@dominio.org")
        assert result.endswith("@dominio.org")


# ===========================================================================
# ReservationValidator
# ===========================================================================

class TestReservationValidatorDate:
    VALID_START = date(2026, 6, 2)   
    VALID_END = date(2026, 6, 5)

    def test_valid_dates_pass(self):
        ReservationValidator.validate_date(self.VALID_START, self.VALID_END)

    def test_end_before_start_raises(self):
        with pytest.raises(ValidationError, match="posterior"):
            ReservationValidator.validate_date(self.VALID_END, self.VALID_START)

    def test_same_day_start_end_raises(self):
        with pytest.raises(ValidationError):
            ReservationValidator.validate_date(self.VALID_START, self.VALID_START)

    def test_start_before_season_raises(self):
        with pytest.raises(ValidationError, match="Junio"):
            ReservationValidator.validate_date(date(2026, 5, 31), self.VALID_END)

    def test_start_after_season_raises(self):
        with pytest.raises(ValidationError, match="Junio"):
            ReservationValidator.validate_date(date(2026, 9, 1), date(2026, 9, 5))

    def test_end_exceeds_season_raises(self):
        with pytest.raises(ValidationError, match="cierre"):
            ReservationValidator.validate_date(date(2026, 8, 30), date(2026, 9, 2))

    def test_end_on_season_boundary_passes(self):
        ReservationValidator.validate_date(date(2026, 8, 30), date(2026, 9, 1))

    def test_none_start_raises(self):
        with pytest.raises(ValidationError):
            ReservationValidator.validate_date(None, self.VALID_END)

    def test_none_end_raises(self):
        with pytest.raises(ValidationError):
            ReservationValidator.validate_date(self.VALID_START, None)


class TestReservationValidatorTuesday:
    def test_monday_passes(self):
        monday = date(2026, 6, 1)
        assert monday.weekday() == 0
        ReservationValidator.validate_tuesday(monday)

    def test_tuesday_raises(self):
        tuesday = date(2026, 6, 2)
        assert tuesday.weekday() == 1
        with pytest.raises(ValidationError, match="martes"):
            ReservationValidator.validate_tuesday(tuesday)

    def test_wednesday_passes(self):
        wednesday = date(2026, 6, 3)
        assert wednesday.weekday() == 2
        ReservationValidator.validate_tuesday(wednesday)

    def test_all_weekdays_except_tuesday_pass(self):
        base = date(2026, 6, 1)
        for offset in [0, 2, 3, 4, 5, 6]:
            d = base + timedelta(days=offset)
            ReservationValidator.validate_tuesday(d)


class TestReservationValidatorPeople:
    def test_minimum_passes(self):
        ReservationValidator.validate_people(1)

    def test_maximum_passes(self):
        ReservationValidator.validate_people(20)

    def test_zero_raises(self):
        with pytest.raises(ValidationError):
            ReservationValidator.validate_people(0)

    def test_negative_raises(self):
        with pytest.raises(ValidationError):
            ReservationValidator.validate_people(-1)

    def test_twenty_one_raises(self):
        with pytest.raises(ValidationError, match="20"):
            ReservationValidator.validate_people(21)

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            ReservationValidator.validate_people(None)


@pytest.mark.django_db
class TestReservationValidatorLodging:
    def test_correct_park_and_capacity_passes(self, cabin, park):
        ReservationValidator.validate_lodging(cabin, park, 2)

    def test_wrong_park_raises(self, db, cabin, deleted_park):
        with pytest.raises(ValidationError, match="parque"):
            ReservationValidator.validate_lodging(cabin, deleted_park, 1)

    def test_exceeds_capacity_raises(self, cabin, park):
        with pytest.raises(ValidationError, match="máximo"):
            ReservationValidator.validate_lodging(cabin, park, cabin.capacity + 1)

    def test_exact_capacity_passes(self, cabin, park):
        ReservationValidator.validate_lodging(cabin, park, cabin.capacity)


# ===========================================================================
# AvailabilityService
# ===========================================================================

@pytest.mark.django_db
class TestAvailabilityServiceCabin:

    def test_free_cabin_has_full_capacity(self, cabin, season_start, season_end_date):
        remaining = AvailabilityService.remaining_capacity(cabin, season_start, season_end_date)
        assert remaining == cabin.capacity

    def test_booked_cabin_has_zero_capacity(self, active_reservation, cabin, season_start, season_end_date):
        remaining = AvailabilityService.remaining_capacity(cabin, season_start, season_end_date)
        assert remaining == 0

    def test_cancelled_reservation_does_not_block_cabin(self, cancelled_reservation, cabin, season_start, season_end_date):
        remaining = AvailabilityService.remaining_capacity(cabin, season_start, season_end_date)
        assert remaining == cabin.capacity

    def test_non_overlapping_reservation_does_not_block(self, db, user, park, cabin):
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 5),
            people=1, status=Reservation.Status.ACTIVE,
        )
        remaining = AvailabilityService.remaining_capacity(cabin, date(2026, 6, 1), date(2026, 6, 5))
        assert remaining == cabin.capacity

    def test_is_lodging_available_true_when_free(self, cabin, season_start, season_end_date):
        assert AvailabilityService.is_lodging_available(cabin, season_start, season_end_date, 1) is True

    def test_is_lodging_available_false_when_booked(self, active_reservation, cabin, season_start, season_end_date):
        assert AvailabilityService.is_lodging_available(cabin, season_start, season_end_date, 1) is False


@pytest.mark.django_db
class TestAvailabilityServiceCamping:

    def test_free_camping_has_full_capacity(self, camping_spot, season_start, season_end_date):
        remaining = AvailabilityService.remaining_capacity(camping_spot, season_start, season_end_date)
        assert remaining == camping_spot.capacity

    def test_partial_booking_reduces_capacity(self, db, user, park, camping_spot, season_start, season_end_date):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=3, status=Reservation.Status.ACTIVE,
        )
        remaining = AvailabilityService.remaining_capacity(camping_spot, season_start, season_end_date)
        assert remaining == camping_spot.capacity - 3

    def test_full_booking_returns_zero(self, db, user, park, camping_spot, season_start, season_end_date):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=camping_spot.capacity, status=Reservation.Status.ACTIVE,
        )
        remaining = AvailabilityService.remaining_capacity(camping_spot, season_start, season_end_date)
        assert remaining == 0

    def test_people_booked_sums_overlapping(self, db, user, other_user, park, camping_spot, season_start, season_end_date):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=3, status=Reservation.Status.ACTIVE,
        )
        Reservation.objects.create(
            user=other_user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=4, status=Reservation.Status.ACTIVE,
        )
        total = AvailabilityService.people_booked(camping_spot, season_start, season_end_date)
        assert total == 7

    def test_cancelled_reservation_not_counted(self, db, user, park, camping_spot, season_start, season_end_date):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=5, status=Reservation.Status.CANCELLED,
        )
        booked = AvailabilityService.people_booked(camping_spot, season_start, season_end_date)
        assert booked == 0

    def test_available_lodgings_returns_with_capacity_attr(self, park, camping_spot, season_start, season_end_date):
        results = list(AvailabilityService.available_lodgings(
            park, Lodging.Kind.CAMPING, season_start, season_end_date, n_people=1
        ))
        assert len(results) == 1
        assert hasattr(results[0], "available_capacity")
        assert results[0].available_capacity == camping_spot.capacity

    def test_available_lodgings_excludes_full(self, db, user, park, camping_spot, season_start, season_end_date):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=camping_spot.capacity, status=Reservation.Status.ACTIVE,
        )
        results = list(AvailabilityService.available_lodgings(
            park, Lodging.Kind.CAMPING, season_start, season_end_date, n_people=1
        ))
        assert len(results) == 0


# ===========================================================================
# NotificationService
# ===========================================================================

@pytest.mark.django_db
class TestNotificationService:
    def test_send_confirmation_email(self, active_reservation, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        result = NotificationService.send_confirmation_email(active_reservation)
        assert result is True
        assert len(mail.outbox) == 1
        assert "Confirmación" in mail.outbox[0].subject

    def test_send_cancellation_email(self, active_reservation, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        result = NotificationService.send_cancellation_email(active_reservation)
        assert result is True
        assert len(mail.outbox) == 1
        assert "Cancelación" in mail.outbox[0].subject

    def test_send_verification_email(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        result = NotificationService.send_verification_email("test@mail.com", "12345", "Usuario")
        assert result is True
        assert len(mail.outbox) == 1
        assert "12345" in mail.outbox[0].body

    def test_no_email_user_returns_false(self, db, user, park, cabin, season_start, season_end_date):
        user.email = ""
        user.save()
        res = Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=1,
        )
        result = NotificationService.send_confirmation_email(res)
        assert result is False

    def test_send_to_empty_recipient_returns_false(self):
        result = NotificationService._send_to("Asunto", "Cuerpo", "")
        assert result is False


# ===========================================================================
# ReservationService
# ===========================================================================

@pytest.mark.django_db
class TestReservationServiceCreate:
    def test_creates_reservation_successfully(self, user, cabin, park, settings, season_start, season_end_date):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        reservation = ReservationService.create_reservation(
            user=user,
            lodging=cabin,
            start_date=season_start,
            end_date=season_end_date,
            n_people=2,
        )
        assert reservation.pk is not None
        assert reservation.status == Reservation.Status.ACTIVE
        assert reservation.user == user

    def test_raises_on_tuesday_start(self, user, cabin, park):
        tuesday = date(2026, 6, 2)
        assert tuesday.weekday() == 1
        with pytest.raises(ValidationError, match="martes"):
            ReservationService.create_reservation(
                user=user, lodging=cabin,
                start_date=tuesday, end_date=date(2026, 6, 5),
                n_people=1,
            )

    def test_raises_when_cabin_already_booked(self, user, other_user, cabin, park, season_start, season_end_date):
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=1, status=Reservation.Status.ACTIVE,
        )
        with pytest.raises(ValidationError, match="cabaña"):
            ReservationService.create_reservation(
                user=other_user, lodging=cabin,
                start_date=season_start, end_date=season_end_date,
                n_people=1,
            )

    def test_raises_when_camping_full(self, db, user, other_user, park, camping_spot, season_start, season_end_date):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=camping_spot.capacity, status=Reservation.Status.ACTIVE,
        )
        with pytest.raises(ValidationError, match="completamente"):
            ReservationService.create_reservation(
                user=other_user, lodging=camping_spot,
                start_date=season_start, end_date=season_end_date,
                n_people=1,
            )

    def test_raises_when_camping_partially_full(self, db, user, other_user, park, camping_spot, season_start, season_end_date):
        remaining_spots = 2
        people_booked = camping_spot.capacity - remaining_spots
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=people_booked, status=Reservation.Status.ACTIVE,
        )
        with pytest.raises(ValidationError, match="quedan"):
            ReservationService.create_reservation(
                user=other_user, lodging=camping_spot,
                start_date=season_start, end_date=season_end_date,
                n_people=remaining_spots + 1,
            )

    def test_raises_when_park_deleted(self, user, deleted_park, settings):
        lodging = Lodging.objects.create(
            park=deleted_park, kind=Lodging.Kind.CAMPING,
            name="Parcela X", capacity=5,
        )
        with pytest.raises(ValidationError, match="disponible"):
            ReservationService.create_reservation(
                user=user, lodging=lodging,
                start_date=date(2026, 6, 2), end_date=date(2026, 6, 5),
                n_people=1,
            )

    def test_raises_on_out_of_season_date(self, user, cabin):
        with pytest.raises(ValidationError, match="Junio"):
            ReservationService.create_reservation(
                user=user, lodging=cabin,
                start_date=date(2026, 5, 1), end_date=date(2026, 5, 5),
                n_people=1,
            )

    def test_raises_on_too_many_people(self, user, camping_spot, season_start, season_end_date):
        with pytest.raises(ValidationError):
            ReservationService.create_reservation(
                user=user, lodging=camping_spot,
                start_date=season_start, end_date=season_end_date,
                n_people=21,
            )


@pytest.mark.django_db
class TestReservationServiceCancel:
    def test_owner_can_cancel(self, user, active_reservation, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        result = ReservationService.cancel_reservation(user, active_reservation)
        assert result.status == Reservation.Status.CANCELLED

    def test_staff_can_cancel_other_user_reservation(self, staff_user, active_reservation, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        result = ReservationService.cancel_reservation(staff_user, active_reservation)
        assert result.status == Reservation.Status.CANCELLED

    def test_other_user_cannot_cancel(self, other_user, active_reservation):
        with pytest.raises(ValidationError, match="permisos"):
            ReservationService.cancel_reservation(other_user, active_reservation)

    def test_cannot_cancel_already_cancelled(self, user, cancelled_reservation):
        with pytest.raises(ValidationError, match="activa"):
            ReservationService.cancel_reservation(user, cancelled_reservation)

    def test_get_user_reservations_returns_all(self, user, active_reservation, cancelled_reservation):
        qs = ReservationService.get_user_reservations(user)
        pks = list(qs.values_list("pk", flat=True))
        assert active_reservation.pk in pks

    def test_get_user_reservations_only_active(self, user, active_reservation, cancelled_reservation):
        qs = ReservationService.get_user_reservations(user, only_active=True)
        assert active_reservation in qs
        assert cancelled_reservation not in qs
