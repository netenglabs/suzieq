FROM python:3.7.9-slim-buster AS compiler

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib

RUN apt-get update && \
    pip3 install --upgrade pip

RUN mkdir -p /suzieq/
WORKDIR /suzieq

COPY dist/suzieq-0.11.0-py3-none-any.whl  /tmp/
RUN pip install /tmp//suzieq-0.11.0-py3-none-any.whl
COPY suzieq/config/etc/suzieq-cfg.yml /root/.suzieq/suzieq-cfg.yml

# Certificates and such for REST server
#COPY logo-small.jpg /suzieq

# Copy parquet files for demo
#COPY ./parquet /suzieq/parquet

WORKDIR /suzieq

ENV PATH=/root/.local/bin:$PATH:/root/.local/lib/python3.7/site-packages/suzieq/cli/:/root/.local/lib/python3.7/site-packages/suzieq/poller/:/root/.local/lib/python3.7/site-packages/suzieq/restServer

#ENV PYTHONPATH=/src/python-nubia
ENTRYPOINT ["/bin/bash"]

# USER 1001

LABEL name=suzieq-demo
LABEL version=0.11.0
LABEL description="Network Observability Tool"
