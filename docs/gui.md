## GUI

Starting with version 0.8, Suzieq has a GUI. The GUI is included in the same docker container, ddutt/suzieq, as the rest of the suzieq pieces such as the REST server, the poller and the CLI. However, its recommended to launch a separate instance of the docker container that just runs the GUI. 

To launch the docker container running the GUI, you can do:
```docker run -itd -v <host parquet dir>:/suzieq/parquet -p 8501:8501 --name suzieq ddutt/suzieq:latest```

Now attach to the docker container via:
```docker attach suzieq```

And at the prompt you can type ```suzieq-gui &``` and detach from the container via the usual escape sequence CTRL-P CTRL-Q

Now you can connect to localhost:8501 and enjoy the GUI. 
