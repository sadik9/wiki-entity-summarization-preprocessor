# RELIEF image. Build context is the repository root (see compose.yaml):
#   relief/docker-build.sh            (records the git commit in the image)
#   docker compose run --rm relief check
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    RELIEF_RUNS_DIR=/runs
WORKDIR /app/relief

# Dependencies first, so code changes don't reinstall the ~5 GB of CUDA wheels.
COPY relief/requirements.lock ./requirements.lock
RUN pip install -r requirements.lock

COPY relief/pyproject.toml ./
COPY relief/src ./src
COPY relief/tests ./tests
COPY relief/pilot ./pilot
# --no-build-isolation: build with the setuptools already installed above, no second download
RUN pip install --no-deps --no-build-isolation -e .

ARG GIT_COMMIT=unknown
ENV RELIEF_GIT_COMMIT=${GIT_COMMIT}
LABEL org.opencontainers.image.revision=${GIT_COMMIT} \
      org.opencontainers.image.title="wikes-relief"

ENTRYPOINT ["relief"]
CMD ["check"]
