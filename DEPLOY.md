# Despliegue seguro de ParleyStats

El backend lee `FOOTBALL_DATA_API_TOKEN` desde una variable de entorno. El token no está en `app.html`, Dockerfile ni repositorio.

Servicio recomendado: Render (Web Service + Docker). Configura la variable secreta `FOOTBALL_DATA_API_TOKEN` en el panel del servicio y despliega este directorio.
