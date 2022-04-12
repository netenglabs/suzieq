ARG version

FROM suzieq-base:$version

ARG version
ARG username=suzieq
ARG user_id=1000

RUN useradd $username -u $user_id --create-home --user-group

RUN python3 -m pip install --upgrade --no-cache-dir pip

COPY --chown=$username suzieq/config/etc/suzieq-cfg.yml /home/$username/.suzieq/suzieq-cfg.yml

RUN mkdir /home/$username/parquet && \
    chown $user_id:$user_id /home/$username/parquet && \
    sed -i 's/127.0.0.1/0.0.0.0/' /home/$username/.suzieq/suzieq-cfg.yml

COPY ./dist/suzieq-$version-py3-none-any.whl  /tmp/

RUN python3 -m pip install --no-cache-dir /tmp/suzieq-$version-py3-none-any.whl && \
    rm -rf /tmp/* /var/tmp/*

VOLUME [ "/home/$username/parquet" ]
 
ENV PATH=/root/.local/bin:$PATH:/root/.local/lib/python3.7/site-packages/suzieq/cli/:/root/.local/lib/python3.7/site-packages/suzieq/poller/:/root/.local/lib/python3.7/site-packages/suzieq/restServer

ENV SQENV=docker

USER $username
WORKDIR /home/$username
ENTRYPOINT ["/bin/bash"]

LABEL name=suzieq
LABEL description="Network Observability Tool"
LABEL version=$version
