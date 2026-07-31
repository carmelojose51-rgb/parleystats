# ParleyStats

Prototipo móvil conectado a Football-Data.org mediante un proxy seguro.

## Iniciar

1. Define el token como variable de entorno (no lo pongas en `app.html`):
   `export FOOTBALL_DATA_API_TOKEN='TU_TOKEN'`
2. Ejecuta: `python3 server.py`
3. Abre `http://localhost:8080`

El navegador consulta `/api/competitions`, `/api/teams` y `/api/analyze`; el token solo vive en el servidor.
