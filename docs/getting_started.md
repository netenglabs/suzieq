## Quick Start

We want to make it as easy as possible for you to start engaging with Suzieq, so we have a demo that has data in including the the iamge.

    docker run -it -p 8501:8501 --name suzieq netenglabs/suzieq-demo
    suzieq-cli for the CLI OR
    suzieq-gui for the GUI. Connect to http://localhost:8501 via the browser to access the GUI

When you're within the suzieq-cli, you can run device unique columns=namespace to see the list of different scenarios, we've gathered data for. Use help inside the suzieq-cli to navigate your way around the CLI. Network operators should find the CLI easy to use as a router/bridge CLI as it provides contextual help and completions.

To start collecting data for your network, create an inventory file to gather the data from following the instructions here. Decide the directory where the data will be stored (ensure you have sufficient available space if you're going to be running the poller, say 100 MB at least). Lets call this dbdir. Now launch the suzieq docker container as follows:
```
    docker run -it -vdbdir:/suzieq/parquet --name sq-poller netenglabs/suzieq
    Connect to the container via docker attach sq-poller
```

Launch the poller with the appropriate options. For example, sq-poller -D inventory.yml -k where mydatacenter is the name of the namespace where the data associated with the inventory is storedand inventory.yml is the inventory file in Suzieq poller native format (Use -a if you're using Ansible inventory file format).
