"""
Pruebas unitarias de los modelos de sistema_app

Lo que se prueba:
    - Service: __str__(), unicidad de nombre
    - Park: __str__(), soft_delete(), restore(), has_cabins, camping_capacity
    - ParkQuerySet: active()
    - Lodging: __str__(), unique_together, full_clean()
    - Reservation: is_cancellable(), __str__(), status por defecto
    - PendingRegistration: is_expired(), seconds_until_resend(), seconds_elapsed()
"""

import pytest

pytestmark = pytest.mark.unit

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from sistema_app.models import Lodging, Park, PendingRegistration, Reservation, Service


# ===========================================================================
# Service
# ===========================================================================

@pytest.mark.django_db
class TestServiceModel:
    def test_str_returns_name(self):
        """Crea un Service con nombre 'Estacionamiento' y verifica que str() retorna ese nombre."""
        svc = Service.objects.create(name="Estacionamiento")
        assert str(svc) == "Estacionamiento"

    def test_name_is_unique(self):
        """Crea dos Services con el mismo nombre 'WiFi' y verifica que la BD lanza IntegrityError."""
        from django.db import IntegrityError
        Service.objects.create(name="WiFi")
        with pytest.raises(IntegrityError):
            Service.objects.create(name="WiFi")


# ===========================================================================
# Park
# ===========================================================================

@pytest.mark.django_db
class TestParkModel:
    def test_str_returns_name(self, park):
        """Usa el fixture park y verifica que str() retorna el nombre del parque."""
        assert str(park) == park.name

    def test_soft_delete_sets_flag(self, park):
        """Llama park.soft_delete() y recarga desde BD; verifica que is_deleted cambia a True."""
        park.soft_delete()
        park.refresh_from_db()
        assert park.is_deleted is True

    def test_soft_delete_idempotent(self, park):
        """Llama park.soft_delete() dos veces consecutivas; verifica que no lanza error y is_deleted permanece True."""
        park.soft_delete()
        park.soft_delete()
        park.refresh_from_db()
        assert park.is_deleted is True

    def test_soft_delete_raises_if_park_has_active_reservations(self, active_reservation, park):
        """Intenta hacer soft_delete() en un parque con reservación activa; verifica que lanza excepción."""
        with pytest.raises(Exception):
            park.soft_delete()

    def test_restore_clears_flag(self, park):
        """Hace soft_delete() seguido de restore() y recarga desde BD; verifica que is_deleted vuelve a False."""
        park.soft_delete()
        park.restore()
        park.refresh_from_db()
        assert park.is_deleted is False

    def test_restore_idempotent(self, park):
        """Llama restore() en un parque que nunca fue eliminado; verifica que no lanza error y is_deleted permanece False."""
        park.restore()
        park.refresh_from_db()
        assert park.is_deleted is False

    def test_has_cabins_true_when_cabin_exists(self, park, cabin):
        """El parque tiene un Lodging tipo CABIN; verifica que has_cabins retorna True."""
        assert park.has_cabins is True

    def test_has_cabins_false_when_no_cabin(self, park, camping_spot):
        """El parque solo tiene un Lodging tipo CAMPING; verifica que has_cabins retorna False."""
        assert park.has_cabins is False

    def test_has_cabins_false_when_no_lodgings(self, park):
        """El parque no tiene ningún Lodging; verifica que has_cabins retorna False."""
        assert park.has_cabins is False

    def test_camping_capacity_sums_all_camping_lodgings(self, park):
        """Crea dos Lodgings tipo CAMPING con capacidades 10 y 15; verifica que camping_capacity retorna 25."""
        Lodging.objects.create(park=park, kind=Lodging.Kind.CAMPING, name="P-1", capacity=10)
        Lodging.objects.create(park=park, kind=Lodging.Kind.CAMPING, name="P-2", capacity=15)
        assert park.camping_capacity == 25

    def test_camping_capacity_ignores_cabins(self, park, cabin):
        """El parque tiene una cabaña y un camping con capacidad 8; verifica que camping_capacity retorna 8."""
        Lodging.objects.create(park=park, kind=Lodging.Kind.CAMPING, name="P-1", capacity=8)
        assert park.camping_capacity == 8

    def test_camping_capacity_zero_when_no_camping(self, park, cabin):
        """El parque solo tiene cabañas sin ningún camping; verifica que camping_capacity retorna 0."""
        assert park.camping_capacity == 0

    def test_camping_capacity_zero_when_no_lodgings(self, park):
        """El parque no tiene ningún alojamiento; verifica que camping_capacity retorna 0."""
        assert park.camping_capacity == 0


