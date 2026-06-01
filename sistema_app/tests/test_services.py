"""
Pruebas unitarias de la capa de servicios (services.py)

Lo que se prueba:
    - generate_verification_code(): formato y aleatoriedad
    - mask_email(): censura correcta de correos
    - ReservationValidator: cada regla de negocio (fecha, martes, personas, lodging)
    - AvailabilityService: disponibilidad de CABIN y CAMPING
    - NotificationService: envío de correos
    - ReservationService: crear y cancelar reservas
    - LodgingCapacityValidator: bloqueo de reducciones de capacidad con reservas activas
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
    LodgingCapacityValidator,
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
        """Llama generate_verification_code() y verifica que retorna una cadena de exactamente 5 caracteres numéricos."""
        code = generate_verification_code()
        assert len(code) == 5
        assert code.isdigit()

    def test_zero_padded(self):
        """Mockea secrets.randbelow para retornar 0 y llama generate_verification_code(); verifica que retorna '00000'."""
        with patch("sistema_app.services.secrets.randbelow", return_value=0):
            code = generate_verification_code()
        assert code == "00000"

    def test_codes_are_not_always_equal(self):
        """Genera 20 códigos y los agrega a un set; verifica que el set tiene más de un valor distinto."""
        codes = {generate_verification_code() for _ in range(20)}
        assert len(codes) > 1


# ===========================================================================
# mask_email
# ===========================================================================

class TestMaskEmail:
    def test_long_local_part(self):
        """Llama mask_email('saosapis.666@gmail.com'); verifica que retorna 'sa*********6@gmail.com'."""
        assert mask_email("saosapis.666@gmail.com") == "sa*********6@gmail.com"

    def test_exactly_4_chars_local(self):
        """Llama mask_email('abcd@x.com') con parte local de exactamente 4 caracteres; verifica que retorna 'ab*d@x.com'."""
        assert mask_email("abcd@x.com") == "ab*d@x.com"

    def test_short_local_part_unchanged(self):
        """Llama mask_email('abc@x.com') con parte local de 3 caracteres; verifica que retorna el email sin modificar."""
        assert mask_email("abc@x.com") == "abc@x.com"

    def test_empty_string_returns_empty(self):
        """Llama mask_email('') con cadena vacía; verifica que retorna cadena vacía."""
        assert mask_email("") == ""

    def test_no_at_sign_returns_unchanged(self):
        """Llama mask_email('sinArroba') sin símbolo @; verifica que retorna la cadena sin modificar."""
        assert mask_email("sinArroba") == "sinArroba"

    def test_domain_preserved(self):
        """Llama mask_email('usuario123@dominio.org'); verifica que el resultado conserva el dominio '@dominio.org' intacto."""
        result = mask_email("usuario123@dominio.org")
        assert result.endswith("@dominio.org")


# ===========================================================================
# ReservationValidator — fechas
# ===========================================================================

class TestReservationValidatorDate:
    VALID_START = date(2026, 6, 2)
    VALID_END = date(2026, 6, 5)

    def test_valid_dates_pass(self):
        """Llama validate_date() con start=2026-06-02 y end=2026-06-05 (dentro de temporada); verifica que no lanza excepción."""
        ReservationValidator.validate_date(self.VALID_START, self.VALID_END)

    def test_end_before_start_raises(self):
        """Llama validate_date() con start posterior a end; verifica que lanza ValidationError con mensaje 'posterior'."""
        with pytest.raises(ValidationError, match="posterior"):
            ReservationValidator.validate_date(self.VALID_END, self.VALID_START)

    def test_same_day_start_end_raises(self):
        """Llama validate_date() con start igual a end; verifica que lanza ValidationError."""
        with pytest.raises(ValidationError):
            ReservationValidator.validate_date(self.VALID_START, self.VALID_START)

    def test_start_before_season_raises(self):
        """Llama validate_date() con start=2026-05-31 (antes del inicio de temporada); verifica que lanza ValidationError con 'Junio'."""
        with pytest.raises(ValidationError, match="Junio"):
            ReservationValidator.validate_date(date(2026, 5, 31), self.VALID_END)

    def test_start_after_season_raises(self):
        """Llama validate_date() con start=2026-09-01 (después del cierre de temporada); verifica que lanza ValidationError con 'Junio'."""
        with pytest.raises(ValidationError, match="Junio"):
            ReservationValidator.validate_date(date(2026, 9, 1), date(2026, 9, 5))

    def test_end_exceeds_season_raises(self):
        """Llama validate_date() con end=2026-09-02 (posterior al último día de temporada); verifica que lanza ValidationError con 'cierre'."""
        with pytest.raises(ValidationError, match="cierre"):
            ReservationValidator.validate_date(date(2026, 8, 30), date(2026, 9, 2))

    def test_end_on_season_boundary_passes(self):
        """Llama validate_date() con end=2026-09-01 (exactamente en el límite de cierre); verifica que no lanza excepción."""
        ReservationValidator.validate_date(date(2026, 8, 30), date(2026, 9, 1))

    def test_none_start_raises(self):
        """Llama validate_date() con start=None; verifica que lanza ValidationError."""
        with pytest.raises(ValidationError):
            ReservationValidator.validate_date(None, self.VALID_END)

    def test_none_end_raises(self):
        """Llama validate_date() con end=None; verifica que lanza ValidationError."""
        with pytest.raises(ValidationError):
            ReservationValidator.validate_date(self.VALID_START, None)


# ===========================================================================
# ReservationValidator — martes
# ===========================================================================

class TestReservationValidatorTuesday:
    def test_monday_passes(self):
        """Llama validate_tuesday() con la fecha 2026-06-01 (lunes); verifica que no lanza excepción."""
        monday = date(2026, 6, 1)
        assert monday.weekday() == 0
        ReservationValidator.validate_tuesday(monday)

    def test_tuesday_raises(self):
        """Llama validate_tuesday() con la fecha 2026-06-02 (martes); verifica que lanza ValidationError con mensaje 'martes'."""
        tuesday = date(2026, 6, 2)
        assert tuesday.weekday() == 1
        with pytest.raises(ValidationError, match="martes"):
            ReservationValidator.validate_tuesday(tuesday)

    def test_wednesday_passes(self):
        """Llama validate_tuesday() con la fecha 2026-06-03 (miércoles); verifica que no lanza excepción."""
        wednesday = date(2026, 6, 3)
        assert wednesday.weekday() == 2
        ReservationValidator.validate_tuesday(wednesday)

    def test_all_weekdays_except_tuesday_pass(self):
        """Llama validate_tuesday() con los 6 días de la semana distintos al martes; verifica que no lanza excepción en ninguno."""
        base = date(2026, 6, 1)
        for offset in [0, 2, 3, 4, 5, 6]:
            d = base + timedelta(days=offset)
            ReservationValidator.validate_tuesday(d)


# ===========================================================================
# ReservationValidator — personas
# ===========================================================================

class TestReservationValidatorPeople:
    def test_minimum_passes(self):
        """Llama validate_people() con el mínimo permitido (people=1); verifica que no lanza excepción."""
        ReservationValidator.validate_people(1)

    def test_maximum_passes(self):
        """Llama validate_people() con el máximo permitido (people=20); verifica que no lanza excepción."""
        ReservationValidator.validate_people(20)

    def test_zero_raises(self):
        """Llama validate_people() con people=0; verifica que lanza ValidationError."""
        with pytest.raises(ValidationError):
            ReservationValidator.validate_people(0)

    def test_negative_raises(self):
        """Llama validate_people() con people=-1; verifica que lanza ValidationError."""
        with pytest.raises(ValidationError):
            ReservationValidator.validate_people(-1)

    def test_twenty_one_raises(self):
        """Llama validate_people() con people=21 (sobre el máximo de 20); verifica que lanza ValidationError con mensaje '20'."""
        with pytest.raises(ValidationError, match="20"):
            ReservationValidator.validate_people(21)

    def test_none_raises(self):
        """Llama validate_people() con people=None; verifica que lanza ValidationError."""
        with pytest.raises(ValidationError):
            ReservationValidator.validate_people(None)


# ===========================================================================
# ReservationValidator — lodging
# ===========================================================================

@pytest.mark.django_db
class TestReservationValidatorLodging:
    def test_correct_park_and_capacity_passes(self, cabin, park):
        """Llama validate_lodging() con la cabaña, su parque correcto y people=2; verifica que no lanza excepción."""
        ReservationValidator.validate_lodging(cabin, park, 2)

    def test_wrong_park_raises(self, db, cabin, deleted_park):
        """Llama validate_lodging() con la cabaña pero un parque distinto; verifica que lanza ValidationError con mensaje 'parque'."""
        with pytest.raises(ValidationError, match="parque"):
            ReservationValidator.validate_lodging(cabin, deleted_park, 1)

    def test_exceeds_capacity_raises(self, cabin, park):
        """Llama validate_lodging() con people = cabin.capacity + 1; verifica que lanza ValidationError con mensaje 'máximo'."""
        with pytest.raises(ValidationError, match="máximo"):
            ReservationValidator.validate_lodging(cabin, park, cabin.capacity + 1)

    def test_exact_capacity_passes(self, cabin, park):
        """Llama validate_lodging() con people igual a la capacidad exacta de la cabaña; verifica que no lanza excepción."""
        ReservationValidator.validate_lodging(cabin, park, cabin.capacity)


# ===========================================================================
# AvailabilityService — cabañas
# ===========================================================================

@pytest.mark.django_db
class TestAvailabilityServiceCabin:

    def test_free_cabin_has_full_capacity(self, cabin, season_start, season_end_date):
        """Llama remaining_capacity() con una cabaña sin reservas en el rango dado; verifica que retorna la capacidad total."""
        remaining = AvailabilityService.remaining_capacity(cabin, season_start, season_end_date)
        assert remaining == cabin.capacity

    def test_booked_cabin_has_zero_capacity(self, active_reservation, cabin, season_start, season_end_date):
        """Llama remaining_capacity() con una cabaña con reserva activa en el mismo rango; verifica que retorna 0."""
        remaining = AvailabilityService.remaining_capacity(cabin, season_start, season_end_date)
        assert remaining == 0

    def test_cancelled_reservation_does_not_block_cabin(self, cancelled_reservation, cabin, season_start, season_end_date):
        """Existe una reserva cancelada en las fechas; llama remaining_capacity(); verifica que retorna la capacidad total."""
        remaining = AvailabilityService.remaining_capacity(cabin, season_start, season_end_date)
        assert remaining == cabin.capacity

    def test_non_overlapping_reservation_does_not_block(self, db, user, park, cabin):
        """Existe reserva en fechas distintas sin solapamiento; llama remaining_capacity(); verifica que retorna la capacidad total."""
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 5),
            people=1, status=Reservation.Status.ACTIVE,
        )
        remaining = AvailabilityService.remaining_capacity(cabin, date(2026, 6, 1), date(2026, 6, 5))
        assert remaining == cabin.capacity

    def test_is_lodging_available_true_when_free(self, cabin, season_start, season_end_date):
        """Llama is_lodging_available() con una cabaña libre en el rango dado y n_people=1; verifica que retorna True."""
        assert AvailabilityService.is_lodging_available(cabin, season_start, season_end_date, 1) is True

    def test_is_lodging_available_false_when_booked(self, active_reservation, cabin, season_start, season_end_date):
        """Llama is_lodging_available() con una cabaña ya reservada en el mismo rango; verifica que retorna False."""
        assert AvailabilityService.is_lodging_available(cabin, season_start, season_end_date, 1) is False


# ===========================================================================
# AvailabilityService — camping
# ===========================================================================

@pytest.mark.django_db
class TestAvailabilityServiceCamping:

    def test_free_camping_has_full_capacity(self, camping_spot, season_start, season_end_date):
        """Llama remaining_capacity() con un camping sin reservas en el rango dado; verifica que retorna la capacidad total."""
        remaining = AvailabilityService.remaining_capacity(camping_spot, season_start, season_end_date)
        assert remaining == camping_spot.capacity

    def test_partial_booking_reduces_capacity(self, db, user, park, camping_spot, season_start, season_end_date):
        """Hay una reserva activa de 3 personas en el camping; llama remaining_capacity(); verifica que retorna capacidad menos 3."""
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=3, status=Reservation.Status.ACTIVE,
        )
        remaining = AvailabilityService.remaining_capacity(camping_spot, season_start, season_end_date)
        assert remaining == camping_spot.capacity - 3

    def test_full_booking_returns_zero(self, db, user, park, camping_spot, season_start, season_end_date):
        """Hay una reserva que agota toda la capacidad del camping; llama remaining_capacity(); verifica que retorna 0."""
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=camping_spot.capacity, status=Reservation.Status.ACTIVE,
        )
        remaining = AvailabilityService.remaining_capacity(camping_spot, season_start, season_end_date)
        assert remaining == 0

    def test_people_booked_sums_overlapping(self, db, user, other_user, park, camping_spot, season_start, season_end_date):
        """Hay dos reservas activas solapadas de 3 y 4 personas; llama people_booked(); verifica que retorna 7."""
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
        """Solo existe una reserva cancelada de 5 personas; llama people_booked(); verifica que retorna 0."""
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_end_date,
            people=5, status=Reservation.Status.CANCELLED,
        )
        booked = AvailabilityService.people_booked(camping_spot, season_start, season_end_date)
        assert booked == 0

    def test_available_lodgings_returns_with_capacity_attr(self, park, camping_spot, season_start, season_end_date):
        """Llama available_lodgings() para un parque con un camping libre; verifica que retorna 1 resultado con available_capacity."""
        results = list(AvailabilityService.available_lodgings(
            park, Lodging.Kind.CAMPING, season_start, season_end_date, n_people=1
        ))
        assert len(results) == 1
        assert hasattr(results[0], "available_capacity")
        assert results[0].available_capacity == camping_spot.capacity

    def test_available_lodgings_excludes_full(self, db, user, park, camping_spot, season_start, season_end_date):
        """El camping está completamente reservado; llama available_lodgings(); verifica que retorna lista vacía."""
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
        """Llama send_confirmation_email() con una reservación activa (backend locmem); verifica que retorna True y envía correo con 'Confirmación'."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        result = NotificationService.send_confirmation_email(active_reservation)
        assert result is True
        assert len(mail.outbox) == 1
        assert "Confirmación" in mail.outbox[0].subject

    def test_send_cancellation_email(self, active_reservation, settings):
        """Llama send_cancellation_email() con una reservación activa (backend locmem); verifica que retorna True y envía correo con 'Cancelación'."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        result = NotificationService.send_cancellation_email(active_reservation)
        assert result is True
        assert len(mail.outbox) == 1
        assert "Cancelación" in mail.outbox[0].subject

    def test_send_verification_email(self, settings):
        """Llama send_verification_email() con email, código '12345' y nombre de usuario; verifica que retorna True y el cuerpo contiene el código."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        result = NotificationService.send_verification_email("test@mail.com", "12345", "Usuario")
        assert result is True
        assert len(mail.outbox) == 1
        assert "12345" in mail.outbox[0].body

    def test_no_email_user_returns_false(self, db, user, park, cabin, season_start, season_end_date):
        """Elimina el email del usuario, crea una reserva y llama send_confirmation_email(); verifica que retorna False."""
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
        """Llama _send_to() con destinatario vacío como cadena; verifica que retorna False sin intentar el envío."""
        result = NotificationService._send_to("Asunto", "Cuerpo", "")
        assert result is False


