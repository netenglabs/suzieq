# Chunker
A chunker gets in input an inventory and split it in chunks.

Every chunker plugin must inherit from `.base_chunker.Chunker` and override the following method:
- `chunk(inventory, n_chunks, addl_params)`: splits the input inventory in <n_chunks> different inventory chunks

## StaticChunker(Defualt):
This chunker splits the inventory following two different policies:
- `serial`: takes the inventory and simply splits it in chunks
- `namespace`: takes the inventory and splits it keeping namespaces in the same worker.
This policy tries to divide the inventory homogeneously between workers.

The configuration for this chunker is the following
```yaml
- type: static_chunker      # chunker type (optional)
  split_pol: namespace      # chunking policy (optional)
                            # Default: serial
```
