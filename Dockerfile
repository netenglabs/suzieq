FROM python:3.7.7-slim-buster AS compiler

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib

RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes git && \
    pip3 install --upgrade pip

COPY build/requirements.txt /requirements.txt
RUN pip3 install --user --disable-pip-version-check -r /requirements.txt

FROM python:3.7.7-slim-buster AS builder
COPY --from=compiler /root/.local /root/.local
RUN mkdir -p /suzieq/parquet

COPY ./config /suzieq/config
COPY ./suzieq /root/.local/lib/python3.7/site-packages/suzieq
COPY ./build/suzieq-cfg.yml /root/.suzieq/suzieq-cfg.yml
COPY ./suzieq/cli/suzieq-cli /root/.local/bin
COPY ./suzieq/poller/sq-poller /root/.local/bin

WORKDIR /suzieq

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib
ENTRYPOINT ["/bin/bash"]

# USER 1001

LABEL name=suzieq
LABEL version=0.1
