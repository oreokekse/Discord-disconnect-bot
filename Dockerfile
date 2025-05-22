# Verwende ein schlankes Python-Image
FROM python:3.11-slim

# Arbeitsverzeichnis im Container setzen
WORKDIR /app

# Requirements-Datei kopieren und Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Restliche Projektdateien ins Image kopieren
COPY . .

# Container starten mit dem Bot
CMD ["python", "main.py"]
