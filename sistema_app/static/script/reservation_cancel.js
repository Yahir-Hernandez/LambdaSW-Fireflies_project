// Cancelación de reservas desde el perfil: confirmación con modal + POST vía fetch.
// La vista server-side sigue siendo sistema_app:reservation_cancel; aquí solo
// se gestiona la UI (diálogos) y el envío AJAX con el token CSRF.
(function () {
  // Obtener CSRF de las cookies (método estándar Django).
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  const csrftoken = getCookie('csrftoken');

  // Referencias a los diálogos.
  const confirmDialog = document.getElementById('cancel-confirm-dialog');
  const successDialog = document.getElementById('cancel-success-dialog');
  const errorDialog = document.getElementById('error-dialog'); // del base.html
  const parkNameSpan = document.getElementById('cancel-park-name');
  const confirmYes = document.getElementById('cancel-dialog-yes');
  const confirmNo = document.getElementById('cancel-dialog-no');
  const successClose = document.getElementById('cancel-success-close');

  // Si la página no tiene los modales de cancelación, no hay nada que hacer.
  if (!confirmDialog || !successDialog) return;

  let currentCancelUrl = null;

  // Función auxiliar para mostrar el diálogo de error.
  function showError(msg) {
    const msgEl = document.getElementById('error-dialog-message');
    if (msgEl) msgEl.textContent = msg;
    if (errorDialog) errorDialog.showModal();
  }

  // Evento en todos los botones "Cancelar reserva".
  document.querySelectorAll('.js-cancel-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const park = btn.dataset.reservaPark;
      const url = btn.dataset.cancelUrl;
      if (!park || !url) return;
      parkNameSpan.textContent = park;
      currentCancelUrl = url;
      confirmDialog.showModal();
    });
  });

  // Cerrar modal de confirmación.
  confirmNo.addEventListener('click', () => confirmDialog.close());

  // Confirmar cancelación.
  confirmYes.addEventListener('click', async () => {
    if (!currentCancelUrl) return;
    confirmYes.disabled = true;
    confirmNo.disabled = true;
    // Cerrar el diálogo de confirmación ANTES de mostrar el loader: un <dialog>
    // abierto con showModal() vive en el top-layer del navegador y taparía el
    // overlay del loader.
    confirmDialog.close();
    if (window.AppLoader) window.AppLoader.show();
    try {
      const response = await fetch(currentCancelUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
        },
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({ error: 'Error del servidor' }));
        throw new Error(data.error || 'Error al cancelar la reserva');
      }
      // Éxito: ocultar loader, mostrar confirmación y recargar automáticamente.
      if (window.AppLoader) window.AppLoader.hide();
      successDialog.showModal();
      setTimeout(() => { window.location.reload(); }, 1500);
    } catch (error) {
      if (window.AppLoader) window.AppLoader.hide();
      showError(error.message);
    } finally {
      confirmYes.disabled = false;
      confirmNo.disabled = false;
    }
  });

  // Cerrar modal de éxito manualmente (el botón puede no existir: auto-recarga).
  if (successClose) {
    successClose.addEventListener('click', () => {
      successDialog.close();
      window.location.reload();
    });
  }

  // Cerrar modales al hacer clic fuera.
  [confirmDialog, successDialog].forEach((dialog) => {
    dialog.addEventListener('click', (e) => {
      if (e.target === dialog) dialog.close();
    });
  });
})();