# ===========================================================================
# ReservationService — crear reserva
# ===========================================================================

@pytest.mark.django_db
class TestReservationServiceCreate:
    def test_creates_reservation_successfully(self, user, cabin, park, settings, season_start, season_end_date):
        """Llama create_reservation() con usuario, cabaña, fechas válidas y n_people=2; verifica que la reservación se persiste con status ACTIVE."""
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
        """Llama create_reservation() con start_date en martes (2026-06-02); verifica que lanza ValidationError con mensaje 'martes'."""
        tuesday = date(2026, 6, 2)
        assert tuesday.weekday() == 1
        with pytest.raises(ValidationError, match="martes"):
            ReservationService.create_reservation(
                user=user, lodging=cabin,
                start_date=tuesday, end_date=date(2026, 6, 5),
                n_people=1,
            )

    def test_raises_when_cabin_already_booked(self, user, other_user, cabin, park, season_start, season_end_date):
        """Existe reserva activa en la misma cabaña y fechas; otro usuario intenta reservar; verifica que lanza ValidationError con 'cabaña'."""
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
        """El camping está completamente ocupado; otro usuario intenta reservar 1 persona; verifica que lanza ValidationError con 'completamente'."""
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
        """Solo quedan 2 lugares en el camping; se intenta reservar 3 personas; verifica que lanza ValidationError con 'quedan'."""
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
        """El lodging pertenece a un parque con is_deleted=True; se intenta crear la reserva; verifica que lanza ValidationError con 'disponible'."""
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
        """Llama create_reservation() con fechas en mayo (fuera de temporada); verifica que lanza ValidationError con mensaje 'Junio'."""
        with pytest.raises(ValidationError, match="Junio"):
            ReservationService.create_reservation(
                user=user, lodging=cabin,
                start_date=date(2026, 5, 1), end_date=date(2026, 5, 5),
                n_people=1,
            )

    def test_raises_on_too_many_people(self, user, camping_spot, season_start, season_end_date):
        """Llama create_reservation() con n_people=21 (sobre el máximo de 20); verifica que lanza ValidationError."""
        with pytest.raises(ValidationError):
            ReservationService.create_reservation(
                user=user, lodging=camping_spot,
                start_date=season_start, end_date=season_end_date,
                n_people=21,
            )


