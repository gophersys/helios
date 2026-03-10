FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask requests gunicorn

COPY main.py .

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "--timeout", "30", "main:app"]
