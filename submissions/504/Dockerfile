FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "-w", "4", "-k", "gthread", "--threads", "4", "-b", "0.0.0.0:8080", "app:app"]
