FROM python:3.12-slim
WORKDIR /app
COPY app.html server.py ./
ENV PORT=10000
CMD ["sh", "-c", "python3 -c \"p='server.py';s=open(p).read();s=s.replace(\"('0.0.0.0',8080)\",\"('0.0.0.0',int(__import__('os').environ.get('PORT','8080')))\");open(p,'w').write(s)\" && python3 server.py"]
