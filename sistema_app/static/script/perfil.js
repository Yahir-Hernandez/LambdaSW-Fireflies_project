/*
 * Script para la pagina de perfil
 * @author Yahir
 * @version 1.0
 * @date 2026-12-14
 * Controla la interaccion en la pagina de perfil del usuario
 */

document.addEventListener('DOMContentLoaded', () => {
    const images = getForestImages();
    if (images.length) {
        setRandomReservationImages(images);
    }
});

function getForestImages() {
    const container = document.querySelector('.profile-container');
    if (!container) return [];

    const rawImages = container.dataset.forestImages || '';
    if (!rawImages) return [];

    return rawImages
        .split('|')
        .map((value) => value.trim())
        .filter(Boolean);
}

function setRandomReservationImages(images) {
    const cards = document.querySelectorAll('.reservation__img');
    if (!cards.length) return;

    cards.forEach((img) => {
        const idx = Math.floor(Math.random() * images.length);
        img.src = images[idx];
    });
}