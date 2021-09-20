## Quick Start

We want to make it as easy as possible for you to start engaging with Suzieq. We support two ways in which you can get started with Suzieq. The first is using pre-built Docker containers, and the second is as a regular python package.

### As a Docker Container

To get started seeing the kind of analysis Suzieq provides today, we have a demo container that has data in including the the iamge.

    docker run -it -p 8501:8501 --name suzieq netenglabs/suzieq-demo
    suzieq-cli for the CLI OR
    suzieq-gui for the GUI. Connect to http://localhost:8501 via the browser to access the GUI

When you're within the suzieq-cli, you can run device unique columns=namespace to see the list of different scenarios, we've gathered data for. Use help inside the suzieq-cli to navigate your way around the CLI. Network operators should find the CLI easy to use as a router/bridge CLI as it provides contextual help and completions.

To start collecting data for your network, create an inventory file to gather the data from following the instructions here. Decide the directory where the data will be stored (ensure you have sufficient available space if you're going to be running the poller, say 100 MB at least). Lets call this dbdir. Now launch the suzieq docker container as follows:
```
    docker run -itd -v <parquet-out-loca-dir>:/suzieq/parquet -v <inventory-file>:/suzieq/inventory.yml --name sq-poller netenglabs/suzieq:latest
    Connect to the container via docker attach sq-poller
```

Launch the poller with the appropriate options. For example, `sq-poller -D inventory.yml -n mydatacenter` where mydatacenter is the name of the namespace where the data associated with the inventory is stored and inventory.yml is the inventory file in Suzieq poller native format (Use -a if you're using Ansible inventory file format).

### As a Python Package

Suzieq is also available as a standard Python package that you can install via pip. We strongly recommend the use of [Python virtual environment](https://docs.python.org/3.8/tutorial/venv.html). **Suzieq only works with Python versions 3.7.1 and above, and on Linux and MacOS**. The releases are always tested with Python versions 3.7 and 3.8. 

To install suzieq via pip run:
```
    pip install suzieq
```

To setup a virtual environment if you don't know how to, is as simple as:

* Running ```python -m venv suzieq-env``` (Assuming suzieq-env is a directory in the current folder you want to create the virtual environment in. The directory name can be anything you want it to be).
* Activating the virtual environment by changing directory to suzieq-env, and running ```source bin/activate```

Now, you can install suzieq via pip install as described above. 

Now you can use the main applications of Suzieq:

* sq-poller: The poller to gather the data from the various routers and bridges and Linux servers
* suzieq-gui: The GUI front end to view, query and analyze the data
* suzieq-cli: The CLI front end to view, query and analyze the data
* sq-rest-server: The REST API server
