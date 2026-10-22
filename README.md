# InstaFetch — Descargador de Videos y Reels de Instagram

Aplicación web local desarrollada con **Python (Flask)** y **`yt-dlp`** para previsualizar y descargar Reels, publicaciones con video y carruseles públicos de Instagram en máxima calidad (MP4 HD) sin marcas de agua.

## Características

- **Extracción directa en HD:** Obtiene el flujo de video original en formato MP4.
- **Soporte para Reels y Carruseles:** Compatible con enlaces `/reel/`, `/reels/`, `/p/` y `/tv/`.
- **Previsualización integrada:** Reproductor de video y miniatura antes de descargar.
- **Privado y local:** Funciona directamente en tu navegador local (`http://127.0.0.1:5000`) sin anuncios ni rastreadores.

## Requisitos

- Python 3.10+
- Dependencias en `requirements.txt`:
  ```bash
  py -m pip install -r requirements.txt
  ```

## Uso rápido

1. En Windows, haz doble clic en **`iniciar_instafetch.bat`**, o ejecuta en la terminal:
   ```bash
   py app.py
   ```
2. Abre `http://127.0.0.1:5000` en tu navegador.
3. Pega el enlace del Reel o publicación pública de Instagram y haz clic en **Obtener Video**.
