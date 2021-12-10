# Manager
A manager plugin has two duties:
- communicate to the poller the number of desired workers
- receive the list of inventory chunks and assign each of them to a worker

Every manager plugin must inherit from `.base_manager.Manager` and override
the following functions:
- `get_n_workers(inventory)`: returns the number of desired workers.
This value can be calculated starting from the global inventory
- `apply(inventory_chunks)`: assign each inventory chunk to a different worker

The manager configuration is specified inside the `sq-config.yml`.
The schema of the manager in the configuration file is shown below
```yaml
# ..
# manager configuration
  - type: <manager_type>
    # manager args
```

# StaticManager(Default)
This manager is configured via a static number of workers.
In the `apply` function, the plugin writes a Suzieq native file for each inventory chunk and, if required in the configuration, starts the workers with these generated inventory files.
```yaml
# manager configuration
  - type: static_manager                        # manager type (optional)
      workers_count: 3                          # number of desired workers (optional)
                                                # Default: 1

      inventory_path: path/to/inventory/dir     # generated inventories directory (optional)
                                                # Default: 'suzieq/.poller/intentory/static_inventory'

      inventory_file_name: inventory            # generated inventories file name (optional)
                                                # Default: 'static_inv'
                                                # the output file name format will be <inventory_file_name><chunk_number>.yaml

      start_workers: False                      # if False, the manager only generates the inventories without
                                                # starting the workers (optional)
                                                # Default: True
```
