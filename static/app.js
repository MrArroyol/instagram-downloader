document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("search-form");
    const urlInput = document.getElementById("url-input");
    const pasteBtn = document.getElementById("paste-btn");
    const submitBtn = document.getElementById("submit-btn");
    const btnText = submitBtn.querySelector(".btn-text");
    const spinner = document.getElementById("loading-spinner");
    const statusAlert = document.getElementById("status-alert");
    const resultsSection = document.getElementById("results-section");
    const resultsGrid = document.getElementById("results-grid");

    function showAlert(message, type = "error") {
        statusAlert.textContent = message;
        statusAlert.className = `alert ${type}`;
    }

    function hideAlert() {
        statusAlert.className = "alert hidden";
        statusAlert.textContent = "";
    }

    function setLoading(isLoading) {
        submitBtn.disabled = isLoading;
        if (isLoading) {
            btnText.textContent = "Procesando...";
            spinner.classList.remove("hidden");
        } else {
            btnText.textContent = "Obtener Video";
            spinner.classList.add("hidden");
        }
    }

    pasteBtn.addEventListener("click", async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                urlInput.value = text.trim();
                urlInput.focus();
                hideAlert();
            }
        } catch (err) {
            showAlert("No se pudo acceder al portapapeles automáticamente. Presiona Ctrl+V en el campo.", "info");
        }
    });

    function createVideoCard(video) {
        const card = document.createElement("article");
        card.className = "video-card";

        const thumbProxyUrl = video.thumbnail
            ? `/api/proxy-thumbnail?url=${encodeURIComponent(video.thumbnail)}`
            : "";

        const downloadEndpoint = `/api/download?url=${encodeURIComponent(video.original_url)}&index=${encodeURIComponent(video.index)}`;

        const durationBadge = video.duration
            ? `<span class="media-tag">${video.duration}</span>`
            : "";

        const resolutionBadge = video.resolution
            ? `<span class="media-tag">${video.resolution}</span>`
            : "";

        let mediaContent = "";
        if (video.direct_url) {
            mediaContent = `
                <video controls preload="metadata" poster="${thumbProxyUrl}">
                    <source src="${video.direct_url}" type="video/mp4">
                </video>
            `;
        } else if (thumbProxyUrl) {
            mediaContent = `<img src="${thumbProxyUrl}" alt="Vista previa del video">`;
        }

        card.innerHTML = `
            <div class="video-media">
                ${mediaContent}
                <div class="media-badges">
                    ${resolutionBadge}
                    ${durationBadge}
                </div>
            </div>
            <div class="video-body">
                <div class="uploader-row">
                    <span>@${escapeHtml(video.uploader)}</span>
                    <span>ID: ${escapeHtml(video.id)}</span>
                </div>
                <p class="video-desc">${escapeHtml(video.description || video.title)}</p>
                <div class="download-actions">
                    <a href="${downloadEndpoint}" class="btn-download" download>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                        <span>Descargar MP4 (${escapeHtml(video.resolution || "HD")})</span>
                    </a>
                </div>
            </div>
        `;
        return card;
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (!url) return;

        hideAlert();
        resultsSection.classList.add("hidden");
        resultsGrid.innerHTML = "";
        setLoading(true);

        try {
            const response = await fetch("/api/info", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url }),
            });

            const data = await response.json();

            if (!response.ok || data.error) {
                showAlert(data.error || "No se pudo extraer la información del video.", "error");
                return;
            }

            if (data.videos && data.videos.length > 0) {
                data.videos.forEach((video) => {
                    resultsGrid.appendChild(createVideoCard(video));
                });
                resultsSection.classList.remove("hidden");
            } else {
                showAlert("No se encontraron videos en el enlace proporcionado.", "error");
            }
        } catch (err) {
            showAlert("Error de conexión con el servidor local. Asegúrate de que el backend esté en ejecución.", "error");
        } finally {
            setLoading(false);
        }
    });
});
