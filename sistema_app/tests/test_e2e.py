"""
Pruebas de sistema (E2E) con Playwright

Cubren flujos completos desde el navegador:
    - La página principal carga con los elementos de navegación y contenido esperados
    - La página de registro muestra el formulario con los campos requeridos
    - Un usuario registrado puede iniciar sesión y es redirigido correctamente
    - Credenciales incorrectas no autentican al usuario y la página de login permanece visible
    - Un usuario no autenticado que intenta acceder al perfil es redirigido al login
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

from playwright.sync_api import expect


# ===========================================================================
# Página principal
# ===========================================================================

def test_home_page_loads(page, live_server):
    """La página principal carga y muestra las secciones de parques y el botón de reserva."""
    page.goto(live_server.url + "/")

    expect(page).to_have_title("Festival Internacional de las Luciernagas 2026")
    expect(page.locator("#parques-destacados")).to_be_visible()
    expect(page.locator("#reservar-ahora-btn")).to_be_visible()


# ===========================================================================
# Formulario de registro
# ===========================================================================

def test_register_page_shows_form_with_required_fields(page, live_server):
    """La página de registro muestra el formulario con todos los campos obligatorios."""
    page.goto(live_server.url + "/register/")

    expect(page.locator("h2.auth-dialog__title")).to_contain_text("Registrarse")
    expect(page.locator("#signup-form")).to_be_visible()
    expect(page.locator("input[name='username']")).to_be_visible()
    expect(page.locator("input[name='email']")).to_be_visible()
    expect(page.locator("input[name='password1']")).to_be_visible()
    expect(page.locator("input[name='password2']")).to_be_visible()
    expect(page.locator("input[type='submit']")).to_be_visible()


# ===========================================================================
# Login exitoso
# ===========================================================================

def test_login_with_valid_credentials_redirects(page, live_server, user):
    """Un usuario registrado puede iniciar sesión y el sistema lo redirige a la página principal."""
    page.goto(live_server.url + "/login/")

    expect(page).to_have_title("iniciar sesión")

    page.locator("input[name='username']").fill("visitante")
    page.locator("input[name='password']").fill("TestPass123!")
    page.locator("input[type='submit']").click()

    expect(page).to_have_url(live_server.url + "/")


# ===========================================================================
# Login fallido
# ===========================================================================

def test_login_with_invalid_credentials_stays_on_login(page, live_server, user):
    """Ingresar una contraseña incorrecta no autentica al usuario y la página de login sigue visible."""
    page.goto(live_server.url + "/login/")

    page.locator("input[name='username']").fill("visitante")
    page.locator("input[name='password']").fill("contrasena_incorrecta")
    page.locator("input[type='submit']").click()

    expect(page).to_have_title("iniciar sesión")
    expect(page.locator("h2.auth-dialog__title")).to_contain_text("Iniciar sesión")


# ===========================================================================
# Perfil requiere autenticación
# ===========================================================================

def test_unauthenticated_user_redirected_to_login_on_perfil(page, live_server):
    """Un usuario no autenticado que intenta visitar /perfil/ es redirigido automáticamente al login."""
    page.goto(live_server.url + "/perfil/")

    expect(page).to_have_title("iniciar sesión")
    expect(page.locator("h2.auth-dialog__title")).to_contain_text("Iniciar sesión")
