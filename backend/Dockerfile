FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir \
    fastapi "uvicorn[standard]" sqlalchemy alembic "psycopg[binary]"

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
