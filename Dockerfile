FROM python:3.12-slim
WORKDIR /app
COPY app.html server.py ./
ENV PORT=10000
CMD ["python3", "server.py"]
