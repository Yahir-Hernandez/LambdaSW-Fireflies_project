/*
 * Mapa de parques
  * @author Yahir
  * @version 1.0
  * @date 2026-12-12
  * Despliegue y control del mapa de parques, modulo que controla la 
  * interaccion mapa-usuario
 */

let map;
let markers = [];
let selectedParkId = null;
/**
 * Inicializa el mapa con los parques y los marcadores
 */
function initMap() {
    let centerLat = 19.4284;
    let centerLng = -99.1405;
    let zoom = 6;
    
    if (data_parks.length > 0) {
        centerLat = data_parks[0].latitud;
        centerLng = data_parks[0].longitud;
        zoom = 10;
    }
    
    map = L.map('map').setView([centerLat, centerLng], zoom);
    
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    }).addTo(map);
    
    createMarkers();

    populateParkList();

    populateServiceFilter();
    setupFilters();
}

/**
 * Devuelve los parques que cumplen los filtros activos (búsqueda, servicio, cabañas).
 * El filtrado es client-side sobre data_parks.
 */
function getFilteredParks() {
    const queryEl = document.getElementById('filterQuery');
    const serviceEl = document.getElementById('filterService');
    const cabinsEl = document.getElementById('filterCabins');

    const query = (queryEl?.value || '').trim().toLowerCase();
    const service = serviceEl?.value || '';
    const cabins = cabinsEl?.value || '';

    return data_parks.filter(parque => {
        if (query && !parque.nombre.toLowerCase().includes(query)) return false;
        if (service && !parque.servicios.includes(service)) return false;
        if (cabins === 'yes' && !parque.has_cabins) return false;
        if (cabins === 'no' && parque.has_cabins) return false;
        return true;
    });
}

/**
 * Llena el desplegable de servicios con la unión de servicios de todos los parques.
 */
function populateServiceFilter() {
    const select = document.getElementById('filterService');
    if (!select) return;

    const servicios = new Set();
    data_parks.forEach(parque => parque.servicios.forEach(s => servicios.add(s)));

    Array.from(servicios).sort((a, b) => a.localeCompare(b)).forEach(servicio => {
        const option = document.createElement('option');
        option.value = servicio;
        option.textContent = servicio;
        select.appendChild(option);
    });
}

/**
 * Re-renderiza marcadores y lista según los filtros actuales.
 */
function applyFilters() {
    createMarkers();
    populateParkList();
}

/**
 * Enlaza los controles del filtro a applyFilters() y el botón de limpiar.
 */
function setupFilters() {
    const queryEl = document.getElementById('filterQuery');
    const serviceEl = document.getElementById('filterService');
    const cabinsEl = document.getElementById('filterCabins');
    const clearEl = document.getElementById('filterClear');
    const toggleEl = document.getElementById('filterToggle');
    const filterEl = document.getElementById('mapFilter');

    toggleEl?.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = filterEl.classList.toggle('is-open');
        toggleEl.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    // Cerrar el panel al hacer clic fuera de él
    document.addEventListener('click', (e) => {
        if (filterEl && filterEl.classList.contains('is-open') && !filterEl.contains(e.target)) {
            filterEl.classList.remove('is-open');
            toggleEl?.setAttribute('aria-expanded', 'false');
        }
    });

    queryEl?.addEventListener('input', applyFilters);
    serviceEl?.addEventListener('change', applyFilters);
    cabinsEl?.addEventListener('change', applyFilters);

    clearEl?.addEventListener('click', () => {
        if (queryEl) queryEl.value = '';
        if (serviceEl) serviceEl.value = '';
        if (cabinsEl) cabinsEl.value = '';
        applyFilters();
    });
}

/**
 * Crea los marcadores para los parques en el mapa
 */
function createMarkers() {
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    getFilteredParks().forEach((parque, i) => {
        // Icono por marcador para escalonar la animación de aparición
        const parkIcon = L.divIcon({
            className: 'park-marker',
            html: `<div class="marker-icon" style="animation-delay:${(i * 0.03).toFixed(2)}s"><img src="${parkIconUrl}" alt="Luciérnaga" class="marker-image logo--mini"/></div>`,
            iconSize: [40, 40],
            iconAnchor: [20, 40]
        });

        const marker = L.marker([parque.latitud, parque.longitud], {
            icon: parkIcon,
            title: parque.nombre
        }).addTo(map);
        
        /*marker.bindPopup(`
            <div class="park-popup">
                <h4>${parque.nombre}</h4>
                <p><strong>Disponibilidad:</strong> ${parque.disponibilidad_actual}/${parque.maximo_visitantes}</p>
                <button onclick="selectPark(${parque.id})" class="btn-popup">Ver detalles</button>
            </div>
        `);*/
        
        marker.on('click', function() {
            selectPark(parque.id);
        });
        
        markers.push(marker);
    });
}

