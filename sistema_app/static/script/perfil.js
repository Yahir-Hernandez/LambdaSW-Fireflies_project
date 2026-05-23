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
    
    // Verificar si hay notificaciones pendientes
    checkNotifications();
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

// Cambiar foto de perfil
function changeProfilePhoto() {
    // Crear input de archivo
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.style.display = 'none';
    
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            // Validar tipo de archivo
            if (!file.type.match('image.*')) {
                alert('Por favor, selecciona una imagen válida.');
                return;
            }
            
            // Validar tamaño (max 5MB)
            if (file.size > 5 * 1024 * 1024) {
                alert('La imagen es demasiado grande. Máximo 5MB.');
                return;
            }
            
            // Mostrar preview
            const reader = new FileReader();
            reader.onload = function(e) {
                const avatarPlaceholder = document.querySelector('.avatar-placeholder');
                if (avatarPlaceholder) {
                    // Reemplazar icono con imagen
                    avatarPlaceholder.innerHTML = `<img src="${e.target.result}" alt="Foto de perfil" class="avatar-image">`;
                    
                    // Agregar estilos para la imagen
                    const style = document.createElement('style');
                    style.textContent = `
                        .avatar-image {
                            width: 100%;
                            height: 100%;
                            border-radius: 50%;
                            object-fit: cover;
                        }
                    `;
                    document.head.appendChild(style);
                    
                    // Aquí podrías enviar la imagen al servidor
                    // uploadProfilePhoto(file);
                    
                    showNotification('Foto de perfil actualizada exitosamente');
                }
            };
            reader.readAsDataURL(file);
        }
    });
    
    // Disparar el input de archivo
    document.body.appendChild(fileInput);
    fileInput.click();
    document.body.removeChild(fileInput);
}

// Editar perfil
function editProfile() {
    // Aquí podrías abrir un modal o redirigir a una página de edición
    console.log('Abriendo editor de perfil para:', user.username);
    
    // Ejemplo: mostrar un modal de edición
    showEditModal();
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

// Ver entrada de reserva
function viewReservationTicket(reservationCard) {
    const parkName = reservationCard.querySelector('.reservation-park').textContent;
    
    console.log('Viendo entrada de reserva para:', parkName);
    
    // Aquí podrías generar o mostrar la entrada
    // Por ejemplo, abrir un PDF o mostrar un código QR
    
    showNotification(`Generando entrada para ${parkName}`);
    
    // Simular generación de entrada
    setTimeout(() => {
        alert(`🎟️ ENTRADA PARA: ${parkName}\n📅 Fecha: ${new Date().toLocaleDateString('es-MX')}\n👤 Usuario: ${user.username}\n✅ Esta entrada es válida para el acceso al parque.`);
    }, 1000);
}

// Abrir configuración
function openSetting(settingType) {
    console.log('Abriendo configuración:', settingType);
    
    // Aquí podrías redirigir a diferentes páginas de configuración
    // o mostrar modales específicos
    
    switch(settingType.toLowerCase()) {
        case 'seguridad':
            showSecuritySettings();
            break;
        case 'notificaciones':
            showNotificationSettings();
            break;
        case 'preferencias':
            showPreferencesSettings();
            break;
        default:
            showNotification(`Configuración de ${settingType} abierta`);
    }
}

// Mostrar modal de edición (ejemplo)
function showEditModal() {
    // Crear modal
    const modal = document.createElement('div');
    modal.className = 'profile-modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>Editar Perfil</h3>
                <button class="modal-close"><i class="fa-solid fa-times"></i></button>
            </div>
            <div class="modal-body">
                <form id="editProfileForm">
                    <div class="form-group">
                        <label for="editFirstName">Nombre</label>
                        <input type="text" id="editFirstName" value="${user.first_name || ''}" placeholder="Tu nombre">
                    </div>
                    <div class="form-group">
                        <label for="editLastName">Apellido</label>
                        <input type="text" id="editLastName" value="${user.last_name || ''}" placeholder="Tu apellido">
                    </div>
                    <div class="form-group">
                        <label for="editEmail">Correo electrónico</label>
                        <input type="email" id="editEmail" value="${user.email || ''}" placeholder="tu@email.com">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn btn--outline modal-close">Cancelar</button>
                        <button type="submit" class="btn btn--primary">Guardar cambios</button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    // Agregar al DOM
    document.body.appendChild(modal);
    
    // Agregar estilos
    const style = document.createElement('style');
    style.textContent = `
        .profile-modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(8, 14, 16, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            animation: fadeIn 0.3s ease;
        }
        
        .modal-content {
            background: var(--bg-card);
            border-radius: 12px;
            width: 90%;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
            animation: slideUp 0.3s ease;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            border-bottom: 1px solid var(--border);
        }
        
        .modal-header h3 {
            margin: 0;
            color: var(--text);
            font-size: 1.3rem;
        }
        
        .modal-close {
            background: none;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            font-size: 1.2rem;
            padding: 4px;
            border-radius: 4px;
            transition: background 0.2s;
        }
        
        .modal-close:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        .modal-body {
            padding: 20px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: var(--text);
            font-size: 0.9rem;
            font-weight: 500;
        }
        
        .form-group input {
            width: 100%;
            padding: 10px 12px;
            background: var(--bg-section);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-size: 0.95rem;
            transition: border-color 0.2s;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: var(--accent);
        }
        
        .form-actions {
            display: flex;
            gap: 12px;
            margin-top: 30px;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);
    
    // Event listeners para el modal
    const closeBtns = modal.querySelectorAll('.modal-close');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            modal.style.opacity = '0';
            setTimeout(() => {
                modal.remove();
                style.remove();
            }, 300);
        });
    });
    
    // Form submit
    const form = modal.querySelector('#editProfileForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Aquí podrías enviar los datos al servidor
            const formData = {
                first_name: document.getElementById('editFirstName').value,
                last_name: document.getElementById('editLastName').value,
                email: document.getElementById('editEmail').value
            };
            
            console.log('Datos del perfil a actualizar:', formData);
            
            // Simular actualización
            showNotification('Perfil actualizado exitosamente');
            
            // Cerrar modal
            modal.style.opacity = '0';
            setTimeout(() => {
                modal.remove();
                style.remove();
            }, 300);
        });
    }
}

// Funciones de ejemplo para configuraciones
function showSecuritySettings() {
    alert('Configuración de seguridad:\n\n• Cambiar contraseña\n• Autenticación de dos factores\n• Sesiones activas');
}

function showNotificationSettings() {
    alert('Configuración de notificaciones:\n\n• Correos electrónicos\n• Notificaciones push\n• Recordatorios de reservas');
}

function showPreferencesSettings() {
    alert('Preferencias:\n\n• Idioma\n• Zona horaria\n• Tema (claro/oscuro)');
}

// Función para subir foto de perfil (ejemplo)
function uploadProfilePhoto(file) {
    // Aquí iría la lógica para subir la foto al servidor
    // usando AJAX o Fetch API
    
    const formData = new FormData();
    formData.append('profile_photo', file);
    
    // Ejemplo con Fetch API
    fetch('/api/upload-profile-photo/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Foto de perfil actualizada exitosamente');
        } else {
            showNotification('Error al actualizar la foto: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error al subir la foto');
    });
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