# ===========================================================================
# ReservationService — cancelar reserva
# ===========================================================================

@pytest.mark.django_db
class TestReservationServiceCancel:
    def test_owner_can_cancel(self, user, active_reservation, settings):
        """El dueño de la reserva llama cancel_reservation(); verifica que la fila es eliminada de BD."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        pk = active_reservation.pk
        ReservationService.cancel_reservation(user, active_reservation)
        assert not Reservation.objects.filter(pk=pk).exists()

    def test_staff_can_cancel_other_user_reservation(self, staff_user, active_reservation, settings):
        """Un usuario staff llama cancel_reservation() sobre la reserva de otro usuario; verifica que la fila es eliminada de BD."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        pk = active_reservation.pk
        ReservationService.cancel_reservation(staff_user, active_reservation)
        assert not Reservation.objects.filter(pk=pk).exists()

    def test_other_user_cannot_cancel(self, other_user, active_reservation):
        """Un usuario sin permisos llama cancel_reservation() sobre la reserva de otro; verifica que lanza ValidationError con 'permisos'."""
        with pytest.raises(ValidationError, match="permisos"):
            ReservationService.cancel_reservation(other_user, active_reservation)

    def test_cannot_cancel_already_cancelled(self, user, cancelled_reservation):
        """El dueño intenta cancelar una reserva que ya está cancelada; verifica que lanza ValidationError con mensaje 'activa'."""
        with pytest.raises(ValidationError, match="activa"):
            ReservationService.cancel_reservation(user, cancelled_reservation)

    def test_get_user_reservations_returns_all(self, user, active_reservation, cancelled_reservation):
        """Llama get_user_reservations() sin filtros para un usuario con reserva activa; verifica que el pk de la activa está en el QS."""
        qs = ReservationService.get_user_reservations(user)
        pks = list(qs.values_list("pk", flat=True))
        assert active_reservation.pk in pks

    def test_get_user_reservations_only_active(self, user, active_reservation, cancelled_reservation):
        """Llama get_user_reservations(only_active=True); verifica que el QS contiene la activa y excluye la cancelada."""
        qs = ReservationService.get_user_reservations(user, only_active=True)
        assert active_reservation in qs
        assert cancelled_reservation not in qs


