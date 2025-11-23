FROM python:3.11-slim

WORKDIR /app

# Installiere System-Abhängigkeiten (für lxml, etc.)
# Chrome/Selenium braucht mehr Setup, aber wir verwenden headless Chrome
# Für Docker ist es oft einfacher, Selenium Grid zu nutzen oder Chromium zu installieren.
# Wir installieren Chromium für Selenium.
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port für Web UI
EXPOSE 8000

# Startbefehl
CMD ["python", "main.py"]
