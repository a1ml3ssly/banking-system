FROM python:3.12-slim

WORKDIR /app

# System deps needed by pymssql
RUN apt-get update && apt-get install -y --no-install-recommends \
    freetds-dev \
    freetds-bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "-m", "flask", "--app", "app", "run", "--host=0.0.0.0", "--port=5000"]
