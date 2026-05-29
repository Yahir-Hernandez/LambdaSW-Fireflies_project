// Indicador de carga global minimalista.
// Expone window.AppLoader.show()/.hide() y muestra el overlay automáticamente
// al enviar cualquier <form data-loader>. Para acciones AJAX, llamar show()/hide()
// manualmente (ver verify_email.js, password_reset_verify.js, reservation_cancel.js).
(function () {
  let overlay = null;

  function ensureOverlay() {
    if (overlay) return overlay;
    overlay = document.querySelector('.app-loader');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'app-loader';
      overlay.setAttribute('aria-hidden', 'true');
      overlay.innerHTML = '<div class="app-loader__spinner"></div>';
      document.body.appendChild(overlay);
    }
    return overlay;
  }

  function show() {
    ensureOverlay().classList.add('is-active');
  }

  function hide() {
    ensureOverlay().classList.remove('is-active');
  }

  window.AppLoader = { show: show, hide: hide };

  document.addEventListener('DOMContentLoaded', function () {
    ensureOverlay();

    // Mostrar el loader al enviar formularios marcados con data-loader.
    document.querySelectorAll('form[data-loader]').forEach(function (form) {
      form.addEventListener('submit', function () {
        // Si el navegador bloquea el envío por validación nativa, no mostrar.
        if (typeof form.checkValidity === 'function' && !form.checkValidity()) return;
        show();
      });
    });
  });

  // Si el usuario vuelve con el botón "atrás" (bfcache), ocultar el overlay.
  window.addEventListener('pageshow', hide);
})();
