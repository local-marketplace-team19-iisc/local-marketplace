FROM --platform=linux/amd64 python:3.11-slim

# Accept corporate proxy + SSL-inspection CA at build time.
# These args are passed via --build-arg; they have no effect when unset.
ARG http_proxy
ARG https_proxy
ARG no_proxy
ARG PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

WORKDIR /app

COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir \
      --timeout 300 \
      --trusted-host pypi.org \
      --trusted-host files.pythonhosted.org \
      --trusted-host pypi.python.org \
      .

ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "backend.app.main"]
