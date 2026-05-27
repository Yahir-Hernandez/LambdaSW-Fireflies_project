/*
 * Scanner JS del check-in dentro del admin de Django.
 * - Inicia la cámara con html5-qrcode.
 * - Al detectar un QR válido, extrae el UUID y carga los datos vía AJAX.
 * - El botón "Confirmar entrada" hace POST sin recargar.
 * - "Escanear otro" reanuda la cámara y limpia la vista.
 */
(() => {
    const detailsEl = document.getElementById("qr-details");
    const messageEl = document.getElementById("qr-message");
    const csrfInput = document.querySelector("input[name=csrfmiddlewaretoken]");
    const csrfToken = csrfInput ? csrfInput.value : "";

    if (typeof Html5Qrcode === "undefined") {
        showMessage("No se pudo cargar la librería del scanner.", "error");
        return;
    }

    const html5QrCode = new Html5Qrcode("qr-scanner");
    const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
    let scannerActive = false;

    function showMessage(text, type = "") {
        messageEl.textContent = text || "";
        messageEl.className = type ? `qr-message qr-message--${type}` : "qr-message";
    }

    function extractToken(text) {
        const match = (text || "").match(UUID_RE);
        return match ? match[0] : null;
    }

    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, (c) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        })[c]);
    }

    async function startScanner() {
        try {
            await html5QrCode.start(
                { facingMode: "environment" },
                { fps: 10, qrbox: 250 },
                onScanSuccess,
                () => { /* lectura fallida entre frames es normal */ },
            );
            scannerActive = true;
            showMessage("Apunta la cámara hacia el QR.", "info");
        } catch (err) {
            showMessage(
                "No se pudo iniciar la cámara. Verifica permisos del navegador. (" + err + ")",
                "error",
            );
        }
    }

    async function pauseScanner() {
        if (scannerActive) {
            try { await html5QrCode.pause(true); } catch (_) { /* noop */ }
        }
    }

    async function resumeScanner() {
        detailsEl.innerHTML = "";
        showMessage("Apunta la cámara hacia el QR.", "info");
        if (scannerActive) {
            try { await html5QrCode.resume(); } catch (_) { /* noop */ }
        } else {
            await startScanner();
        }
    }

    async function onScanSuccess(decodedText) {
        const token = extractToken(decodedText);
        if (!token) {
            showMessage("QR no reconocido — no contiene un token válido.", "error");
            return;
        }
        await pauseScanner();
        await loadReservation(token);
    }

    async function loadReservation(token) {
        showMessage("Cargando datos de la reserva...", "info");

        const url = window.QR_CHECKIN_URLS.data.replace("__TOKEN__", token);
        let res;
        try {
            res = await fetch(url, {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            });
        } catch (err) {
            console.error("Network error fetching reservation:", err);
            showMessage(`Sin conexión al servidor: ${err.message}`, "error");
            renderResumeOnly();
            return;
        }

        const text = await res.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch {
            // Cuando la respuesta no es JSON, lo más común es:
            //  - HTTP 302 con HTML de login (sesión admin expiró).
            //  - HTTP 404/500 con HTML de Django (UUID inexistente, DEBUG=True).
            console.error(`HTTP ${res.status} non-JSON response:`, text.slice(0, 500));
            showMessage(
                `Respuesta inesperada del servidor (HTTP ${res.status}). Abre DevTools (F12) → Console para ver detalles.`,
                "error",
            );
            renderResumeOnly();
            return;
        }

        if (!res.ok) {
            showMessage(data.error || `HTTP ${res.status}`, "error");
            renderResumeOnly();
            return;
        }
        showMessage("");
        renderDetails(data, token);
    }

    function renderDetails(data, token) {
        const confirmBtn = data.can_check_in
            ? `<button type="button" id="confirm-btn" class="button button--primary">Confirmar entrada</button>`
            : `<p><strong>Esta reserva no se puede checar</strong> (estado: ${escapeHtml(data.status_display)}).</p>`;

        detailsEl.innerHTML = `
            <h2>Reservación #${escapeHtml(data.id)}</h2>
            <ul>
                <li><strong>Cliente:</strong> ${escapeHtml(data.user_name)} (${escapeHtml(data.user_email)})</li>
                <li><strong>Parque:</strong> ${escapeHtml(data.park)}</li>
                <li><strong>Hospedaje:</strong> ${escapeHtml(data.lodging)}</li>
                <li><strong>Fechas:</strong> ${escapeHtml(data.start_date)} → ${escapeHtml(data.end_date)}</li>
                <li><strong>Personas:</strong> ${escapeHtml(data.people)}</li>
                <li><strong>Estado:</strong> ${escapeHtml(data.status_display)}</li>
            </ul>
            ${confirmBtn}
            <div class="qr-actions">
                <button type="button" id="resume-btn" class="button button--secondary">Escanear otro</button>
            </div>
        `;
        const confirm = document.getElementById("confirm-btn");
        if (confirm) confirm.addEventListener("click", () => confirmCheckin(token));
        document.getElementById("resume-btn").addEventListener("click", resumeScanner);
    }

    function renderResumeOnly() {
        detailsEl.innerHTML = `
            <div class="qr-actions">
                <button type="button" id="resume-btn" class="button button--secondary">Escanear otro</button>
            </div>
        `;
        document.getElementById("resume-btn").addEventListener("click", resumeScanner);
    }

    async function confirmCheckin(token) {
        const btn = document.getElementById("confirm-btn");
        if (btn) {
            btn.disabled = true;
            btn.textContent = "Confirmando...";
        }

        function restoreBtn() {
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Confirmar entrada";
            }
        }

        const url = window.QR_CHECKIN_URLS.confirm.replace("__TOKEN__", token);
        let res;
        try {
            res = await fetch(url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    Accept: "application/json",
                },
                credentials: "same-origin",
            });
        } catch (err) {
            console.error("Network error confirming check-in:", err);
            showMessage(`Sin conexión al servidor: ${err.message}`, "error");
            restoreBtn();
            return;
        }

        const text = await res.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch {
            console.error(`HTTP ${res.status} non-JSON response on confirm:`, text.slice(0, 500));
            showMessage(
                `Respuesta inesperada del servidor (HTTP ${res.status}). Abre DevTools (F12) → Console para ver detalles.`,
                "error",
            );
            restoreBtn();
            return;
        }

        if (res.ok && data.ok) {
            showMessage("Entrada confirmada. La reserva quedó marcada como usada.", "success");
            if (btn) btn.remove();
        } else {
            showMessage(data.error || `HTTP ${res.status}`, "error");
            restoreBtn();
        }
    }

    // Input manual de UUID — fallback cuando la cámara no funciona o el QR
    // no es escaneable (resolución baja, falta HTTPS en móvil, etc).
    const manualBtn = document.getElementById("manual-token-btn");
    const manualInput = document.getElementById("manual-token-input");
    if (manualBtn && manualInput) {
        manualBtn.addEventListener("click", async () => {
            const token = extractToken(manualInput.value.trim());
            if (!token) {
                showMessage("UUID inválido. Formato esperado: 8-4-4-4-12 chars hex.", "error");
                return;
            }
            await pauseScanner();
            await loadReservation(token);
        });
        manualInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                manualBtn.click();
            }
        });
    }

    startScanner();
})();
