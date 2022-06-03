ARG version=1.0

FROM python:3.7.11-buster AS base

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y curl && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    python -m pip install --upgrade --no-cache-dir pip wheel


RUN curl -sSL https://install.python-poetry.org -o /tmp/install-poetry.py && \
    python /tmp/install-poetry.py && \
    rm -f /tmp/install-poetry.py

ENV PATH="${PATH}:/root/.local/bin"

RUN poetry config virtualenvs.create false && \
    poetry config installer.parallel false


COPY poetry.lock pyproject.toml /source/

WORKDIR /source/

RUN poetry install --no-interaction --no-ansi --no-root 

COPY ./ ./

RUN poetry install --no-interaction --no-ansi

ENV SQENV=docker

ENTRYPOINT ["tail", "-f", "/dev/null"]

