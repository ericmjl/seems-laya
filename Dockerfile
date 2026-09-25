FROM docker.io/library/python:3.13-slim
# The app image carries Laya and its CPU-only PyTorch build so the same image can
# serve judgments (tools/laya_server.py) or run them in-process. The CPU wheel keeps
# the image far smaller than the CUDA default; point LAYA_URL at a GPU-served
# laya_server elsewhere if you need the speed.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    HF_HOME=/home/app/.cache/huggingface
WORKDIR /app
COPY requirements.txt requirements-laya.txt ./
RUN pip install -r requirements.txt \
    && pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-laya.txt \
    && useradd --create-home --uid 10001 app
COPY --chown=app:app pytest.ini ./
COPY --chown=app:app seems ./seems
COPY --chown=app:app app ./app
COPY --chown=app:app examples ./examples
COPY --chown=app:app tests ./tests
COPY --chown=app:app tools ./tools
COPY --chown=app:app docs ./docs
USER app
ENV PORT=3000 PYTHONPATH=/app
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 CMD python -c "import sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:3000/api/health', timeout=2).status == 200 else 1)"
CMD ["gunicorn", "--config", "app/gunicorn.conf.py", "app.server:app"]