function populateParkList() {
    const parkList = document.getElementById('park-items');
    parkList.innerHTML = '';

    if (data_parks.length === 0) {
        parkList.innerHTML = '<div class="no-parks"><p>No hay parques registrados.</p></div>';
        return;
    }

    const parques = getFilteredParks();

    if (parques.length === 0) {
        parkList.innerHTML = '<div class="no-parks"><p>Ningún parque coincide con los filtros.</p></div>';
        return;
    }

    // Crear elemento para cada parque (los servicios solo se muestran al desplegar el detalle)
    parques.forEach((parque, i) => {
        const parkItem = document.createElement('div');
        parkItem.className = `park-item ${selectedParkId === parque.id ? 'selected' : ''}`;
        parkItem.dataset.parkId = parque.id;
        parkItem.style.animationDelay = (i * 0.04) + 's';

        // Calcular porcentaje de disponibilidad
        const availabilityPercent = (parque.disponibilidad_actual / parque.maximo_visitantes) * 100;

        parkItem.innerHTML = `
            <div class="park-item-header">
                <h4>${parque.nombre}</h4>
            </div>
            <p class="park-location">${parque.direccion}</p>
            <div class="park-availability-row">
                <span class="park-availability-label">Disponibilidad</span>
                <span class="availability-badge ${availabilityPercent > 50 ? 'high' : availabilityPercent > 20 ? 'medium' : 'low'}">
                    ${parque.disponibilidad_actual}/${parque.maximo_visitantes}
                </span>
            </div>`;

        // Evento al hacer clic en el item
        parkItem.addEventListener('click', function() {
            selectPark(parque.id);
        });

        parkList.appendChild(parkItem);
    });
}

function selectPark(parkId) {
    selectedParkId = parkId;
    const parque = data_parks.find(p => p.id === parkId);
    
    if (!parque) return;

    // Resaltar el seleccionado sin reconstruir la lista (evita re-animar las cards)
    document.querySelectorAll('.park-item').forEach(item => {
        item.classList.toggle('selected', Number(item.dataset.parkId) === parkId);
    });

    // Mostrar información detallada
    showParkInfo(parque);
    
    // Centrar el mapa en el parque seleccionado
    map.setView([parque.latitud, parque.longitud], 13);
    
    // Abrir el popup del marcador
    /*const markerIndex = data_parks.findIndex(p => p.id === parkId);
    if (markerIndex >= 0 && markers[markerIndex]) {
        markers[markerIndex].openPopup();
    }*/
}

// Mostrar información detallada del parque
function showParkInfo(parque) {
    const parkInfo = document.getElementById('park-info');
    
    // Calcular porcentaje de disponibilidad
    const availabilityPercent = (parque.disponibilidad_actual / parque.maximo_visitantes) * 100;
    
    const headerImageUrl = forestImages[Math.floor(Math.random() * forestImages.length)];
    
    parkInfo.innerHTML = `
        <div class="park-details">
            <div class="park-header-img" style="background-image: url('${headerImageUrl}');"></div>
            <div class="park-header">
                <h3>${parque.nombre}</h3>
                <div class="park-availability">
                    <span class="availability-label">Disponibilidad:</span>
                    <span class="availability-value ${availabilityPercent > 50 ? 'high' : availabilityPercent > 20 ? 'medium' : 'low'}">
                        ${parque.disponibilidad_actual}/${parque.maximo_visitantes}
                    </span>
                </div>
            </div>
            
            <div class="park-section">
                <h4><i class="fa-solid fa-location-dot"></i> Ubicación</h4>
                <p>${parque.direccion}</p>
            </div>
            
            <div class="park-section">
                <h4><i class="fa-solid fa-circle-info"></i> Descripción</h4>
                <p>${parque.descripcion || 'No hay descripción disponible.'}</p>
            </div>
            
            <div class="park-section">
                <h4><i class="fa-solid fa-concierge-bell"></i> Servicios</h4>
                <div class="services-list">
                    ${parque.servicios.length > 0 
                        ? parque.servicios.map(servicio => `<span class="service-tag">${servicio}</span>`).join('')
                        : '<p>No hay servicios registrados.</p>'
                    }
                </div>
            </div>
            
            <div class="park-section">
                <h4><i class="fa-solid fa-phone"></i> Contacto</h4>
                <div class="contact-info">
                    ${parque.telefono_contacto ? `<p><strong>Teléfono:</strong> ${parque.telefono_contacto}</p>` : ''}
                    ${parque.email_contacto ? `<p><strong>Email:</strong> ${parque.email_contacto}</p>` : ''}
                </div>
            </div>
            
            <div class="park-actions">
                <button class="btn btn--primary" onclick="reservarParque(${parque.id})">
                    <i class="fa-solid fa-calendar-check"></i> Reservar
                </button>
                <button class="btn btn--outline" onclick="verEnMapa(${parque.id})">
                    <i class="fa-solid fa-map-location-dot"></i> Ver en mapa
                </button>
            </div>
        </div>
    `;
}

// Navegar al formulario de nueva reservación con el parque preseleccionado.
// Si el usuario no ha iniciado sesión, lo mandamos al login con ?next= para
// que regrese al formulario tras autenticarse.
function reservarParque(parkId) {
    if (typeof isAuthenticated !== "undefined" && !isAuthenticated) {
        if (typeof window.openAuthDialog === 'function') {
            const target = `${reservationUrl}?park=${parkId}`;
            window.openAuthDialog(target);
            return;
        }
        window.location.href = loginUrl;
        return;
    }
    if (typeof window.openReservaModal === 'function') {
        window.openReservaModal(parkId);
        return;
    }
    alert(`Función de reserva para el parque ID: ${parkId}\nEsta funcionalidad se implementará más adelante.`);
}

// Función para centrar en el mapa (placeholder)
function verEnMapa(parkId) {
    const parque = data_parks.find(p => p.id === parkId);
    if (parque) {
        map.setView([parque.latitud, parque.longitud], 15);
    }
}

// Inicializar el mapa cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', initMap);


