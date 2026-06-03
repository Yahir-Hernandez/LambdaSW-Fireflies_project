(() => {
  const track = document.getElementById('galeria-track');
  const prevBtn = document.getElementById('galeria-prev');
  const nextBtn = document.getElementById('galeria-next');
  const lightbox = document.getElementById('galeria-lightbox');
  const lightboxImg = document.getElementById('galeria-lightbox-img');
  const closeBtn = document.getElementById('galeria-lightbox-close');
  if (!track || !prevBtn || !nextBtn || !lightbox) return;

  const step = () => {
    const item = track.querySelector('.galeria__item');
    if (!item) return 378;
    return item.offsetWidth + parseInt(getComputedStyle(track).gap || '18', 10);
  };

  let offset = 0;

  function maxOffset() {
    return Math.max(0, track.scrollWidth - track.parentElement.offsetWidth);
  }

  function applyOffset() {
    track.style.transform = `translateX(-${offset}px)`;
  }

  nextBtn.addEventListener('click', () => {
    const next = offset + step();
    offset = next > maxOffset() ? 0 : next;
    applyOffset();
  });

  prevBtn.addEventListener('click', () => {
    const prev = offset - step();
    offset = prev < 0 ? maxOffset() : prev;
    applyOffset();
  });

  window.addEventListener('resize', () => {
    offset = Math.min(offset, maxOffset());
    applyOffset();
  });

  applyOffset();

  // Lightbox
  track.querySelectorAll('.galeria__item').forEach(item => {
    item.addEventListener('click', () => {
      lightboxImg.src = item.dataset.src;
      lightboxImg.alt = item.dataset.alt || '';
      lightbox.showModal();
    });
  });

  closeBtn?.addEventListener('click', () => lightbox.close());
  lightbox.addEventListener('click', e => {
    if (e.target === lightbox) lightbox.close();
  });
})();
