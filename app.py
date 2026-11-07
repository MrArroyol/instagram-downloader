import os
import re
import uuid
import shutil
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    after_this_request,
    Response,
)
import requests
import yt_dlp

app = Flask(__name__)

# Directorio temporal para descargas procesadas en servidor
DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "instadownloader_temp"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

INSTAGRAM_URL_REGEX = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv|stories)/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)

TIKTOK_URL_REGEX = re.compile(
    r"^https?://(?:(?:www|vm|vt|m|t)\.)?tiktok\.com/.+",
    re.IGNORECASE,
)


def detect_platform(url: str) -> str | None:
    """Devuelve 'instagram', 'tiktok' o None si la URL no corresponde a ninguna soportada."""
    if not url:
        return None
    clean_url = url.strip()
    if INSTAGRAM_URL_REGEX.match(clean_url):
        return "instagram"
    if TIKTOK_URL_REGEX.match(clean_url):
        return "tiktok"
    return None


def is_valid_supported_url(url: str) -> bool:
    return detect_platform(url) is not None


def cleanup_old_files(max_age_seconds: int = 1800):
    """Limpia archivos temporales antiguos (por defecto > 30 mins)."""
    now = time.time()
    try:
        for item in DOWNLOAD_DIR.iterdir():
            if item.is_file() and (now - item.stat().st_mtime) > max_age_seconds:
                try:
                    item.unlink()
                except OSError:
                    pass
    except Exception:
        pass


def format_duration(seconds):
    if not seconds:
        return None
    seconds = int(round(seconds))
    mins, secs = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def extract_clean_username(entry: dict, info: dict, url: str = "") -> str:
    """Extrae el nombre de usuario (handle) del creador y lo limpia para usarlo en nombres de archivo."""
    candidates = [
        entry.get("uploader_id"),
        entry.get("channel"),
        entry.get("uploader"),
        entry.get("creator"),
        info.get("uploader_id"),
        info.get("channel"),
        info.get("uploader"),
        info.get("creator"),
    ]
    # Intentar extraer handle de URL de TikTok si viene como @usuario
    if url:
        m = re.search(r"tiktok\.com/@([A-Za-z0-9_.-]+)", url, re.IGNORECASE)
        if m:
            candidates.insert(0, m.group(1))

    for c in candidates:
        if c and isinstance(c, str):
            cleaned = c.strip().lstrip("@")
            # Limpiar caracteres inválidos en nombres de archivo de Windows
            cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", cleaned)
            cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
            if cleaned and cleaned.lower() not in ("none", "unknown", "usuario_de_instagram", "usuario_de_tiktok"):
                return cleaned[:50]
    return "usuario"


def pick_best_no_watermark_format(formats: list) -> dict | None:
    """Selecciona el mejor formato MP4 con video y audio combinados evitando marcas de agua."""
    combined_formats = [
        f
        for f in (formats or [])
        if f.get("vcodec") != "none"
        and f.get("acodec") != "none"
        and f.get("url")
    ]
    if not combined_formats:
        return None

    def format_priority(f):
        fmt_id = str(f.get("format_id") or "").lower()
        fmt_note = str(f.get("format_note") or "").lower()
        has_wm = (
            "watermark" in fmt_id
            or "watermark" in fmt_note
            or fmt_id == "download"
            or "wm" in fmt_id.split("_")
        )
        no_wm = 0 if has_wm else 1
        is_h264 = 1 if str(f.get("vcodec") or "").startswith("avc") else 0
        return (
            no_wm,
            f.get("height") or 0,
            is_h264,
            f.get("tbr") or 0,
        )

    combined_formats.sort(key=format_priority, reverse=True)
    return combined_formats[0]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def get_video_info():
    cleanup_old_files()
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Por favor ingresa un enlace de Instagram o TikTok."}), 400

    platform = detect_platform(url)
    if not platform:
        return (
            jsonify(
                {
                    "error": "El enlace no es válido. Ingresa un enlace de Instagram (ej. instagram.com/reel/...) o TikTok (ej. tiktok.com/@usuario/video/... o vm.tiktok.com/...)."
                }
            ),
            400,
        )

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Manejar carruseles / playlists o post único
        entries = info.get("entries") if "entries" in info else [info]
        videos = []

        for idx, entry in enumerate(entries):
            if not entry:
                continue

            formats = entry.get("formats") or []
            best_url = entry.get("url")
            width = entry.get("width")
            height = entry.get("height")

            chosen = pick_best_no_watermark_format(formats)
            if chosen:
                best_url = chosen.get("url")
                width = chosen.get("width") or width
                height = chosen.get("height") or height

            platform_label = "TikTok" if platform == "tiktok" else "Instagram"
            title = (
                entry.get("title")
                or info.get("title")
                or f"{platform_label} Video {idx + 1}"
            )
            description = entry.get("description") or info.get("description") or ""
            username = extract_clean_username(entry, info, url)
            uploader = (
                username
                if username != "usuario"
                else (
                    entry.get("uploader")
                    or entry.get("creator")
                    or info.get("uploader")
                    or f"Usuario de {platform_label}"
                )
            )
            thumbnail = entry.get("thumbnail") or info.get("thumbnail")
            duration = format_duration(entry.get("duration") or info.get("duration"))
            shortcode = entry.get("id") or info.get("id") or "video"

            # En TikTok las URLs directas de CDN suelen requerir cookies/headers de sesión,
            # por lo que usamos nuestro endpoint de streaming/descarga para la vista previa segura
            preview_url = (
                f"/api/download?url={requests.utils.quote(url)}&index={idx + 1}&inline=1"
                if platform == "tiktok"
                else best_url
            )

            videos.append(
                {
                    "id": shortcode,
                    "index": idx + 1,
                    "platform": platform,
                    "platform_label": platform_label,
                    "title": title,
                    "description": description[:280]
                    + ("..." if len(description) > 280 else ""),
                    "uploader": uploader,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "resolution": f"{width}x{height}" if width and height else "HD",
                    "direct_url": preview_url,
                    "original_url": url,
                }
            )

        if not videos:
            return (
                jsonify(
                    {
                        "error": "No se encontraron videos en este enlace. Asegúrate de que sea una publicación pública con video."
                    }
                ),
                404,
            )

        return jsonify({"success": True, "videos": videos})

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "login required" in msg.lower() or "private" in msg.lower():
            return (
                jsonify(
                    {
                        "error": "Esta publicación es privada o la plataforma solicita inicio de sesión para verla."
                    }
                ),
                403,
            )
        return (
            jsonify(
                {
                    "error": "No se pudo obtener el video. Verifica que el enlace sea público y correcto.",
                    "details": msg,
                }
            ),
            400,
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "error": "Ocurrió un error inesperado al procesar el enlace.",
                    "details": str(e),
                }
            ),
            500,
        )


