FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir .

ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "backend.app.main"]
