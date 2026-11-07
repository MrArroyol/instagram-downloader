# InstaFetch — Descargador de Videos de Instagram y TikTok

Aplicación web local desarrollada con **Python (Flask)** y **`yt-dlp`** para previsualizar y descargar Reels, publicaciones de Instagram y videos de TikTok en máxima calidad (MP4 HD) sin marcas de agua.

## Características

- **Soporte Multiplataforma (Instagram y TikTok):**
  - **Instagram:** Reels (`/reel/`, `/reels/`), publicaciones (`/p/`), IGTV (`/tv/`) y carruseles.
  - **TikTok:** Enlaces estándar (`tiktok.com/@usuario/video/...`) y enlaces cortos móviles (`vm.tiktok.com/...`, `vt.tiktok.com/...`).
- **Sin marca de agua en HD:** Prioriza automáticamente los flujos de video originales sin marca de agua.
- **Previsualización integrada:** Reproductor de video y miniatura antes de descargar.
- **Privado y local:** Funciona directamente en tu navegador local (`http://127.0.0.1:5000`) sin anuncios ni rastreadores.

## Requisitos

- Python 3.10+
- Dependencias en `requirements.txt`:
  ```bash
  py -m pip install -r requirements.txt
  ```

## Uso rápido

1. Haz doble clic en el acceso directo **InstaFetch** en tu Escritorio (o en `iniciar_instafetch.bat`).
2. Se abrirá `http://127.0.0.1:5000` en tu navegador.
3. Pega el enlace de Instagram o TikTok y haz clic en **Obtener Video**.
