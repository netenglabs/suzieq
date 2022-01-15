# GUI

Starting with version 0.8, Suzieq has a GUI. The GUI is included in the same docker container, netenglabs/suzieq, as the rest of the suzieq pieces such as the REST server, the poller and the CLI. However, its recommended to launch a separate instance of the docker container that just runs the GUI. 

To launch the docker container running the GUI, you can do:
```docker run -itd -v <host parquet dir>:/suzieq/parquet -p 8501:8501 --name suzieq netenglabs/suzieq:latest```

Now attach to the docker container via:
```docker attach suzieq```

And at the prompt you can type ```suzieq-gui &``` and detach from the container via the usual escape sequence CTRL-P CTRL-Q

Now you can connect to localhost:8501 or to the host's IP address and port 8501 (for example, http://192.168.12.23:8501) and enjoy the GUI (ignore the external URL thats displayed when you launch the GUI). 

## Experimental Feature on Xplore Page

With the new table display, you can filter both simple and complex queries without needing to understand pandas query. This works without the experimental feature option selected. With the experimental option selected, whenever you add a filter, the distribution counts are immediately updated with the values of the filtered data. This needs more work, and may display some unexpected behavior. Hence we deem this experimental.

The caveats with this are:

* In the Xplore page, after changing the shown table, applying a filter might cause a page refresh. After this reload, filters work as expected. The page may randomly refresh at times causing you to lose the filters. 
* Keeping the page idle for more than 20 seconds, applying a filter or changing the column of the distribution graph might cause the page to be reloaded. After the reloading, filters should work as expected.
* Changing the column of the distribution graph might may cause a page refresh, so filters are lost.

