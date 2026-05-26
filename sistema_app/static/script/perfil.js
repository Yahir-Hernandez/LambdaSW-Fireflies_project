/*
 * Script para la página de perfil
 * @author Yahir
 * @version 1.0
 * @date 2026-12-14
 * Controla la interacción en la página de perfil del usuario
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Página de perfil cargada');
    
    // Inicializar funcionalidades
    initProfilePage();
    
    // Agregar event listeners
    setupEventListeners();
});

// Inicializar la página de perfil
function initProfilePage() {
    console.log('Inicializando página de perfil para:', usuarioName);
    
    // Actualizar estadísticas si es necesario
    updateProfileStats();

    // Asignar imagenes aleatorias a las reservas
    setRandomReservationImages();
    
    // Verificar si hay notificaciones pendientes
    checkNotifications();
}

function setRandomReservationImages() {
    const images = Array.isArray(window.forestImages) ? window.forestImages : [];
    if (images.length === 0) return;

    const cards = document.querySelectorAll('.reservation-image__img');
    if (!cards.length) return;

    cards.forEach((img) => {
        const idx = Math.floor(Math.random() * images.length);
        img.src = images[idx];
    });
}

// Configurar event listeners
function setupEventListeners() {
    // Botón para cambiar foto de perfil
    const changePhotoBtn = document.querySelector('.profile-avatar-actions .btn');
    if (changePhotoBtn) {
        changePhotoBtn.addEventListener('click', function(e) {
            e.preventDefault();
            changeProfilePhoto();
        });
    }
    
    // Botón para editar perfil
    const editProfileBtn = document.querySelector('.profile-actions .btn--primary');
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', function(e) {
            e.preventDefault();
            editProfile();
        });
    }
    
    // Botones de ver detalles en reservas
    const viewDetailsBtns = document.querySelectorAll('.reservation-actions .btn--outline');
    if (viewDetailsBtns) {
        viewDetailsBtns.forEach(btn => {
            if (btn.type === 'submit' || btn.closest('form')) return;
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const reservationCard = this.closest('.reservation-card');
                viewReservationDetails(reservationCard);
            });
        });
    }   
    
    // Botones de ver entrada en reservas confirmadas
    const viewTicketBtns = document.querySelectorAll('.reservation-actions .btn--primary');
    if (viewTicketBtns) {
        viewTicketBtns.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const reservationCard = this.closest('.reservation-card');
                viewReservationTicket(reservationCard);
            });
        });
    }
    
    // Enlaces de configuración
    const settingLinks = document.querySelectorAll('.setting-item a');
    if (settingLinks) {
        settingLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const settingType = this.closest('.setting-item').querySelector('h3').textContent;
                openSetting(settingType);
            });
        });
    }
}

// Actualizar estadísticas del perfil
function updateProfileStats() {
    // Aquí podrías hacer una llamada AJAX para obtener estadísticas actualizadas
    // Por ahora, solo mostramos un mensaje en consola
    console.log('Estadísticas del perfil actualizadas');
    
    // Ejemplo de cómo actualizar estadísticas dinámicamente
    // const statsElement = document.querySelector('.profile-stats');
    // if (statsElement) {
    //     // Actualizar contenido dinámico aquí
    // }
}

// Verificar notificaciones
function checkNotifications() {
    // Aquí podrías verificar si el usuario tiene notificaciones pendientes
    // Por ejemplo, reservas próximas, mensajes, etc.
    
    // Ejemplo de notificación
    const today = new Date();
    const nextWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
    
    // Simular una notificación de reserva próxima
    const hasUpcomingReservation = false; // Cambiar a true para probar
    
    if (hasUpcomingReservation) {
        showNotification('Tienes una reserva próxima para el ' + nextWeek.toLocaleDateString('es-MX'));
    }
}

// Mostrar notificación
function showNotification(message) {
    // Crear elemento de notificación
    const notification = document.createElement('div');
    notification.className = 'profile-notification';
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fa-solid fa-bell"></i>
            <span>${message}</span>
            <button class="notification-close"><i class="fa-solid fa-times"></i></button>
        </div>
    `;
    
    // Agregar al DOM
    const profileContainer = document.querySelector('.profile-container');
    if (profileContainer) {
        profileContainer.insertBefore(notification, profileContainer.firstChild);
        
        // Agregar estilos dinámicos
        const style = document.createElement('style');
        style.textContent = `
            .profile-notification {
                background: rgba(255, 186, 10, 0.1);
                border: 1px solid var(--accent);
                border-radius: 8px;
                padding: 12px 16px;
                margin-bottom: 20px;
                animation: slideIn 0.3s ease;
            }
            
            .notification-content {
                display: flex;
                align-items: center;
                gap: 10px;
                color: var(--text);
            }
            
            .notification-content i {
                color: var(--accent);
            }
            
            .notification-close {
                background: none;
                border: none;
                color: var(--text-dim);
                cursor: pointer;
                margin-left: auto;
                padding: 4px;
                border-radius: 4px;
                transition: background 0.2s;
            }
            
            .notification-close:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        `;
        document.head.appendChild(style);
        
        // Agregar evento para cerrar notificación
        const closeBtn = notification.querySelector('.notification-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                notification.style.opacity = '0';
                notification.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    notification.remove();
                }, 300);
            });
        }
        
        // Auto-ocultar después de 10 segundos
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.opacity = '0';
                notification.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 10000);
    }
}

// Ver detalles de reserva
function viewReservationDetails(reservationCard) {
    // Obtener información de la reserva
    const parkName = reservationCard.querySelector('.reservation-park').textContent;
    const status = reservationCard.querySelector('.reservation-status').textContent;
    
    console.log('Viendo detalles de reserva:', { parkName, status });
    
    // Aquí podrías mostrar un modal con más detalles
    // o redirigir a una página de detalles
    
    showNotification(`Mostrando detalles de la reserva en ${parkName}`);
}

// Función auxiliar para obtener cookies
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