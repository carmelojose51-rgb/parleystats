FROM python:3.12-slim
WORKDIR /app
COPY app.html index.html server.py manifest.json icon-192.png icon-512.png ./
ENV PORT=10000
CMD ["python3", "server.py"]
