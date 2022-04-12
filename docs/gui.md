# GUI

Starting with version 0.8, Suzieq has a GUI. The GUI is included in the same docker container, netenglabs/suzieq, as the rest of the suzieq pieces such as the REST server, the poller and the CLI. However, its recommended to launch a separate instance of the docker container that just runs the GUI.

To launch the docker container running the GUI, you can do:
```docker run -it -v <parquet-out-local-dir>:/home/suzieq/parquet -p 8501:8501 --name suzieq netenglabs/suzieq:latest```

And at the prompt you can type ```suzieq-gui &``` and detach from the container via the usual escape sequence CTRL-P CTRL-Q

Now you can connect to localhost:8501 or to the host's IP address and port 8501 (for example, http://192.168.12.23:8501) and enjoy the GUI (ignore the external URL thats displayed when you launch the GUI).

## GUI arguments
The SuzieQ GUI can be simply started, as shown above, typing the command `suzieq-gui`.
Some additional arguments are allowed to set up the GUI:

- `-p --port`: defines in which port the GUI is going to run. By default is `8501`
- `-c --config`: SuzieQ configuration file to use. Check the [Configuration](config_file.md#use-config-file) page to check the default configuration file location.
