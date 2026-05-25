# Probar el flujo QR de check-in en localhost

Guía operativa para probar el sistema de check-in con QR sin necesidad de
ngrok, dispositivos móviles, ni extraer manualmente adjuntos del correo
en consola.

## Setup mínimo

```bash
python manage.py migrate           # asegúrate de tener la migración 0008
python manage.py createsuperuser   # si no tienes uno
python manage.py runserver
```

Luego loguéate en <http://localhost:8000/admin/>.

## Crear una reserva de prueba

- **Opción A — desde la UI**: registrarse con un usuario normal, crear reserva en `/mapa/`.
- **Opción B — desde el admin**: Reservaciones → Añadir reserva (recuerda que la fecha de inicio no puede ser martes y debe caer dentro de jun-ago 2026).

## Obtener el QR (3 opciones, de más fácil a menos)

### Opción 1: endpoint admin (recomendado)

1. En el admin, abrir **Reservaciones**.
2. Cada fila tiene un link **"Ver QR"** en la última columna.
3. Click → se abre el PNG del QR en una pestaña nueva.
4. Mostrar esa pestaña en pantalla y escanearla desde la cámara del laptop.

> El endpoint también sirve en producción cuando un usuario perdió el correo:
> el staff puede abrir el PNG y mostrárselo o imprimirlo.

### Opción 2: input manual de UUID (sin cámara)

1. En el listado del admin, editar una reserva ACTIVE → copiar el campo `checkin_token` (es readonly).
2. Ir a **Reservaciones → "Escanear QR de check-in"**.
3. Expandir **"¿Sin cámara? Ingresar UUID manualmente"**.
4. Pegar el UUID → click **"Cargar"** (o Enter).

Funciona idéntico al flujo del scanner: muestra los detalles inline y permite confirmar la entrada.

### Opción 3: extraer del correo en consola (último recurso)

`console.EmailBackend` imprime el correo en la terminal de `runserver` pero el adjunto del QR queda como base64 ilegible. Para obtener el PNG real:

1. Cambiar el backend de email temporalmente en `.env`:

   ```dotenv
   EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend
   EMAIL_FILE_PATH=/tmp/django-emails
   ```

2. Reiniciar `runserver` y crear una nueva reserva.
3. Buscar el archivo más reciente en `/tmp/django-emails/` (extensión `.log`).
4. Abrirlo con un cliente de correo (Thunderbird/Apple Mail/etc.) — el QR se renderiza.

## Probar el check-in con la cámara

1. **Reservaciones → "Escanear QR de check-in"**.
2. El navegador pide permiso de cámara → aceptar.
3. Apuntar al QR (de la opción 1, mostrado en pantalla).
4. Los detalles cargan inline → click **"Confirmar entrada"** → status pasa a `USED`.
5. Re-escanear el mismo QR → muestra "no se puede checar" (porque ya está usada).

## Si ves "Error de red al cargar la reserva" o similar

Abre **DevTools (F12) → Console**. El JS ahora loguea el error completo con detalles (status HTTP, snippet del body de respuesta). Causas típicas:

| Síntoma en pantalla | Causa probable |
|---|---|
| `Sin conexión al servidor: ...` | `runserver` no está corriendo, o cortó la conexión. |
| `Respuesta inesperada del servidor (HTTP 302)` | La sesión admin expiró (`SESSION_COOKIE_AGE = 1800`, 30 min). Re-loguéate en `/admin/`. |
| `Respuesta inesperada del servidor (HTTP 404)` | Django retornó HTML 404 — el path no resolvió. Mira la URL en DevTools → Network. |
| `Respuesta inesperada del servidor (HTTP 500)` | Excepción en el servidor; mira la consola de `runserver` para el traceback. |
| `Reserva no encontrada.` | El UUID del QR no existe en la BD (¿reseteaste la BD después de generar el QR?). |
| `No se puede marcar como usada...` | La reserva ya está USED, CANCELLED o PAST. Esperado si re-escaneas. |

## Probar desde un teléfono

Los navegadores móviles **bloquean la cámara fuera de HTTPS** (excepto `localhost`, que no aplica para un teléfono accediendo a la IP de tu laptop). Dos caminos:

### Camino 1: túnel HTTPS con ngrok

```bash
ngrok http 8000
# → https://abc123.ngrok-free.app
```

En `.env`:

```dotenv
SITE_URL=https://abc123.ngrok-free.app
```

En `luciernagas2026/settings.py`, añadir el dominio a `ALLOWED_HOSTS`:

```python
ALLOWED_HOSTS = ['abc123.ngrok-free.app', 'localhost', '127.0.0.1']
```

Reiniciar `runserver`. Acceder al admin desde el teléfono usando la URL de ngrok, hacer login, abrir el scanner y escanear normalmente.

### Camino 2: sin cámara

El input manual de UUID también funciona en móvil. El staff puede leer el UUID del QR a simple vista (es legible al lado del código) o pedírselo al usuario.

## Resumen de URLs útiles

| Para qué | URL |
|---|---|
| Página del scanner | `/admin/sistema_app/reservation/scan/` |
| QR PNG de una reserva | `/admin/sistema_app/reservation/<id>/qr.png` |
| Datos JSON de una reserva | `/admin/sistema_app/reservation/checkin/<uuid>/data/` |
| Confirmar check-in (POST) | `/admin/sistema_app/reservation/checkin/<uuid>/confirm/` |

Todas requieren sesión con `is_staff=True`.
