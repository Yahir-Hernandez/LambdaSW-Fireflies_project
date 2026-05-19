/*
 * Verificación de correo electrónico tras el signup.
 *  - 5 celdas independientes con auto-focus al siguiente al escribir,
 *    backspace al anterior, soporte de paste y auto-submit al completar.
 *  - Cuenta regresiva de 2 minutos sobre el botón "Reenviar".
 *  - POST AJAX al endpoint de verificación.
 *  - En éxito: abre el popup verde y redirige a perfil tras un breve delay.
 */

(() => {
    const dlg = document.getElementById('verify-dialog');
    const successDlg = document.getElementById('verify-success-dialog');
    const form = document.getElementById('verify-form');
    const errorEl = document.getElementById('verify-error');
    const resendBtn = document.getElementById('verify-resend-btn');
    const cells = Array.from(document.querySelectorAll('.code-cell'));
    const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;

    if (!dlg || cells.length !== 5) return;
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');

    // Bloquear ESC: la página detrás está vacía y se ve fea.
    // 1) Interceptamos keydown en fase de captura para que llegue ANTES
    //    que cualquier handler interno del navegador sobre <dialog>.
    // 2) preventDefault del evento "cancel" como segunda barrera.
    // 3) Si por alguna razón el dialog se cierra, lo reabrimos.
    window.addEventListener(
        'keydown',
        (event) => {
            if (event.key === 'Escape' || event.keyCode === 27) {
                event.preventDefault();
                event.stopImmediatePropagation();
                event.stopPropagation();
            }
        },
        true,
    );
    dlg.addEventListener('cancel', (event) => event.preventDefault());
    dlg.addEventListener('close', () => {
        // Si se cierra sin que lo hayamos pedido (verify success o back btn
        // navegan antes de poder ver el close), lo reabrimos.
        if (!intentionalClose) {
            if (typeof dlg.showModal === 'function') dlg.showModal();
            else dlg.setAttribute('open', '');
        }
    });

    const backBtn = document.getElementById('verify-back-btn');
    backBtn?.addEventListener('click', () => {
        intentionalClose = true;
        window.location.href = verifyUrls.back;
    });

    let resendRemaining = Math.max(0, initialResendIn);
    let resendInterval = null;
    let submitting = false;
    let intentionalClose = false;

    const setError = (text) => {
        errorEl.textContent = text || '';
        if (text) cells.forEach((c) => c.classList.add('is-error'));
    };

    const clearError = () => {
        errorEl.textContent = '';
        cells.forEach((c) => c.classList.remove('is-error'));
    };

    const formatMMSS = (totalSeconds) => {
        const m = Math.floor(totalSeconds / 60);
        const s = String(totalSeconds % 60).padStart(2, '0');
        return `${m}:${s}`;
    };

    const renderResend = () => {
        if (resendRemaining <= 0) {
            if (resendInterval) {
                clearInterval(resendInterval);
                resendInterval = null;
            }
            resendBtn.disabled = false;
            resendBtn.textContent = 'Reenviar código';
            return;
        }
        resendBtn.disabled = true;
        resendBtn.innerHTML = `Reenviar en <span id="verify-resend-timer">${formatMMSS(resendRemaining)}</span>`;
    };

    const startResendCountdown = (seconds) => {
        resendRemaining = Math.max(0, seconds);
        renderResend();
        if (resendInterval) clearInterval(resendInterval);
        if (resendRemaining > 0) {
            resendInterval = setInterval(() => {
                resendRemaining -= 1;
                renderResend();
            }, 1000);
        }
    };
    startResendCountdown(resendRemaining);

    const getCode = () => cells.map((c) => c.value).join('');

    const setCells = (digits) => {
        cells.forEach((cell, i) => {
            cell.value = digits[i] || '';
            cell.classList.toggle('is-filled', !!digits[i]);
        });
    };

    const focusCell = (i) => {
        const idx = Math.max(0, Math.min(cells.length - 1, i));
        cells[idx].focus();
        cells[idx].select?.();
    };

    const clearCells = (focusFirst = true) => {
        cells.forEach((c) => {
            c.value = '';
            c.classList.remove('is-filled');
        });
        if (focusFirst) focusCell(0);
    };

    const verifyCode = async () => {
        const code = getCode();
        if (code.length !== 5 || submitting) return;
        submitting = true;
        clearError();

        const fd = new FormData();
        fd.append('code', code);
        try {
            const res = await fetch(verifyUrls.verify, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: fd,
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) {
                intentionalClose = true;
                dlg.close();
                if (typeof successDlg.showModal === 'function') successDlg.showModal();
                else successDlg.setAttribute('open', '');
                setTimeout(() => {
                    window.location.href = verifyUrls.profile;
                }, 1500);
                return;
            }
            setError(data.error || 'Código incorrecto.');
            clearCells();
        } catch (_err) {
            setError('Error de red. Intenta de nuevo.');
        } finally {
            submitting = false;
        }
    };

    cells.forEach((cell, idx) => {
        cell.addEventListener('input', (event) => {
            const digit = (event.target.value || '').replace(/\D/g, '').slice(-1);
            event.target.value = digit;
            cell.classList.toggle('is-filled', !!digit);
            if (errorEl.textContent) clearError();

            if (digit) {
                if (idx < cells.length - 1) focusCell(idx + 1);
                if (getCode().length === 5) verifyCode();
            }
        });

        cell.addEventListener('keydown', (event) => {
            if (event.key === 'Backspace' && !cell.value && idx > 0) {
                event.preventDefault();
                cells[idx - 1].value = '';
                cells[idx - 1].classList.remove('is-filled');
                focusCell(idx - 1);
            } else if (event.key === 'ArrowLeft' && idx > 0) {
                event.preventDefault();
                focusCell(idx - 1);
            } else if (event.key === 'ArrowRight' && idx < cells.length - 1) {
                event.preventDefault();
                focusCell(idx + 1);
            }
        });

        cell.addEventListener('paste', (event) => {
            event.preventDefault();
            const pasted = (event.clipboardData?.getData('text') || '')
                .replace(/\D/g, '')
                .slice(0, 5);
            if (!pasted) return;
            setCells(pasted);
            focusCell(pasted.length - 1);
            if (pasted.length === 5) verifyCode();
        });

        cell.addEventListener('focus', () => cell.select?.());
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const code = getCode();
        if (code.length !== 5) {
            setError('Ingresa los 5 dígitos del código.');
            focusCell(code.length);
            return;
        }
        verifyCode();
    });

    resendBtn.addEventListener('click', async () => {
        clearError();
        try {
            const res = await fetch(verifyUrls.resend, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) {
                clearCells();
                startResendCountdown(120);
                return;
            }
            setError(data.error || 'No se pudo reenviar el código.');
            if (typeof data.retry_in === 'number') startResendCountdown(data.retry_in);
        } catch (_err) {
            setError('Error de red. Intenta de nuevo.');
        }
    });
})();
