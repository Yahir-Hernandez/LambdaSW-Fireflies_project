/*
 * Verificación de correo electrónico tras el signup.
 *  - Cuenta regresiva de 2 minutos sobre el botón "Reenviar".
 *  - POST AJAX al endpoint de verificación; muestra error inline si falla.
 *  - En éxito: cierra el popup, abre el de "Verificación exitosa" y
 *    redirige a la página de perfil tras un breve delay.
 */

(() => {
    const dlg = document.getElementById('verify-dialog');
    const successDlg = document.getElementById('verify-success-dialog');
    const form = document.getElementById('verify-form');
    const codeInput = document.getElementById('verify-code');
    const errorEl = document.getElementById('verify-error');
    const resendBtn = document.getElementById('verify-resend-btn');
    const resendTimerEl = document.getElementById('verify-resend-timer');
    const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;

    if (!dlg) return;
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');

    let resendRemaining = Math.max(0, initialResendIn);
    let resendInterval = null;

    const setError = (text) => {
        errorEl.textContent = text || '';
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

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        setError('');
        const code = (codeInput.value || '').trim();
        if (!/^\d{5}$/.test(code)) {
            setError('Ingresa un código de 5 dígitos.');
            return;
        }
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
                dlg.close();
                if (typeof successDlg.showModal === 'function') successDlg.showModal();
                else successDlg.setAttribute('open', '');
                setTimeout(() => {
                    window.location.href = verifyUrls.profile;
                }, 1500);
                return;
            }
            setError(data.error || 'No se pudo verificar el código.');
        } catch (_err) {
            setError('Error de red. Intenta de nuevo.');
        }
    });

    resendBtn.addEventListener('click', async () => {
        setError('');
        try {
            const res = await fetch(verifyUrls.resend, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) {
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
