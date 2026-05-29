/*
 * Verificación de código para restablecimiento de contraseña.
 *  - 6 celdas con auto-focus, backspace, paste y auto-submit.
 *  - Cuenta regresiva de 2 minutos para reenviar.
 *  - En éxito redirige a la página de nueva contraseña.
 */

(() => {
    const dlg        = document.getElementById('reset-verify-dialog');
    const successDlg = document.getElementById('reset-success-dialog');
    const form       = document.getElementById('reset-verify-form');
    const errorEl    = document.getElementById('reset-verify-error');
    const resendBtn  = document.getElementById('reset-resend-btn');
    const cells      = Array.from(document.querySelectorAll('.code-cell'));
    const csrfToken  = form.querySelector('input[name="csrfmiddlewaretoken"]').value;

    if (!dlg || cells.length !== 6) return;
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
    dlg.addEventListener('cancel', (e) => e.preventDefault());

    let intentionalClose = false;
    dlg.addEventListener('close', () => {
        if (!intentionalClose) {
            if (typeof dlg.showModal === 'function') dlg.showModal();
            else dlg.setAttribute('open', '');
        }
    });

    let resendRemaining = Math.max(0, resetInitialResendIn);
    let resendInterval  = null;
    let submitting      = false;

    const setError = (text) => {
        errorEl.textContent = text || '';
        if (text) cells.forEach((c) => c.classList.add('is-error'));
    };
    const clearError = () => {
        errorEl.textContent = '';
        cells.forEach((c) => c.classList.remove('is-error'));
    };

    const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

    const renderResend = () => {
        if (resendRemaining <= 0) {
            if (resendInterval) { clearInterval(resendInterval); resendInterval = null; }
            resendBtn.disabled = false;
            resendBtn.textContent = 'Reenviar código';
        } else {
            resendBtn.disabled = true;
            resendBtn.innerHTML = `Reenviar en <span id="reset-resend-timer">${fmt(resendRemaining)}</span>`;
        }
    };
    const startCountdown = (s) => {
        resendRemaining = Math.max(0, s);
        renderResend();
        if (resendInterval) clearInterval(resendInterval);
        if (resendRemaining > 0) {
            resendInterval = setInterval(() => { resendRemaining -= 1; renderResend(); }, 1000);
        }
    };
    startCountdown(resendRemaining);

    const getCode    = () => cells.map((c) => c.value).join('');
    const focusCell  = (i) => { const idx = Math.max(0, Math.min(5, i)); cells[idx].focus(); cells[idx].select?.(); };
    const clearCells = (focusFirst = true) => {
        cells.forEach((c) => { c.value = ''; c.classList.remove('is-filled'); });
        if (focusFirst) focusCell(0);
    };
    const setCells = (digits) => {
        cells.forEach((cell, i) => {
            cell.value = digits[i] || '';
            cell.classList.toggle('is-filled', !!digits[i]);
        });
    };

    const verifyCode = async () => {
        const code = getCode();
        if (code.length !== 6 || submitting) return;
        submitting = true;
        clearError();
        try {
            const res  = await fetch(resetUrls.verify, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
                body: JSON.stringify({ code }),
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) {
                intentionalClose = true;
                dlg.close();
                if (typeof successDlg.showModal === 'function') successDlg.showModal();
                else successDlg.setAttribute('open', '');
                setTimeout(() => { window.location.href = resetUrls.next; }, 1400);
                return;
            }
            setError(data.error || 'Código incorrecto.');
            clearCells();
        } catch (_) {
            setError('Error de red. Intenta de nuevo.');
        } finally {
            submitting = false;
        }
    };

    cells.forEach((cell, idx) => {
        cell.addEventListener('input', (e) => {
            const digit = (e.target.value || '').replace(/\D/g, '').slice(-1);
            e.target.value = digit;
            cell.classList.toggle('is-filled', !!digit);
            if (errorEl.textContent) clearError();
            if (digit) {
                if (idx < 5) focusCell(idx + 1);
                if (getCode().length === 6) verifyCode();
            }
        });
        cell.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !cell.value && idx > 0) {
                e.preventDefault();
                cells[idx - 1].value = '';
                cells[idx - 1].classList.remove('is-filled');
                focusCell(idx - 1);
            } else if (e.key === 'ArrowLeft'  && idx > 0) { e.preventDefault(); focusCell(idx - 1); }
              else if (e.key === 'ArrowRight' && idx < 5) { e.preventDefault(); focusCell(idx + 1); }
        });
        cell.addEventListener('paste', (e) => {
            e.preventDefault();
            const pasted = (e.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 6);
            if (!pasted) return;
            setCells(pasted);
            focusCell(pasted.length - 1);
            if (pasted.length === 6) verifyCode();
        });
        cell.addEventListener('focus', () => cell.select?.());
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const code = getCode();
        if (code.length !== 6) { setError('Ingresa los 6 dígitos del código.'); focusCell(code.length); return; }
        verifyCode();
    });

    resendBtn.addEventListener('click', async () => {
        clearError();
        try {
            const res  = await fetch(resetUrls.resend, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) { clearCells(); startCountdown(data.resend_in ?? 120); return; }
            setError(data.error || 'No se pudo reenviar el código.');
        } catch (_) {
            setError('Error de red. Intenta de nuevo.');
        }
    });
})();
