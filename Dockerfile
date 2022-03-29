ARG version

FROM suzieq-base:$version

ARG version
ARG username=suzieq
ARG user_id=1000

RUN useradd $username -u $user_id --create-home --user-group

COPY ./dist/suzieq-$version-py3-none-any.whl  /tmp/

RUN pip install --upgrade pip
RUN pip install /tmp/suzieq-$version-py3-none-any.whl
RUN rm /tmp/suzieq-$version-py3-none-any.whl
COPY --chown=$username suzieq/config/etc/suzieq-cfg.yml /home/$username/.suzieq/suzieq-cfg.yml
RUN sed -i 's/127.0.0.1/0.0.0.0/' /home/$username/.suzieq/suzieq-cfg.yml
 
ENV PATH=/root/.local/bin:$PATH:/root/.local/lib/python3.7/site-packages/suzieq/cli/:/root/.local/lib/python3.7/site-packages/suzieq/poller/:/root/.local/lib/python3.7/site-packages/suzieq/restServer

USER $username
WORKDIR /home/$username
ENTRYPOINT ["/bin/bash"]

LABEL name=suzieq
LABEL version=$version
LABEL description="Network Observability Tool"