# ===========================================================================
# LodgingCapacityValidator
# ===========================================================================

@pytest.mark.django_db
class TestLodgingCapacityValidator:
    """Valida reducciones de capacidad sobre Lodgings con reservas existentes."""

    def test_creation_skipped(self, park):
        """Llama validate_capacity_reduction() con un Lodging recién instanciado sin pk; verifica que no lanza excepción."""
        lodging = Lodging(park=park, kind=Lodging.Kind.CABIN, name="X", capacity=5)
        LodgingCapacityValidator.validate_capacity_reduction(lodging, 1)

    def test_capacity_unchanged_skipped(self, cabin, active_reservation):
        """Llama validate_capacity_reduction() con la misma capacidad actual de la cabaña; verifica que no lanza excepción."""
        LodgingCapacityValidator.validate_capacity_reduction(cabin, cabin.capacity)

    def test_capacity_increased_skipped(self, cabin, active_reservation):
        """Llama validate_capacity_reduction() con una capacidad mayor a la actual; verifica que no lanza excepción."""
        LodgingCapacityValidator.validate_capacity_reduction(cabin, cabin.capacity + 10)

    def test_cabin_blocks_when_future_reservation_exceeds(
        self, user, park, cabin, season_start, season_end_date
    ):
        """Existe reserva activa futura con people=4; se intenta reducir capacity a 3; verifica que lanza ValidationError con 'cabaña'."""
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=4, status=Reservation.Status.ACTIVE,
        )
        with pytest.raises(ValidationError, match="cabaña"):
            LodgingCapacityValidator.validate_capacity_reduction(cabin, 3)

    def test_cabin_allows_when_within_new_capacity(
        self, user, park, cabin, season_start, season_end_date
    ):
        """Existe reserva activa futura con people=2; se reduce capacity a 3; verifica que no lanza excepción."""
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=2, status=Reservation.Status.ACTIVE,
        )
        LodgingCapacityValidator.validate_capacity_reduction(cabin, 3)

    def test_cabin_ignores_past_used_cancelled(
        self, user, park, cabin, season_start, season_end_date
    ):
        """Existen reservas pasadas y USED con people=4; se reduce capacity a 1; verifica que no lanza excepción."""
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=date(2026, 5, 20), end_date=date(2026, 5, 22),
            people=4, status=Reservation.Status.ACTIVE,
        )
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=4, status=Reservation.Status.USED,
        )
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=date(2026, 4, 5), end_date=date(2026, 4, 8),
            people=4, status=Reservation.Status.PAST,
        )
        LodgingCapacityValidator.validate_capacity_reduction(cabin, 1)

    def test_camping_sweep_blocks_when_peak_exceeds(
        self, user, park, camping_spot, season_start
    ):
        """Dos reservas solapadas de 5 y 3 personas (pico=8); se intenta reducir capacity a 7; verifica que lanza ValidationError con 'camping'."""
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_start + timedelta(days=4),
            people=5, status=Reservation.Status.ACTIVE,
        )
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start + timedelta(days=1),
            end_date=season_start + timedelta(days=3),
            people=3, status=Reservation.Status.ACTIVE,
        )
        with pytest.raises(ValidationError, match="camping"):
            LodgingCapacityValidator.validate_capacity_reduction(camping_spot, 7)

    def test_camping_sweep_allows_when_non_overlapping_fit(
        self, user, park, camping_spot, season_start
    ):
        """Dos reservas no solapadas de 5 personas (pico=5); se reduce capacity a 5; verifica que no lanza excepción."""
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_start + timedelta(days=2),
            people=5, status=Reservation.Status.ACTIVE,
        )
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start + timedelta(days=3),
            end_date=season_start + timedelta(days=5),
            people=5, status=Reservation.Status.ACTIVE,
        )
        LodgingCapacityValidator.validate_capacity_reduction(camping_spot, 5)

    def test_camping_checkout_equals_checkin_does_not_sum(
        self, user, park, camping_spot, season_start
    ):
        """Reserva A termina el día X; reserva B inicia el mismo día X; ambas con 6 personas. Se reduce a 6; verifica que no lanza excepción."""
        x = season_start + timedelta(days=2)
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=x,
            people=6, status=Reservation.Status.ACTIVE,
        )
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=x, end_date=season_start + timedelta(days=5),
            people=6, status=Reservation.Status.ACTIVE,
        )
        LodgingCapacityValidator.validate_capacity_reduction(camping_spot, 6)

    def test_camping_three_overlapping_peak_in_middle(
        self, user, park, camping_spot, season_start
    ):
        """Tres reservas solapadas con 2+3+4 personas (pico=9); a capacity 8 lanza ValidationError con '9'; a 9 no lanza excepción."""
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_start + timedelta(days=5),
            people=2, status=Reservation.Status.ACTIVE,
        )
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start + timedelta(days=1),
            end_date=season_start + timedelta(days=4),
            people=3, status=Reservation.Status.ACTIVE,
        )
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start + timedelta(days=2),
            end_date=season_start + timedelta(days=3),
            people=4, status=Reservation.Status.ACTIVE,
        )
        with pytest.raises(ValidationError, match="9"):
            LodgingCapacityValidator.validate_capacity_reduction(camping_spot, 8)
        LodgingCapacityValidator.validate_capacity_reduction(camping_spot, 9)
