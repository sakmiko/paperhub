FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /root/paper-downloads

USER nobody

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]