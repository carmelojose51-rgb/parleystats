# ParleyStats

Prototipo móvil conectado a Football-Data.org mediante un proxy seguro.

## Iniciar

1. Define el token como variable de entorno (no lo pongas en `app.html`):
   `export FOOTBALL_DATA_API_TOKEN='TU_TOKEN'`
2. Ejecuta: `python3 server.py`
3. Abre `http://localhost:8080`

El navegador consulta `/api/competitions`, `/api/teams` y `/api/analyze`; el token solo vive en el servidor.

## Propiedad y seguridad

ParleyStats es un proyecto original de Carmelo Bohorquez. El código, diseño, marca y lógica de análisis están protegidos y no se autoriza su copia o redistribución sin permiso escrito. Consulta `NOTICE.md` para el aviso completo.

El servidor limita las consultas, restringe el acceso desde orígenes autorizados y no expone detalles internos de errores. Las claves de los proveedores deben configurarse únicamente como variables privadas en Render; nunca deben escribirse en `index.html` ni `app.html`.
