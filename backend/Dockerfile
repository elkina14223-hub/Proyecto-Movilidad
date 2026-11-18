FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY db ./db
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
# --no-server-header: no revelar la versión del servidor (RNF-SEG-05)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--ws-max-size", "4096","--proxy-headers", "--forwarded-allow-ips", "*"]
