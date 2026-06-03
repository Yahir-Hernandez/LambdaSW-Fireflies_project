/* luciernagas.js
   Script separado referenciado desde {% block js %} en index.html
   Ruta Django asumida: static/js/luciernagas.js
*/

// ─── 1. Luciérnagas flotantes ───────────────────────────────────────────────
(function () {
  const container = document.querySelector('.hero__fireflies');
  if (!container) return;

  for (let i = 0; i < 55; i++) {
    const dot = document.createElement('span');
    dot.classList.add('ff');
    dot.style.left   = Math.random() * 100 + '%';
    dot.style.top    = Math.random() * 100 + '%';
    dot.style.animationDelay    = (Math.random() * 6)       + 's';
    dot.style.animationDuration = (2 + Math.random() * 4)   + 's';
    dot.style.setProperty('--dx', (Math.random() * 80 - 40) + 'px');
    dot.style.setProperty('--dy', (Math.random() * 80 - 40) + 'px');
    container.appendChild(dot);
  }
})();

// ─── 2. Nav: fondo sólido al hacer scroll ───────────────────────────────────
(function () {
  const nav = document.querySelector('.nav');
  if (!nav) return;

  const onScroll = () => {
    nav.classList.toggle('nav--scrolled', window.scrollY > 20);
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll(); // estado inicial
})();

// ─── 3. Fade-in con IntersectionObserver ────────────────────────────────────
(function () {
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('visible');
        obs.unobserve(e.target); // solo una vez
      }
    });
  }, { threshold: 0.12 });

  document
    .querySelectorAll('.why__card, .parque-card, .trust-item, .parques-highlight, .festival-card, .galeria')
    .forEach(el => obs.observe(el));
})();