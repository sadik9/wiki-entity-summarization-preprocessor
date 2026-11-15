FROM python:3.10 AS base
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS poetry
RUN pip install poetry==1.8.5 poetry-plugin-export==1.8.0
COPY poetry.lock pyproject.toml /app/
RUN poetry export --without-hashes -o requirements.txt

FROM base AS build
COPY --from=poetry /app/requirements.txt /tmp/requirements.txt
RUN python -m venv .venv && \
    .venv/bin/pip install 'wheel==0.42.0' && \
    .venv/bin/pip install --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/requirements.txt

FROM python:3.10-slim AS runtime
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH
COPY --from=build /app/.venv /app/.venv
COPY commons /app/commons
COPY wiki_summary /app/wiki_summary
COPY summary_processor.py /app/main.py

ENTRYPOINT ["python", "main.py"]
