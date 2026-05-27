(() => {
  const menuBtn = document.querySelector('.nav__menu-btn');
  const sidebar = document.getElementById('nav-sidebar');
  const backdrop = document.querySelector('[data-nav-backdrop]');
  const closeBtn = sidebar?.querySelector('.nav-sidebar__close');

  if (menuBtn && sidebar && backdrop) {
    const open = () => {
      sidebar.classList.add('is-open');
      backdrop.classList.add('is-visible');
      menuBtn.setAttribute('aria-expanded', 'true');
      sidebar.setAttribute('aria-hidden', 'false');
    };

    const close = () => {
      sidebar.classList.remove('is-open');
      backdrop.classList.remove('is-visible');
      menuBtn.setAttribute('aria-expanded', 'false');
      sidebar.setAttribute('aria-hidden', 'true');
    };

    menuBtn.addEventListener('click', open);
    backdrop.addEventListener('click', close);
    closeBtn?.addEventListener('click', close);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') close();
    });
  }

  const errorToasts = Array.from(
    document.querySelectorAll('.flash-messages__item--error')
  );
  if (errorToasts.length > 0) {
    const dlg = document.getElementById('error-dialog');
    const messageEl = document.getElementById('error-dialog-message');
    if (dlg && messageEl) {
      messageEl.textContent = errorToasts
        .map((el) => el.textContent.trim())
        .filter(Boolean)
        .join(' ');

      errorToasts.forEach((el) => el.remove());
      const list = document.querySelector('.flash-messages');
      if (list && list.children.length === 0) list.remove();

      if (typeof dlg.showModal === 'function') dlg.showModal();
      else dlg.setAttribute('open', '');

      const close = () => dlg.close();
      document.getElementById('error-dialog-ok')?.addEventListener('click', close);
      document.getElementById('error-dialog-close')?.addEventListener('click', close);
      dlg.addEventListener('click', (e) => {
        if (e.target === dlg) close();
      });
    }
  }

  const authDialog = document.getElementById('auth-required-dialog');
  if (authDialog) {
    const close = document.getElementById('auth-required-close');
    const defaultNext = authDialog.dataset.defaultNext || '';

    window.openAuthDialog = function (nextUrl) {
      const target = nextUrl || defaultNext;
      authDialog.querySelectorAll('[data-auth-action]').forEach((link) => {
        const base = link.dataset.baseUrl;
        link.href = `${base}?next=${encodeURIComponent(target)}`;
      });
      if (typeof authDialog.showModal === 'function') authDialog.showModal();
      else authDialog.setAttribute('open', '');
    };

    close?.addEventListener('click', () => authDialog.close());
    authDialog.addEventListener('click', (e) => {
      if (e.target === authDialog) authDialog.close();
    });
  }
})();
