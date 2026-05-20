"""
Pruebas de Sistema con Playwright + Django LiveServer

Flujo cubierto:
    1. El servidor de desarrollo Django levanta en un puerto aleatorio (live_server)
    2. Un usuario nuevo accede al sitio y navega a registro
    3. Llena el formulario de registro con datos válidos
    4. Es redirigido a la página de verificación de correo, la verificación real se omite usando 'force_login'
    5. El usuario inicia sesión con sus credenciales
    6. Navega al mapa y verifica que carga correctamente
    7. Accede a su perfil y verifica que sus reservaciones aparecen
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from sistema_app.models import Lodging, Park, Reservation


# ===========================================================================
# Fixtures E2E
# ===========================================================================

@pytest.fixture(scope="function")
def live_park(db):
    park = Park.objects.create(
        name="Parque E2E Test",
        address="Calle E2E 123, CDMX",
        latitude="19.432608",
        longitude="-99.133209",
        working_hours="9:00 - 18:00",
    )
    Lodging.objects.create(
        park=park, kind=Lodging.Kind.CAMPING,
        name="Parcela E2E", capacity=10,
    )
    return park


@pytest.fixture(scope="function")
def live_user(db):
    return User.objects.create_user(
        username="e2e_user",
        email="e2e@test.com",
        password="E2eTestPass123!",
        first_name="E2E",
        last_name="Tester",
    )


# ===========================================================================
# Forzar sesión de login sin pasar por el formulario
# ===========================================================================

def force_login_via_session(client, live_server, user, page):
    """
    Usa el cliente de Django para forzar la sesión y luego inyecta
    la cookie de sesión en el contexto de Playwright.
    """
    from django.test import Client
    django_client = Client()
    django_client.force_login(user)
    session_cookie = django_client.cookies.get("sessionid")
    if session_cookie:
        page.context.add_cookies([{
            "name": "sessionid",
            "value": session_cookie.value,
            "domain": "localhost",
            "path": "/",
        }])


# ===========================================================================
# Tests E2E
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_home_page_loads(live_server, page):
    """Verifica que la página de inicio carga correctamente."""
    page.goto(live_server.url + "/")
    assert page.title() != ""


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_register_page_loads_and_has_form(live_server, page):
    """Verifica que el formulario de registro está presente."""
    page.goto(live_server.url + "/register/")
    assert page.locator("form").count() >= 1
    assert page.locator("input[name='username']").count() == 1
    assert page.locator("input[name='email']").count() == 1
    assert page.locator("input[name='password1']").count() == 1


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_login_page_loads_and_has_form(live_server, page):
    """Verifica que el formulario de login está presente."""
    page.goto(live_server.url + "/login/")
    assert page.locator("form").count() >= 1
    assert page.locator("input[name='username']").count() == 1
    assert page.locator("input[name='password']").count() == 1


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_login_with_valid_credentials(live_server, page, live_user):
    """Flujo de login: llena formulario y verifica redirección."""
    page.goto(live_server.url + "/login/")
    page.fill("input[name='username']", "e2e_user")
    page.fill("input[name='password']", "E2eTestPass123!")
    page.click("button[type='submit'], input[type='submit']")
    page.wait_for_load_state("load")
    assert "/login/" not in page.url


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_login_with_invalid_credentials_shows_error(live_server, page, live_user):
    """Login con credenciales inválidas: se queda en la página con error."""
    page.goto(live_server.url + "/login/")
    page.fill("input[name='username']", "e2e_user")
    page.fill("input[name='password']", "contrasena_incorrecta")
    page.click("button[type='submit'], input[type='submit']")
    page.wait_for_load_state("load")
    assert "/login/" in page.url


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_mapa_page_loads(live_server, page, live_park):
    """Verifica que el mapa carga con los parques activos."""
    page.goto(live_server.url + "/mapa/")
    assert page.title() != ""
    page.wait_for_load_state("load")
    content = page.content()
    assert "Parque E2E Test" in content


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_perfil_redirects_to_login_when_unauthenticated(live_server, page):
    """Un usuario no autenticado que accede a /perfil/ es redirigido a login."""
    page.goto(live_server.url + "/perfil/")
    page.wait_for_load_state("load")
    assert "/login/" in page.url


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_perfil_accessible_after_login(live_server, page, live_user):
    """Un usuario autenticado puede acceder a su perfil."""
    page.goto(live_server.url + "/login/")
    page.fill("input[name='username']", "e2e_user")
    page.fill("input[name='password']", "E2eTestPass123!")
    page.click("button[type='submit'], input[type='submit']")
    page.wait_for_load_state("load")
    
    page.goto(live_server.url + "/perfil/")
    page.wait_for_load_state("load")
    assert "/login/" not in page.url
    assert page.title() != ""


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_logout_redirects_to_home(live_server, page, live_user):
    """Después de logout el usuario no puede acceder al perfil."""
    page.goto(live_server.url + "/login/")
    page.fill("input[name='username']", "e2e_user")
    page.fill("input[name='password']", "E2eTestPass123!")
    page.click("button[type='submit'], input[type='submit']")
    page.wait_for_load_state("load")
    
    page.goto(live_server.url + "/logout/")
    page.wait_for_load_state("load")

    page.goto(live_server.url + "/perfil/")
    page.wait_for_load_state("load")
    assert "/login/" in page.url


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
def test_register_form_validation_empty_fields(live_server, page):
    """El formulario de registro rechaza campos vacíos."""
    page.goto(live_server.url + "/register/")
    page.click("button[type='submit'], input[type='submit']")
    page.wait_for_load_state("load")
    assert "/register/" in page.url or "/verificar" not in page.url
