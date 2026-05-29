// Lógica compartida de los modales legales (Términos y Condiciones / Aviso de
// Privacidad). Disponible en cualquier página que incluya partials/legal_modals.html
// y enlaces/botones con [data-open-modal="<id-del-modal>"].
(function () {
	function openModal(id) {
		const modal = document.getElementById(id);
		if (modal) {
			modal.classList.add('is-open');
			document.body.style.overflow = 'hidden';
		}
	}

	function closeModal(modal) {
		if (modal) {
			modal.classList.remove('is-open');
			document.body.style.overflow = '';
		}
	}

	// Abrir: cualquier elemento con data-open-modal
	document.querySelectorAll('[data-open-modal]').forEach(function (trigger) {
		trigger.addEventListener('click', function (e) {
			e.preventDefault();
			openModal(trigger.dataset.openModal);
		});
	});

	// Cerrar: botón con data-close-modal
	document.querySelectorAll('[data-close-modal]').forEach(function (btn) {
		btn.addEventListener('click', function () {
			closeModal(btn.closest('.tc-modal-overlay'));
		});
	});

	// Aceptar ("Entendido"): marca la casilla de términos si existe y cierra
	document.querySelectorAll('.tc-modal__accept').forEach(function (btn) {
		btn.addEventListener('click', function () {
			const checkbox = document.getElementById('id_terms_accepted');
			if (checkbox) checkbox.checked = true;
			closeModal(btn.closest('.tc-modal-overlay'));
		});
	});

	// Cerrar al hacer click en el overlay
	document.querySelectorAll('.tc-modal-overlay').forEach(function (overlay) {
		overlay.addEventListener('click', function (e) {
			if (e.target === overlay) closeModal(overlay);
		});
	});

	// Cerrar con Escape
	document.addEventListener('keydown', function (e) {
		if (e.key === 'Escape') {
			document.querySelectorAll('.tc-modal-overlay.is-open').forEach(closeModal);
		}
	});
})();
