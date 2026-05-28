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
}

/**
 * Crea los marcadores para los parques en el mapa
 */
function createMarkers() {
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    
    const parkIcon = L.divIcon({
        className: 'park-marker',
        html: `<div class="marker-icon"><img src="${parkIconUrl}" alt="Luciérnaga" class="marker-image logo--mini"/></div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 40]
    });
    
    data_parks.forEach(parque => {
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
    const parkList = document.getElementById('park-list');
    parkList.innerHTML = '';
    
    if (data_parks.length === 0) {
        parkList.innerHTML = '<div class="no-parks"><p>No hay parques registrados.</p></div>';
        return;
    }
    
    // Crear elemento para cada parque
    data_parks.forEach(parque => {
        const parkItem = document.createElement('div');
        parkItem.className = `park-item ${selectedParkId === parque.id ? 'selected' : ''}`;
        parkItem.dataset.parkId = parque.id;
        
        // Calcular porcentaje de disponibilidad
        const availabilityPercent = (parque.disponibilidad_actual / parque.maximo_visitantes) * 100;
        
        parkItem.innerHTML = `
            <div class="park-item-header">
                <h4>${parque.nombre}</h4>
                <span class="availability-badge ${availabilityPercent > 50 ? 'high' : availabilityPercent > 20 ? 'medium' : 'low'}">
                    ${parque.disponibilidad_actual}/${parque.maximo_visitantes}
                </span>
            </div>
            <p class="park-location">${parque.direccion}</p>
            <div class="park-services">
                ${parque.servicios.map(servicio => `<span class="service-tag">${servicio}</span>`).join('')}
            </div>
        `;
        
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
    
    // Actualizar la lista para mostrar el seleccionado
    populateParkList();
    
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
    
    // Obtener imagen aleatoria 1 a 12
    const randomImgNumber = Math.floor(Math.random() * 12) + 1;
    const headerImageUrl = parkIconUrl.replace('luciernaga.png', `forests/forest_${randomImgNumber}.jpg`);
    
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


