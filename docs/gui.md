# GUI

Starting with version 0.8, SuzieQ has a GUI. The GUI is included in the same docker container, netenglabs/suzieq, as the rest of the suzieq pieces such as the REST server, the poller and the CLI. However, its recommended to launch a separate instance of the docker container that just runs the GUI.

To launch the docker container running the GUI, you can do:
```docker run -it -v <parquet-out-local-dir>:/home/suzieq/parquet -p 8501:8501 --name suzieq netenglabs/suzieq:latest```

And at the prompt you can type ```suzieq-gui &``` and detach from the container via the usual escape sequence CTRL-P CTRL-Q

Now you can connect to localhost:8501 or to the host's IP address and port 8501 (for example, http://192.168.12.23:8501) and enjoy the GUI (ignore the external URL thats displayed when you launch the GUI).

## GUI arguments
The SuzieQ GUI can be simply started, as shown above, typing the command `suzieq-gui`.
Some additional arguments are allowed to set up the GUI:

- `-p --port`: defines in which port the GUI is going to run. By default is `8501`
- `-c --config`: SuzieQ configuration file to use. Check the [Configuration](config_file.md) page to check the default configuration file location.

## Start a GUI behind an nginx reverse proxy

This section is an step by step guide on how to set up an [nginx](http://nginx.org/en/docs/) reverse proxy for the SuzieQ GUI.

### Requirements

- nginx: [nginx installation guide](http://nginx.org/en/docs/install.html)
- SuzieQ GUI running

### Configure and start nginx

Move into the nginx config directory

``` shell
cd /etc/nginx
```

!!! info
        Some of the commands below may need `sudo`

Fill the values into the following template and put it in a file under `/etc/nginx/sites-available/suzieq.conf`

```
server {
        listen <PROXY_SERVER_PORT> default_server;
        listen [::]:<PROXY_SERVER_PORT> default_server;
        server_name <SERVER_NAME>;
        location /<PROXY_PATH> {
                proxy_pass <SUZIEQ_GUI_URL>;
        }
        # streamlit redirects config
        location /<PROXY_PATH>/streamlit-components-demo {
                proxy_pass <SUZIEQ_GUI_URL>/;
        }
        location ^~ /<PROXY_PATH>/static {
                proxy_pass <SUZIEQ_GUI_URL>/static/;
        }
        location ^~ /<PROXY_PATH>/healthz {
                proxy_pass <SUZIEQ_GUI_URL>/healthz;
        }
        location ^~ /<PROXY_PATH>/vendor {
                proxy_pass <SUZIEQ_GUI_URL>/vendor;
        }
        location ^~ /<PROXY_PATH>/component {
                proxy_pass <SUZIEQ_GUI_URL>/component;
        }

        location /<PROXY_PATH>/stream {
                proxy_pass <SUZIEQ_GUI_URL>/stream;
                proxy_http_version 1.1;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header Host $host;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                proxy_read_timeout 86400;
        }
}
```

The example below shows a configuration file shows how to create a reverse proxy
to serve a SuzieQ GUI running on `http:localhost:8501` to be mapped to `http:localhost:80/suzieq`

```
server {
        listen 80 default_server;
        listen [::]:80 default_server;
        server_name localhost;
        location /suzieq {
                proxy_pass http://127.0.0.1:8501;
        }
        # streamlit redirects config
        location /suzieq/streamlit-components-demo {
                proxy_pass http://127.0.0.1:8501/;
        }
        location ^~ /suzieq/static {
                proxy_pass http://127.0.0.1:8501/static/;
        }
        location ^~ /suzieq/healthz {
                proxy_pass http://127.0.0.1:8501/healthz;
        }
        location ^~ /suzieq/vendor {
                proxy_pass http://127.0.0.1:8501/vendor;
        }
        location ^~ /suzieq/component {
                proxy_pass http://127.0.0.1:8501/component;
        }

        location /suzieq/stream {
                proxy_pass http://127.0.0.1:8501/stream;
                proxy_http_version 1.1;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header Host $host;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                proxy_read_timeout 86400;
        }
}
```

!!! warning
        These examples, do **NOT** provide any security.
        Please check the [nginx documentation](http://nginx.org/en/docs/) to know how add security to your nginx server


Now copy the configuration from `/etc/nginx/sites-available` to `/etc/nginx/sites-enabled`.
It is recommended to use a symbolic link.

``` shell
ln -s /etc/nginx/sites-available/suzieq.conf /etc/nginx/sites-enabled/suzieq.conf
```

Now restart the nginx service
``` shell
sudo systemctl restart nginx
```

You can open you browser and connect to your configured nginx to see the SuzieQ GUI