# ===========================================================================
# ParkQuerySet
# ===========================================================================

@pytest.mark.django_db
class TestParkQuerySet:
    def test_active_excludes_deleted(self, park, deleted_park):
        """Llama Park.objects.active() con un parque activo y uno eliminado; verifica que el QS incluye al activo y excluye al eliminado."""
        qs = Park.objects.active()
        assert park in qs
        assert deleted_park not in qs

    def test_active_returns_all_non_deleted(self, db):
        """Crea dos parques (uno activo y uno con is_deleted=True) y llama active(); verifica que solo el activo aparece."""
        p1 = Park.objects.create(name="A", address="X", latitude=1, longitude=1)
        p2 = Park.objects.create(name="B", address="Y", latitude=2, longitude=2, is_deleted=True)
        active = list(Park.objects.active())
        assert p1 in active
        assert p2 not in active


# ===========================================================================
# Lodging
# ===========================================================================

@pytest.mark.django_db
class TestLodgingModel:
    def test_str_includes_park_kind_name(self, cabin, park):
        """Llama str() sobre la cabaña del fixture; verifica el formato 'Parque · Tipo: Nombre'."""
        expected = f"{park.name} · Cabaña: {cabin.name}"
        assert str(cabin) == expected

    def test_unique_together_park_name(self, park):
        """Crea dos Lodgings distintos en el mismo parque con el mismo nombre; verifica que lanza IntegrityError."""
        from django.db import IntegrityError
        Lodging.objects.create(park=park, kind=Lodging.Kind.CAMPING, name="Parcela X", capacity=5)
        with pytest.raises(IntegrityError):
            Lodging.objects.create(park=park, kind=Lodging.Kind.CABIN, name="Parcela X", capacity=3)

    def test_different_parks_can_share_name(self, db):
        """Crea dos Lodgings con el mismo nombre pero en parques distintos; verifica que ambos se guardan sin error."""
        p1 = Park.objects.create(name="Parque 1", address="A", latitude=1, longitude=1)
        p2 = Park.objects.create(name="Parque 2", address="B", latitude=2, longitude=2)
        Lodging.objects.create(park=p1, kind=Lodging.Kind.CAMPING, name="Lote 1", capacity=5)
        Lodging.objects.create(park=p2, kind=Lodging.Kind.CAMPING, name="Lote 1", capacity=5)
        assert Lodging.objects.filter(name="Lote 1").count() == 2

    def test_full_clean_raises_when_capacity_reduction_violates(
        self, user, park, cabin, season_start, season_end_date
    ):
        """Crea reserva activa con people=4 en la cabaña, reduce capacity a 2 y llama full_clean(); verifica que lanza ValidationError."""
        from django.core.exceptions import ValidationError as DJValidationError
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=4, status=Reservation.Status.ACTIVE,
        )
        cabin.capacity = 2
        with pytest.raises(DJValidationError):
            cabin.full_clean()

    def test_full_clean_passes_when_no_future_reservations(self, cabin):
        """Reduce la capacity de una cabaña sin reservas futuras y llama full_clean(); verifica que no lanza excepción."""
        cabin.capacity = 1
        cabin.full_clean()


# ===========================================================================
# Reservation
# ===========================================================================