@app.route("/api/download", methods=["GET"])
def download_video():
    """Descarga el video de Instagram o TikTok usando yt-dlp y lo envía como MP4 al navegador."""
    url = (request.args.get("url") or "").strip()
    item_index = request.args.get("index", "1")
    inline = request.args.get("inline", "0") == "1"

    platform = detect_platform(url)
    if not platform:
        return jsonify({"error": "Enlace inválido."}), 400

    unique_id = uuid.uuid4().hex[:10]
    prefix = "tt" if platform == "tiktok" else "ig"
    output_template = str(DOWNLOAD_DIR / f"{prefix}_{unique_id}_%(id)s.%(ext)s")

    # Selector de formato que excluye explícitamente flujos con marca de agua ('download' o 'watermark')
    format_selector = (
        "best[ext=mp4][format_id!*=watermark][format_id!=download][format_note!*=watermark]/"
        "best[ext=mp4]/best"
    )

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": output_template,
        "format": format_selector,
        "playlist_items": str(item_index),
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if "entries" in info and info["entries"]:
                entry = info["entries"][0]
            else:
                entry = info
            downloaded_path = Path(ydl.prepare_filename(entry))

        if not downloaded_path.exists():
            matches = list(DOWNLOAD_DIR.glob(f"{prefix}_{unique_id}_*"))
            if not matches:
                return jsonify({"error": "No se pudo generar el archivo de video."}), 500
            downloaded_path = matches[0]

        shortcode = entry.get("id") or unique_id
        username = extract_clean_username(entry, info, url)
        download_name = f"{username}_{shortcode}.mp4"

        @after_this_request
        def remove_file(response):
            def delayed_delete(path: Path):
                time.sleep(15 if inline else 5)
                try:
                    if path.exists():
                        path.unlink()
                except OSError:
                    pass

            threading.Thread(
                target=delayed_delete, args=(downloaded_path,), daemon=True
            ).start()
            return response

        return send_file(
            downloaded_path,
            as_attachment=not inline,
            download_name=download_name,
            mimetype="video/mp4",
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "error": "Error al descargar el archivo de video.",
                    "details": str(e),
                }
            ),
            500,
        )


@app.route("/api/proxy-thumbnail")
def proxy_thumbnail():
    """Proxy para miniaturas de Instagram y TikTok para evitar bloqueos CORS/Cross-Origin en el navegador."""
    thumb_url = request.args.get("url", "")
    if not thumb_url:
        return "", 404
    parsed = urlparse(thumb_url)
    if not parsed.scheme.startswith("http"):
        return "", 400
    try:
        resp = requests.get(
            thumb_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0"
            },
            timeout=10,
        )
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "image/jpeg"),
        )
    except Exception:
        return "", 502


if __name__ == "__main__":
    print("============================================================")
    print("  InstaFetch - Descargador de Videos de Instagram y TikTok")
    print("  Servidor activo en: http://127.0.0.1:5000")
    print("============================================================")
    app.run(host="127.0.0.1", port=5000, debug=False)
