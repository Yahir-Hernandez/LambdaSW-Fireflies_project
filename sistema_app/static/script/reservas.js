/*
 * Logica del modal de reservas (frontend)
 */

(() => {
	const modal = document.getElementById('reservaModal');
	const form = document.getElementById('reservaForm');
	const parkIdInput = document.getElementById('parkId');
	const fechaInicioInput = document.getElementById('fechaInicio');
	const fechaTerminoInput = document.getElementById('fechaTermino');
	const numPersonasInput = document.getElementById('numPersonas');
	const modalParkName = document.getElementById('modalParkName');
	const summaryName = document.getElementById('reservaParkName');
	const summaryAvailability = document.getElementById('reservaParkAvailability');
	const messageEl = document.getElementById('reservaMessage');

	if (!modal || !form) {
		return;
	}

	const seasonStart = new Date('2026-06-01T00:00:00');
	const seasonEnd = new Date('2026-08-31T23:59:59');

	if (fechaInicioInput) {
		fechaInicioInput.min = '2026-06-01';
		fechaInicioInput.max = '2026-08-31';
	}
	if (fechaTerminoInput) {
		fechaTerminoInput.min = '2026-06-01';
		fechaTerminoInput.max = '2026-08-31';
	}

	let currentPark = null;

	const setMessage = (text, type = '') => {
		if (!messageEl) {
			return;
		}
		messageEl.textContent = text || '';
		messageEl.classList.remove('is-error', 'is-success');
		if (type) {
			messageEl.classList.add(type);
		}
	};

	const formatAvailability = (parque) => {
		const availabilityPercent = (parque.disponibilidad_actual / parque.maximo_visitantes) * 100;
		return `Disponibilidad: <span class="availability-badge ${availabilityPercent > 50 ? 'high' : availabilityPercent > 20 ? 'medium' : 'low'}">
                    ${parque.disponibilidad_actual}/${parque.maximo_visitantes}
                </span>`;
	};

	const updateSummary = (parque) => {
		if (summaryName) {
			summaryName.textContent = parque ? parque.nombre : 'Sin seleccionar';
		}
		if (summaryAvailability) {
			summaryAvailability.innerHTML = parque ? formatAvailability(parque) : 'Disponibilidad: --/--';
		}
		if (modalParkName) {
			modalParkName.textContent = parque ? `Reservar ${parque.nombre}` : 'Reservar Parque';
		}
	};

	const resetForm = () => {
		form.reset();
		if (parkIdInput) {
			parkIdInput.value = '';
		}
		setMessage('');
	};

	const openReservaModal = (parkId) => {
		const parks = Array.isArray(window.data_parks)
			? window.data_parks
			: typeof data_parks !== 'undefined' && Array.isArray(data_parks)
				? data_parks
				: [];
		const parque = parks.find((item) => item.id === parkId) || null;

		currentPark = parque || null;
		resetForm();
		updateSummary(currentPark);

		if (parkIdInput && currentPark) {
			parkIdInput.value = currentPark.id;
		}

		modal.classList.add('is-open');
	};

	const closeReservaModal = () => {
		modal.classList.remove('is-open');
	};

	const isTuesday = (date) => date.getDay() === 2;

	const parseDateInput = (value) => {
		if (!value) {
			return null;
		}
		const parsed = new Date(`${value}T00:00:00`);
		return Number.isNaN(parsed.getTime()) ? null : parsed;
	};

	form.addEventListener('submit', (event) => {
		event.preventDefault();
		setMessage('');

		if (!currentPark) {
			setMessage('Selecciona un parque para reservar.', 'is-error');
			return;
		}

		const fechaInicio = parseDateInput(fechaInicioInput?.value);
		const fechaTermino = parseDateInput(fechaTerminoInput?.value);
		const numPersonas = parseInt(numPersonasInput?.value, 10) || 0;

		if (!fechaInicio || !fechaTermino) {
			setMessage('Completa las fechas de inicio y término.', 'is-error');
			return;
		}

		if (fechaInicio < seasonStart || fechaInicio > seasonEnd) {
			setMessage('La fecha de inicio debe estar entre junio y agosto de 2026.', 'is-error');
			return;
		}

		if (isTuesday(fechaInicio)) {
			setMessage('No se permiten reservas con inicio en martes.', 'is-error');
			return;
		}

		if (fechaTermino < fechaInicio) {
			setMessage('La fecha de término no puede ser anterior a la fecha de inicio.', 'is-error');
			return;
		}

		if (numPersonas <= 0) {
			setMessage('El numero de personas debe ser mayor a 0.', 'is-error');
			return;
		}

		if (numPersonas > currentPark.disponibilidad_actual) {
			setMessage('La cantidad de personas supera la disponibilidad actual.', 'is-error');
			return;
		}

		setMessage('Reserva validada. Enviando...', 'is-success');
		form.submit();
	});

	window.openReservaModal = openReservaModal;
	window.closeReservaModal = closeReservaModal;
})();
