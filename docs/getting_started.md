## Quick Start

We want to make it as easy as possible for you to start engaging with Suzieq. We support two ways in which you can get started. The first is using pre-built Docker container, and the second is as a regular Python package.

### As a Docker Container

To get started seeing the kind of analysis Suzieq provides today, we have a demo container that has data in including the image.

    docker run -it -p 8501:8501 --name suzieq netenglabs/suzieq-demo
    suzieq-cli for the CLI OR
    suzieq-gui for the GUI. Connect to http://localhost:8501 via the browser to access the GUI

When you're within the **suzieq-cli**, you can run device unique *columns=namespace* to see the list of different scenarios, we've gathered data for. Use *help* command, *?* or *TAB key* inside the **suzieq-cli** to navigate your way around the CLI. Network operators should find the CLI easy to use as a router/bridge CLI as it provides contextual help and completions.

To start collecting data for your network, create an inventory file to gather the data from. Next decide the directory where the data (in Parquet format) will be stored. Ensure you have sufficient available space if you're going to be running the poller continuously, say 100 MB at least. Let's call this path **dbdir**. Now launch the Suzieq docker container as follows:
```
    docker run -itd -v <dbdir>:/suzieq/parquet -v <inventory-file>:/suzieq/inventory.yml --name sq-poller netenglabs/suzieq:latest
    Connect to the container via docker attach sq-poller
```

Launch the poller with the appropriate options. For example, `sq-poller -D inventory.yml -n mydatacenter` where **mydatacenter** is the name of the **namespace** where the data associated with the inventory will be stored, and **inventory.yml** is the inventory file in Suzieq poller native format (Use **-a** if you're using Ansible inventory file format).

### As a Python Package

Suzieq is also available as a standard Python package that you can install via **pip**. We strongly recommend the use of [Python virtual environment](https://docs.python.org/3.8/tutorial/venv.html). **Suzieq only works with Python versions 3.7.1 and above, and on Linux and MacOS**. The releases are always tested with Python versions 3.7 and 3.8. 

To install Suzieq via pip run:
```
    pip install suzieq
```

To setup a virtual environment if you don't know how to, is as simple as:

* Running ```python -m venv suzieq-env``` (Assuming *suzieq-env* is a directory in the current folder you want to create the virtual environment in. The directory name can be anything you want it to be).
* Activating the virtual environment by changing directory to suzieq-env, and running ```source bin/activate```

Now, you can install Suzieq via "pip install" as described above. 

Now you can use the main applications of Suzieq:

* **sq-poller**: The poller to gather the data from the various routers and bridges and Linux servers
* **suzieq-gui**: The GUI front end to view, query and analyze the data
* **suzieq-cli**: The CLI front end to view, query and analyze the data
* **sq-rest-server**: The REST API server

###  Installation with Pipenv for developers
The complicated non-docker way to install Suzieq is to get the code from GitHub:
 1. git clone: `git clone git@github.com:netenglabs/suzieq.git`
 2. Suzieq assumes the use of python3.7 which may not be installed on your computer by default. 
 Ubuntu 18.04 ships with 3.6 as default, for example. Check your python version with `python3 --version`. 
 If that is different from 3.7, you’ll need to add the python3.7 and 3.7 dev package. 
 But, until we can build the different engines separately, we’re stuck with this requirement. 
 3. To install python3.7 on Ubuntu 18.04, please execute the following commands:
    ```
    sudo add-apt-repository ppa:deadsnakes/ppa
    sudo apt install python3.7 python3.7-dev
    ```
 4. Install python3-pip if it has not been installed.
    ```
    sudo apt install python3-pip
    ``` 
 5. From the suzieq directory, run pip3 on the requirements file:
   ```bash
   pip3 install --user --disable-pip-version-check -r /requirements.txt
   ```

Suzieq requires that you have a suzieq config file either in '/.suzieq/suzieq-cfg.yml' or '/.suzieq-cfg.yml'.
It looks like:
```
data-directory: /home/jpiet/parquet-out
service-directory: /home/jpiet/suzieq/config
schema-directory: /home/jpiet/suzieq/config/schema
temp-directory: /tmp/suzieq
logging-level: WARNING
```

`python3 suzieq/poller/sq-poller.py -D ~/dual-bgp`