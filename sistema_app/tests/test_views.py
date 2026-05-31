"""
Pruebas de integración de las vistas (views.py) usando Django TestClient

Lo que se prueba:
    - home: responde 200
    - register: GET 200, POST válido redirige a verificación, POST inválido muestra error
    - verify_email_page: sin sesión redirige a registro
    - verify_email_api: código correcto crea usuario, expirado retorna 400, incorrecto 400
    - resend_verification_code_api: cooldown activo retorna 429, sin cooldown renueva código
    - login: GET 200, POST válido redirige, POST inválido muestra error
    - logout: destruye sesión y redirige a home
    - perfil: requiere autenticación, muestra reservas del usuario
    - reservation_list: redirige a perfil
    - crear_reserva: POST válido redirige a perfil con mensaje, inválido redirige a mapa
    - reservation_cancel: cancela si es dueño, rechaza si no lo es
"""

import pytest

pytestmark = pytest.mark.integration

from datetime import date, timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from sistema_app.models import Lodging, PendingRegistration, Reservation


def url(name, **kwargs):
    return reverse(f"sistema_app:{name}", kwargs=kwargs if kwargs else None)


# ===========================================================================
# home
# ===========================================================================

@pytest.mark.django_db
class TestHomeView:
    def test_returns_200(self, client):
        response = client.get(url("home"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestReservationQrPng:
    def test_returns_png_without_login(self, client, active_reservation, settings):
        settings.SITE_URL = "https://luciernagas2026.onrender.com"
        response = client.get(
            reverse(
                "sistema_app:reservation_qr_png",
                args=[active_reservation.checkin_token],
            )
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")


# ===========================================================================
# register
# ===========================================================================

@pytest.mark.django_db
class TestRegisterView:
    def test_get_returns_200(self, client):
        response = client.get(url("register"))
        assert response.status_code == 200

    def test_valid_post_redirects_to_verification(self, client, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        data = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "testuser@mail.com",
            "password1": "Sup3rS3gur@!",
            "password2": "Sup3rS3gur@!",
        }
        response = client.post(url("register"), data)
        assert response.status_code == 302
        assert "verificar" in response["Location"]

    def test_valid_post_creates_pending_registration(self, client, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        data = {
            "username": "testuser2",
            "first_name": "Test",
            "last_name": "User",
            "email": "testuser2@mail.com",
            "password1": "Sup3rS3gur@!",
            "password2": "Sup3rS3gur@!",
        }
        client.post(url("register"), data)
        assert PendingRegistration.objects.filter(email="testuser2@mail.com").exists()

    def test_invalid_post_returns_200_with_errors(self, client):
        response = client.post(url("register"), {"username": "", "email": ""})
        assert response.status_code == 200
        assert "form" in response.context

    def test_duplicate_email_shows_error(self, client, user):
        data = {
            "username": "nuevo_user",
            "first_name": "Nuevo",
            "last_name": "User",
            "email": user.email, 
            "password1": "Sup3rS3gur@!",
            "password2": "Sup3rS3gur@!",
        }
        response = client.post(url("register"), data)
        assert response.status_code == 200
        assert "email" in response.context["form"].errors


# ===========================================================================
# verify_email_page
# ===========================================================================

@pytest.mark.django_db
class TestVerifyEmailPage:
    def test_without_session_redirects_to_register(self, client):
        response = client.get(url("verify_email"))
        assert response.status_code == 302
        assert "register" in response["Location"]

    def test_with_valid_session_returns_200(self, client, db, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        pending = PendingRegistration.objects.create(
            username="pend_user", email="pend@mail.com",
            password="hashed", code="11111",
        )
        session = client.session
        session["pending_registration_id"] = pending.pk
        session.save()
        response = client.get(url("verify_email"))
        assert response.status_code == 200


# ===========================================================================
# verify_email_api
# ===========================================================================

@pytest.mark.django_db
class TestVerifyEmailApi:
    def _setup_pending(self, client, code="12345"):
        pending = PendingRegistration.objects.create(
            username="verificar_user",
            email="verificar@mail.com",
            password="pbkdf2_sha256$...",
            code=code,
        )
        session = client.session
        session["pending_registration_id"] = pending.pk
        session.save()
        return pending

    def test_correct_code_creates_user(self, client, db):
        pending = self._setup_pending(client, "99999")
        response = client.post(url("verify_email_api"), {"code": "99999"})
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert User.objects.filter(username="verificar_user").exists()

    def test_wrong_code_returns_400(self, client, db):
        self._setup_pending(client, "99999")
        response = client.post(url("verify_email_api"), {"code": "00000"})
        assert response.status_code == 400
        assert "Código incorrecto" in response.json()["error"]

    def test_empty_code_returns_400(self, client, db):
        self._setup_pending(client, "99999")
        response = client.post(url("verify_email_api"), {"code": ""})
        assert response.status_code == 400

    def test_expired_code_returns_400(self, client, db):
        past = timezone.now() - timedelta(seconds=PendingRegistration.EXPIRY_SECONDS + 10)
        pending = PendingRegistration.objects.create(
            username="expired_user",
            email="expired@mail.com",
            password="hash",
            code="11111",
            created_at=past,
        )
        session = client.session
        session["pending_registration_id"] = pending.pk
        session.save()
        response = client.post(url("verify_email_api"), {"code": "11111"})
        assert response.status_code == 400
        assert "expiró" in response.json()["error"]

    def test_no_session_returns_400(self, client, db):
        response = client.post(url("verify_email_api"), {"code": "12345"})
        assert response.status_code == 400


# ===========================================================================
# resend_verification_code_api
# ===========================================================================

@pytest.mark.django_db
class TestResendVerificationCodeApi:
    def test_resend_during_cooldown_returns_429(self, client, db):
        pending = PendingRegistration.objects.create(
            username="resend_user", email="resend@mail.com",
            password="hash", code="11111",
        )
        session = client.session
        session["pending_registration_id"] = pending.pk
        session.save()
        response = client.post(url("resend_code_api"))
        assert response.status_code == 429

    def test_resend_after_cooldown_returns_200(self, client, db, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        past = timezone.now() - timedelta(seconds=PendingRegistration.RESEND_COOLDOWN_SECONDS + 10)
        pending = PendingRegistration.objects.create(
            username="resend_user2", email="resend2@mail.com",
            password="hash", code="22222", created_at=past,
        )
        session = client.session
        session["pending_registration_id"] = pending.pk
        session.save()
        response = client.post(url("resend_code_api"))
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_no_session_returns_400(self, client, db):
        response = client.post(url("resend_code_api"))
        assert response.status_code == 400


# ===========================================================================
# login
# ===========================================================================

@pytest.mark.django_db
class TestLoginView:
    def test_get_returns_200(self, client):
        response = client.get(url("login"))
        assert response.status_code == 200

    def test_valid_credentials_redirects(self, client, user):
        response = client.post(url("login"), {
            "username": "visitante",
            "password": "TestPass123!",
        })
        assert response.status_code == 302

    def test_invalid_credentials_returns_200_with_form(self, client, user):
        response = client.post(url("login"), {
            "username": "visitante",
            "password": "clave_incorrecta",
        })
        assert response.status_code == 200
        assert "form" in response.context

    def test_nonexistent_user_returns_200(self, client, db):
        response = client.post(url("login"), {
            "username": "no_existe",
            "password": "cualquier_cosa",
        })
        assert response.status_code == 200

    def test_account_blocked_after_6_failed_attempts(self, client, user):
        for _ in range(6):
            client.post(url("login"), {
                "username": "visitante",
                "password": "contrasena_incorrecta",
            })
        response = client.post(url("login"), {
            "username": "visitante",
            "password": "TestPass123!",
        })
        assert response.status_code == 200

    def test_lockout_message_shown_after_6_failed_attempts(self, client, user):
        for _ in range(6):
            client.post(url("login"), {
                "username": "visitante",
                "password": "contrasena_incorrecta",
            })
        response = client.post(url("login"), {
            "username": "visitante",
            "password": "contrasena_incorrecta",
        })
        content = response.content.decode("utf-8")
        assert "bloqueada" in content.lower() or "bloqueado" in content.lower()

    def test_session_cookie_age_is_30_minutes(self):
        from django.conf import settings as django_settings
        assert getattr(django_settings, "SESSION_COOKIE_AGE", None) == 1800

# ===========================================================================
# logout
# ===========================================================================

@pytest.mark.django_db
class TestLogoutView:
    def test_logout_redirects_to_home(self, auth_client):
        response = auth_client.get(url("logout"))
        assert response.status_code == 302
        assert "/" in response["Location"]

    def test_after_logout_cannot_access_perfil(self, auth_client):
        auth_client.get(url("logout"))
        response = auth_client.get(url("perfil"))
        assert response.status_code == 302
        assert "login" in response["Location"]


# ===========================================================================
# perfil
# ===========================================================================

@pytest.mark.django_db
class TestPerfilView:
    def test_requires_authentication(self, client):
        response = client.get(url("perfil"))
        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_authenticated_user_sees_their_reservations(self, auth_client, active_reservation):
        response = auth_client.get(url("perfil"))
        assert response.status_code == 200
        assert active_reservation in response.context["reservas"]

    def test_perfil_default_excludes_past_reservations(self, auth_client, active_reservation, cancelled_reservation, past_reservation):
        """Por default /perfil/ muestra sólo ACTIVE. PAST/USED/CANCELLED se excluyen."""
        response = auth_client.get(url("perfil"))
        assert response.status_code == 200
        reservas = response.context["reservas"]
        assert active_reservation in reservas
        assert past_reservation not in reservas
        assert cancelled_reservation not in reservas

    def test_perfil_show_past_only_includes_past(self, auth_client, active_reservation, past_reservation):
        """Con ?show=past sólo aparecen las PAST (y USED)."""
        response = auth_client.get(url("perfil") + "?show=past")
        assert response.status_code == 200
        reservas = response.context["reservas"]
        assert past_reservation in reservas
        assert active_reservation not in reservas
        assert response.context["show_past"] is True

    def test_user_does_not_see_other_users_reservations(self, auth_client, db, other_user, park, cabin, season_start, season_end_date):
        other_res = Reservation.objects.create(
            user=other_user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=1,
        )
        response = auth_client.get(url("perfil"))
        assert other_res not in response.context["reservas"]

    def test_perfil_auto_promotes_expired_active_to_past(
        self, auth_client, user, db, park, cabin
    ):
        from datetime import date
        expired = Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=date(2026, 5, 20), end_date=date(2026, 5, 22),
            people=2, status=Reservation.Status.ACTIVE,
        )
        auth_client.get(url("perfil"))
        expired.refresh_from_db()
        assert expired.status == Reservation.Status.PAST

    def test_perfil_excludes_cancelled_from_current_panel(
        self, auth_client, active_reservation, cancelled_reservation
    ):
        response = auth_client.get(url("perfil"))
        assert cancelled_reservation not in response.context["reservas"]

    def test_perfil_excludes_cancelled_from_past_panel(
        self, auth_client, cancelled_reservation
    ):
        response = auth_client.get(url("perfil") + "?show=past")
        assert cancelled_reservation not in response.context["reservas"]

    def test_perfil_current_panel_excludes_used(
        self, auth_client, user, db, park, cabin, season_start, season_end_date
    ):
        used = Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=2, status=Reservation.Status.USED,
        )
        response = auth_client.get(url("perfil"))
        assert used not in response.context["reservas"]

    def test_perfil_past_panel_includes_used_and_past(
        self, auth_client, user, db, park, cabin, season_start, season_end_date,
        past_reservation,
    ):
        used = Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=2, status=Reservation.Status.USED,
        )
        response = auth_client.get(url("perfil") + "?show=past")
        reservas = response.context["reservas"]
        assert past_reservation in reservas
        assert used in reservas

    def test_perfil_renders_status_badge_class(
        self, auth_client, active_reservation
    ):
        response = auth_client.get(url("perfil"))
        assert b'reservation-status' in response.content
        assert b'activa' in response.content


# ===========================================================================
# mapa
# ===========================================================================

@pytest.mark.django_db
class TestMapaView:
    def test_returns_200(self, client, park):
        response = client.get(url("mapa"))
        assert response.status_code == 200

    def test_only_active_parks_shown(self, client, park, deleted_park):
        response = client.get(url("mapa"))
        parques = response.context["parques"]
        names = [p.name for p in parques]
        assert park.name in names
        assert deleted_park.name not in names


# ===========================================================================
# crear_reserva
# ===========================================================================

@pytest.mark.django_db
class TestCrearReservaView:
    def test_requires_authentication(self, client, cabin):
        response = client.post(url("crear_reserva"), {
            "lodging_id": cabin.pk,
            "fecha_inicio": "2026-06-02",
            "fecha_termino": "2026-06-05",
            "num_personas": "2",
        })
        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_valid_reservation_redirects_to_perfil(self, auth_client, cabin, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        response = auth_client.post(url("crear_reserva"), {
            "lodging_id": cabin.pk,
            "fecha_inicio": "2026-06-03",  # miércoles, dentro de temporada
            "fecha_termino": "2026-06-06",
            "num_personas": "2",
        })
        assert response.status_code == 302
        assert "perfil" in response["Location"]

    def test_invalid_data_redirects_to_mapa(self, auth_client):
        response = auth_client.post(url("crear_reserva"), {
            "lodging_id": "abc",
            "fecha_inicio": "no-es-fecha",
            "fecha_termino": "tampoco",
            "num_personas": "x",
        })
        assert response.status_code == 302
        assert "mapa" in response["Location"]

    def test_tuesday_start_redirects_to_mapa_with_error(self, auth_client, cabin):
        response = auth_client.post(url("crear_reserva"), {
            "lodging_id": cabin.pk,
            "fecha_inicio": "2026-06-02", 
            "fecha_termino": "2026-06-05",
            "num_personas": "1",
        })
        assert response.status_code == 302
        assert "mapa" in response["Location"]

    def test_out_of_season_redirects_to_mapa(self, auth_client, cabin):
        response = auth_client.post(url("crear_reserva"), {
            "lodging_id": cabin.pk,
            "fecha_inicio": "2026-05-01",
            "fecha_termino": "2026-05-05",
            "num_personas": "1",
        })
        assert response.status_code == 302
        assert "mapa" in response["Location"]


# ===========================================================================
# reservation_cancel
# ===========================================================================

@pytest.mark.django_db
class TestReservationCancelView:
    def test_owner_can_cancel_and_redirects_to_perfil(self, auth_client, active_reservation, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        pk = active_reservation.pk
        response = auth_client.post(url("reservation_cancel", pk=pk))
        assert response.status_code == 302
        assert "perfil" in response["Location"]
        # Cancelar ahora ELIMINA la fila (DELETE, no marca CANCELLED).
        assert not Reservation.objects.filter(pk=pk).exists()

    def test_other_user_cannot_cancel(self, client, other_user, active_reservation, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        client.force_login(other_user)
        response = client.post(url("reservation_cancel", pk=active_reservation.pk))
        assert response.status_code == 302
        active_reservation.refresh_from_db()
        assert active_reservation.status == Reservation.Status.ACTIVE

    def test_cancel_nonexistent_returns_404(self, auth_client):
        response = auth_client.post(url("reservation_cancel", pk=99999))
        assert response.status_code == 404

    def test_requires_authentication(self, client, active_reservation):
        response = client.post(url("reservation_cancel", pk=active_reservation.pk))
        assert response.status_code == 302
        assert "login" in response["Location"]
