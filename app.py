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


def is_valid_instagram_url(url: str) -> bool:
    if not url:
        return False
    return bool(INSTAGRAM_URL_REGEX.match(url.strip()))


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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def get_video_info():
    cleanup_old_files()
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Por favor ingresa un enlace de Instagram."}), 400

    if not is_valid_instagram_url(url):
        return (
            jsonify(
                {
                    "error": "El enlace no parece ser un Reel o publicación válida de Instagram (ej. https://www.instagram.com/reel/...)."
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

            # Buscar mejor formato MP4 con video y audio combinados, o extraer la URL directa
            formats = entry.get("formats") or []
            best_url = entry.get("url")
            width = entry.get("width")
            height = entry.get("height")

            # Filtrar formatos que tengan video y audio en mp4 si están disponibles
            combined_formats = [
                f
                for f in formats
                if f.get("vcodec") != "none"
                and f.get("acodec") != "none"
                and f.get("url")
            ]
            if combined_formats:
                # Ordenar por altura/calidad
                combined_formats.sort(
                    key=lambda f: (f.get("height") or 0, f.get("tbr") or 0),
                    reverse=True,
                )
                chosen = combined_formats[0]
                best_url = chosen.get("url")
                width = chosen.get("width") or width
                height = chosen.get("height") or height

            title = (
                entry.get("title")
                or info.get("title")
                or f"Instagram Video {idx + 1}"
            )
            description = entry.get("description") or info.get("description") or ""
            uploader = (
                entry.get("uploader")
                or entry.get("channel")
                or info.get("uploader")
                or "Usuario de Instagram"
            )
            thumbnail = entry.get("thumbnail") or info.get("thumbnail")
            duration = format_duration(entry.get("duration") or info.get("duration"))
            shortcode = entry.get("id") or info.get("id") or "video"

            videos.append(
                {
                    "id": shortcode,
                    "index": idx + 1,
                    "title": title,
                    "description": description[:280]
                    + ("..." if len(description) > 280 else ""),
                    "uploader": uploader,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "resolution": f"{width}x{height}" if width and height else "HD",
                    "direct_url": best_url,
                    "original_url": url,
                }
            )

        if not videos:
            return (
                jsonify(
                    {
                        "error": "No se encontraron videos en esta publicación. Asegúrate de que sea una publicación pública con video."
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
                        "error": "Esta publicación es privada o Instagram solicita inicio de sesión para verla."
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
    """Descarga el video usando yt-dlp y lo envía como archivo adjunto MP4 al navegador."""
    url = (request.args.get("url") or "").strip()
    item_index = request.args.get("index", "1")

    if not is_valid_instagram_url(url):
        return jsonify({"error": "Enlace inválido."}), 400

    unique_id = uuid.uuid4().hex[:10]
    output_template = str(DOWNLOAD_DIR / f"ig_{unique_id}_%(id)s.%(ext)s")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "outtmpl": output_template,
        "format": "best[ext=mp4]/best",
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
            # Buscar por prefijo si la extensión cambió
            matches = list(DOWNLOAD_DIR.glob(f"ig_{unique_id}_*"))
            if not matches:
                return jsonify({"error": "No se pudo generar el archivo de video."}), 500
            downloaded_path = matches[0]

        shortcode = entry.get("id") or unique_id
        download_name = f"instagram_{shortcode}.mp4"

        @after_this_request
        def remove_file(response):
            def delayed_delete(path: Path):
                time.sleep(5)
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
            as_attachment=True,
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
    """Proxy para miniaturas de Instagram para evitar bloqueos CORS/Cross-Origin en el navegador."""
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
    print("====================================================")
    print("  InstaFetch - Descargador de Videos de Instagram")
    print("  Servidor activo en: http://127.0.0.1:5000")
    print("====================================================")
    app.run(host="127.0.0.1", port=5000, debug=False)
