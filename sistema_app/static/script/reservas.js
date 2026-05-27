/*
 * Lógica del modal de reservas (frontend).
 * Consulta /api/disponibilidad/ para obtener los hospedajes (cabañas o
 * parcelas de camping) disponibles para el parque, tipo y rango de fechas
 * que el usuario eligió, y permite seleccionar uno antes de enviar.
 */

(() => {
	const modal = document.getElementById('reservaModal');
	const form = document.getElementById('reservaForm');
	if (!modal || !form) {
		return;
	}

	const parkIdInput = document.getElementById('parkId');
	const lodgingIdInput = document.getElementById('lodgingId');
	const fechaInicioInput = document.getElementById('fechaInicio');
	const fechaTerminoInput = document.getElementById('fechaTermino');
	const numPersonasInput = document.getElementById('numPersonas');
	const modalParkName = document.getElementById('modalParkName');
	const summaryName = document.getElementById('reservaParkName');
	const summaryAvailability = document.getElementById('reservaParkAvailability');
	const messageEl = document.getElementById('reservaMessage');
	const tipoVisitaGroup = document.getElementById('tipoVisitaGroup');
	const tipoVisitaCabinLabel = document.getElementById('tipoVisitaCabin');
	const lodgingOptionsEl = document.getElementById('lodgingOptions');

	const seasonStart = '2026-06-01';
	const seasonEnd = '2026-08-31';
	// El backend acepta fecha de término hasta SEASON_END + 1 día (services.py).
	const seasonEndBoundary = '2026-09-01';

	if (fechaInicioInput) {
		fechaInicioInput.min = seasonStart;
		fechaInicioInput.max = seasonEnd;
	}
	if (fechaTerminoInput) {
		fechaTerminoInput.min = seasonStart;
		fechaTerminoInput.max = seasonEndBoundary;
	}

	const isTuesday = (value) => new Date(`${value}T00:00:00`).getDay() === 2;

	// Validación cliente de RNB-01..02 (fechas en temporada, sin martes).
	// Devuelve string con el error, o null si las fechas son válidas.
	// Si alguna fecha está vacía devuelve null (estado neutro: aún sin datos).
	const validateDateRange = (start, end) => {
		if (!start || !end) return null;
		if (start < seasonStart || start > seasonEnd) {
			return 'La fecha de inicio debe estar entre Junio y Agosto de 2026.';
		}
		if (end < seasonStart || end > seasonEndBoundary) {
			return 'La fecha de término no puede exceder el cierre del festival.';
		}
		if (new Date(end) <= new Date(start)) {
			return 'La fecha de término debe ser posterior a la fecha de inicio.';
		}
		if (isTuesday(start)) {
			return 'No se permiten reservas con inicio en martes.';
		}
		return null;
	};

	let currentPark = null;
	let availableLodgings = [];
	let selectedLodgingId = null;
	let fetchSeq = 0;

	const setMessage = (text, type = '') => {
		if (!messageEl) return;
		messageEl.textContent = text || '';
		messageEl.classList.remove('is-error', 'is-success');
		if (type) messageEl.classList.add(type);
	};

	const formatAvailability = (parque) => {
		const max = parque.maximo_visitantes || 0;
		const disp = parque.disponibilidad_actual || 0;
		const pct = max > 0 ? (disp / max) * 100 : 0;
		const badge = pct > 50 ? 'high' : pct > 20 ? 'medium' : 'low';
		return `Camping: <span class="availability-badge ${badge}">${disp}/${max}</span>`;
	};

	const updateSummary = (parque) => {
		if (summaryName) summaryName.textContent = parque ? parque.nombre : 'Sin seleccionar';
		if (summaryAvailability) {
			summaryAvailability.innerHTML = parque ? formatAvailability(parque) : 'Disponibilidad: --/--';
		}
		if (modalParkName) {
			modalParkName.textContent = parque ? `Reservar en ${parque.nombre}` : 'Reservar Parque';
		}
	};

	const setTipoVisitaForPark = (parque) => {
		if (!tipoVisitaCabinLabel) return;
		const hasCabins = !!(parque && parque.has_cabins);
		tipoVisitaCabinLabel.classList.toggle('is-hidden', !hasCabins);
		const cabinRadio = tipoVisitaCabinLabel.querySelector('input[type="radio"]');
		const campingRadio = tipoVisitaGroup.querySelector('input[type="radio"][value="CAMPING"]');
		if (!hasCabins && cabinRadio?.checked && campingRadio) {
			campingRadio.checked = true;
		} else if (hasCabins && cabinRadio) {
			cabinRadio.checked = true;
		}
	};

	const getSelectedKind = () => {
		const checked = tipoVisitaGroup?.querySelector('input[type="radio"]:checked');
		return checked ? checked.value : 'CAMPING';
	};

	const renderLodgings = (lodgings, status) => {
		if (!lodgingOptionsEl) return;
		lodgingOptionsEl.innerHTML = '';
		// Limpieza segura: sin importar el status, la selección previa
		// queda invalidada al re-renderizar (sólo se restablece más abajo
		// si renderizamos cards reales).
		selectedLodgingId = null;
		if (lodgingIdInput) lodgingIdInput.value = '';

		if (status === 'hint') {
			lodgingOptionsEl.innerHTML =
				'<p class="lodging-options__hint">Selecciona fechas y tipo de visita para ver opciones disponibles.</p>';
			return;
		}
		if (status === 'loading') {
			lodgingOptionsEl.innerHTML =
				'<p class="lodging-options__hint">Buscando opciones disponibles…</p>';
			return;
		}
		if (status === 'invalid') {
			// Fechas fuera de temporada / martes — el mensaje específico
			// ya está en #reservaMessage; aquí no mostramos nada.
			return;
		}
		if (!lodgings || lodgings.length === 0) {
			lodgingOptionsEl.innerHTML =
				'<p class="lodging-options__empty">No hay opciones disponibles para esas fechas.</p>';
			return;
		}

		lodgings.forEach((lo, idx) => {
			const card = document.createElement('label');
			card.className = 'lodging-card';
			const meta = lo.kind === 'CAMPING'
				? `Lugares disponibles: ${lo.available} / ${lo.capacity}`
				: `Capacidad: ${lo.capacity} personas`;
			card.innerHTML = `
				<input type="radio" name="lodging_option" value="${lo.id}" ${idx === 0 ? 'checked' : ''}>
				<span class="lodging-card__body">
					<span class="lodging-card__name">${lo.name}</span>
					<span class="lodging-card__meta">${meta}</span>
				</span>
			`;
			card.addEventListener('change', () => {
				selectLodging(lo.id);
			});
			lodgingOptionsEl.appendChild(card);
		});
		selectLodging(lodgings[0].id);
	};

	const selectLodging = (id) => {
		selectedLodgingId = id;
		if (lodgingIdInput) lodgingIdInput.value = id;
		lodgingOptionsEl.querySelectorAll('.lodging-card').forEach((card) => {
			const radio = card.querySelector('input[type="radio"]');
			const isSelected = radio && parseInt(radio.value, 10) === id;
			card.classList.toggle('is-selected', isSelected);
			if (radio) radio.checked = isSelected;
		});
	};

	const fetchAvailability = async () => {
		if (!currentPark) return;
		const start = fechaInicioInput?.value;
		const end = fechaTerminoInput?.value;
		const kind = getSelectedKind();
		if (!start || !end) {
			setMessage('');
			renderLodgings(null, 'hint');
			return;
		}
		// Validación cliente: si las fechas están fuera de temporada o el
		// inicio cae en martes, no consultamos al backend ni mostramos
		// opciones — el formulario quedaría inutilizable de todos modos.
		const dateError = validateDateRange(start, end);
		if (dateError) {
			setMessage(dateError, 'is-error');
			renderLodgings(null, 'invalid');
			return;
		}
		setMessage('');
		const seq = ++fetchSeq;
		renderLodgings(null, 'loading');

		const params = new URLSearchParams({
			park_id: String(currentPark.id),
			kind,
			start_date: start,
			end_date: end,
		});
		try {
			const res = await fetch(`${availabilityUrl}?${params.toString()}`, {
				headers: { Accept: 'application/json' },
			});
			if (seq !== fetchSeq) return; // descartar respuestas obsoletas
			if (!res.ok) {
				renderLodgings([], 'empty');
				return;
			}
			const data = await res.json();
			availableLodgings = data.lodgings || [];
			renderLodgings(availableLodgings, 'ok');
		} catch (_err) {
			if (seq !== fetchSeq) return;
			renderLodgings([], 'empty');
		}
	};

	const resetForm = () => {
		form.reset();
		if (parkIdInput) parkIdInput.value = '';
		if (lodgingIdInput) lodgingIdInput.value = '';
		availableLodgings = [];
		selectedLodgingId = null;
		setMessage('');
		renderLodgings(null, 'hint');
	};

	const openReservaModal = (parkId) => {
		const parks = Array.isArray(window.data_parks)
			? window.data_parks
			: typeof data_parks !== 'undefined' && Array.isArray(data_parks)
				? data_parks
				: [];
		currentPark = parks.find((item) => item.id === parkId) || null;
		resetForm();
		updateSummary(currentPark);
		setTipoVisitaForPark(currentPark);
		if (parkIdInput && currentPark) parkIdInput.value = currentPark.id;
		modal.classList.add('is-open');
	};

	const closeReservaModal = () => {
		modal.classList.remove('is-open');
	};

	// Refrescar la lista cuando cambien fechas o tipo de visita.
	// Escuchamos 'change' Y 'input' para cubrir pickers móviles donde
	// 'change' a veces no se dispara hasta perder foco.
	[fechaInicioInput, fechaTerminoInput].forEach((el) => {
		if (!el) return;
		el.addEventListener('change', fetchAvailability);
		el.addEventListener('input', fetchAvailability);
	});
	tipoVisitaGroup?.addEventListener('change', (e) => {
		if (e.target?.name === 'tipo_visita') fetchAvailability();
	});

	form.addEventListener('submit', (event) => {
		setMessage('');
		if (!currentPark) {
			event.preventDefault();
			setMessage('Selecciona un parque para reservar.', 'is-error');
			return;
		}
		const start = fechaInicioInput?.value;
		const end = fechaTerminoInput?.value;
		if (!start || !end) {
			event.preventDefault();
			setMessage('Completa las fechas de inicio y término.', 'is-error');
			return;
		}
		const dateError = validateDateRange(start, end);
		if (dateError) {
			event.preventDefault();
			setMessage(dateError, 'is-error');
			return;
		}
		const numPersonas = parseInt(numPersonasInput?.value, 10) || 0;
		if (numPersonas <= 0) {
			event.preventDefault();
			setMessage('El número de personas debe ser mayor a 0.', 'is-error');
			return;
		}
		if (!selectedLodgingId) {
			event.preventDefault();
			setMessage('Selecciona una opción disponible de la lista.', 'is-error');
			return;
		}
		const chosen = availableLodgings.find((lo) => lo.id === selectedLodgingId);
		if (chosen) {
			const cap = chosen.kind === 'CAMPING' ? chosen.available : chosen.capacity;
			if (numPersonas > cap) {
				event.preventDefault();
				const noun = chosen.kind === 'CAMPING' ? 'lugares disponibles' : 'personas';
				setMessage(`La opción seleccionada admite máximo ${cap} ${noun}.`, 'is-error');
				return;
			}
		}
		setMessage('Enviando reserva...', 'is-success');
	});

	window.openReservaModal = openReservaModal;
	window.closeReservaModal = closeReservaModal;
})();
