(function () {
  function getCookie(name) {
    let v = null;
    if (document.cookie) {
      document.cookie.split(';').forEach(function (c) {
        c = c.trim();
        if (c.startsWith(name + '=')) v = decodeURIComponent(c.slice(name.length + 1));
      });
    }
    return v;
  }

  const csrftoken = getCookie('csrftoken');
  const reviewDialog = document.getElementById('review-dialog');
  const successDialog = document.getElementById('review-success-dialog');
  const parkLabel = document.getElementById('review-dialog-park');
  const stars = document.querySelectorAll('.rating-star');
  const commentEl = document.getElementById('review-comment');
  const submitBtn = document.getElementById('review-dialog-submit');
  const cancelBtn = document.getElementById('review-dialog-cancel');
  const errorEl = document.getElementById('review-error');

  if (!reviewDialog) return;

  let currentReservaId = null;
  let selectedRating = 0;

  function setRating(value) {
    selectedRating = value;
    stars.forEach(function (btn) {
      const v = parseInt(btn.dataset.value);
      const icon = btn.querySelector('i');
      icon.className = v <= value ? 'fa-solid fa-star' : 'fa-regular fa-star';
    });
  }

  stars.forEach(function (btn) {
    btn.addEventListener('mouseenter', function () { setRating(parseInt(btn.dataset.value)); });
    btn.addEventListener('mouseleave', function () { setRating(selectedRating); });
    btn.addEventListener('click', function () { setRating(parseInt(btn.dataset.value)); });
    btn.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setRating(parseInt(btn.dataset.value));
      }
    });
  });

  function openDialog(reservaId, parkName) {
    currentReservaId = reservaId;
    selectedRating = 0;
    setRating(0);
    if (commentEl) commentEl.value = '';
    if (errorEl) { errorEl.hidden = true; errorEl.textContent = ''; }
    if (parkLabel) parkLabel.textContent = parkName;
    reviewDialog.showModal();
  }

  document.querySelectorAll('.js-review-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      openDialog(btn.dataset.reservaId, btn.dataset.reservaPark);
    });
  });

  if (cancelBtn) {
    cancelBtn.addEventListener('click', function () { reviewDialog.close(); });
  }

  if (submitBtn) {
    submitBtn.addEventListener('click', async function () {
      if (!selectedRating) {
        errorEl.textContent = 'Por favor selecciona una calificación.';
        errorEl.hidden = false;
        return;
      }
      submitBtn.disabled = true;
      const body = new FormData();
      body.append('rating', selectedRating);
      body.append('comment', commentEl ? commentEl.value : '');
      try {
        const res = await fetch('/reservaciones/' + currentReservaId + '/resena/', {
          method: 'POST',
          headers: { 'X-CSRFToken': csrftoken },
          body: body,
        });
        if (!res.ok) {
          const data = await res.json().catch(function () { return { error: 'Error del servidor.' }; });
          throw new Error(data.error || 'Error al enviar la reseña.');
        }
        reviewDialog.close();
        successDialog.showModal();
        setTimeout(function () { window.location.reload(); }, 1500);
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.hidden = false;
      } finally {
        submitBtn.disabled = false;
      }
    });
  }
})();
