FROM python:3.7.9-slim-buster AS compiler

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib

RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes git curl && \
    pip3 install --upgrade pip

RUN mkdir -p /suzieq/
WORKDIR /suzieq

RUN pip install "poetry==1.0.9"
COPY poetry.lock pyproject.toml /suzieq/
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev --no-root

COPY ./config /suzieq/config
COPY ./suzieq /root/.local/lib/python3.7/site-packages/suzieq
COPY ./build/suzieq-cfg.yml /root/.suzieq/suzieq-cfg.yml

# Certificates and such for REST server
COPY ./build/key.pem /root/.suzieq/
COPY ./build/cert.pem /root/.suzieq/
COPY ./build/launch-gui /usr/local/bin/suzieq-gui
COPY logo-small.jpg /suzieq

# Copy parquet files for demo
#COPY ./parquet /suzieq/parquet

WORKDIR /suzieq

ENV PATH=/root/.local/bin:$PATH:/root/.local/lib/python3.7/site-packages/suzieq/cli/:/root/.local/lib/python3.7/site-packages/suzieq/poller/:/root/.local/lib/python3.7/site-packages/suzieq/restServer

ENV PYTHONPATH=/src/python-nubia
ENTRYPOINT ["/bin/bash"]

# USER 1001

LABEL name=suzieq
LABEL version=0.8.0
LABEL description="Network Observability Tool"
