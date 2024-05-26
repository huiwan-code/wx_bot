FROM ohai9/homcloud:4.4.1-python3.12.2-slim-bookworm
EXPOSE 5000

RUN apt update -y && apt install -y --no-install-recommends \
    g++ \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY ./manage.py /app/manage.py
COPY pyproject.toml /app/pyproject.toml
COPY ./bin /app/bin
COPY ./wx_bot /app/wx_bot 

RUN pip install pdm
RUN pdm install

RUN ["chmod", "+x", "/app/bin/docker-entrypoint.sh"]

ENTRYPOINT ["/app/bin/docker-entrypoint.sh"]
CMD ["server"]
