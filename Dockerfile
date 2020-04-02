FROM debian:buster-slim AS builder
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes python3-venv git && \
    python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip

FROM builder AS builder-venv
COPY requirements.txt /requirements.txt
RUN /venv/bin/pip install --disable-pip-version-check -r /requirements.txt

COPY ./config /suzieq/config
COPY ./suzieq /suzieq/suzieq
COPY .bashrc /root/.bashrc
COPY suzieq-cfg.yml /root/.suzieq/suzieq-cfg.yml

RUN mkdir /suzieq/parquet
WORKDIR /suzieq

# ENTRYPOINT ["/"]
# USER 1001

LABEL name=suzieq
LABEL version=0.1