@pytest.mark.django_db
class TestReservationModel:
    def test_is_cancellable_active_future(self, active_reservation):
        """Llama is_cancellable() en una reservación activa con fecha futura; verifica que retorna True."""
        assert active_reservation.is_cancellable() is True

    def test_is_cancellable_false_when_cancelled(self, cancelled_reservation):
        """Llama is_cancellable() en una reservación cancelada; verifica que retorna False."""
        assert cancelled_reservation.is_cancellable() is False

    def test_is_cancellable_false_when_past_status(self, past_reservation):
        """Llama is_cancellable() en una reservación con status PAST; verifica que retorna False."""
        assert past_reservation.is_cancellable() is False

    def test_is_cancellable_false_when_start_date_today(self, db, user, park, cabin):
        """Crea una reservación activa cuya start_date es hoy; verifica que is_cancellable() retorna False."""
        today = timezone.localdate()
        res = Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=today, end_date=today + timedelta(days=2),
            people=1, status=Reservation.Status.ACTIVE,
        )
        assert res.is_cancellable() is False

    def test_is_cancellable_false_when_start_date_past(self, db, user, park, cabin):
        """Crea una reservación activa cuya start_date fue ayer; verifica que is_cancellable() retorna False."""
        yesterday = timezone.localdate() - timedelta(days=1)
        res = Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=yesterday, end_date=yesterday + timedelta(days=2),
            people=1, status=Reservation.Status.ACTIVE,
        )
        assert res.is_cancellable() is False

    def test_str_includes_pk_user_park(self, active_reservation, user, park):
        """Llama str() sobre una reservación activa; verifica que el string contiene pk, username y nombre del parque."""
        s = str(active_reservation)
        assert str(active_reservation.pk) in s
        assert user.username in s
        assert park.name in s

    def test_status_default_is_active(self, db, user, park, cabin, season_start, season_end_date):
        """Crea una Reservation sin especificar status; verifica que el valor por defecto es ACTIVE."""
        res = Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date, people=1,
        )
        assert res.status == Reservation.Status.ACTIVE


# ===========================================================================
# PendingRegistration
# ===========================================================================

@pytest.mark.django_db
class TestPendingRegistrationModel:
    def test_is_expired_false_when_fresh(self, db):
        """Crea un PendingRegistration recién creado y llama is_expired(); verifica que retorna False."""
        pending = PendingRegistration.objects.create(
            username="nuevo", email="nuevo@test.com", password="hash", code="12345"
        )
        assert pending.is_expired() is False

    def test_is_expired_true_after_expiry(self, db):
        """Crea un PendingRegistration con created_at en EXPIRY_SECONDS+1 en el pasado; verifica que is_expired() retorna True."""
        past = timezone.now() - timedelta(seconds=PendingRegistration.EXPIRY_SECONDS + 1)
        pending = PendingRegistration.objects.create(
            username="viejo", email="viejo@test.com", password="hash", code="99999",
            created_at=past,
        )
        assert pending.is_expired() is True

    def test_seconds_until_resend_positive_when_fresh(self, db):
        """Crea un registro recién creado y llama seconds_until_resend(); verifica que retorna valor positivo dentro del cooldown."""
        pending = PendingRegistration.objects.create(
            username="usuario1", email="u1@test.com", password="hash", code="11111"
        )
        remaining = pending.seconds_until_resend()
        assert 0 < remaining <= PendingRegistration.RESEND_COOLDOWN_SECONDS

    def test_seconds_until_resend_zero_after_cooldown(self, db):
        """Crea un registro con created_at pasado el tiempo de cooldown; verifica que seconds_until_resend() retorna 0."""
        past = timezone.now() - timedelta(seconds=PendingRegistration.RESEND_COOLDOWN_SECONDS + 1)
        pending = PendingRegistration.objects.create(
            username="usuario2", email="u2@test.com", password="hash", code="22222",
            created_at=past,
        )
        assert pending.seconds_until_resend() == 0

    def test_seconds_elapsed_grows_with_time(self, db):
        """Crea un registro con created_at hace 60 segundos; verifica que seconds_elapsed() retorna un valor >= 60."""
        past = timezone.now() - timedelta(seconds=60)
        pending = PendingRegistration.objects.create(
            username="usuario3", email="u3@test.com", password="hash", code="33333",
            created_at=past,
        )
        assert pending.seconds_elapsed() >= 60
