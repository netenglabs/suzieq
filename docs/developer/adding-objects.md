# Adding New Objects Including Command

Suzieq exposes the underlying data as objects with methods. BGP is an example of such an object as are interfaces and MAC addresses. The methods are realized via engines. Engines themselves are a class with specific instantiations such as pandas, spark, modin, dask etc.

So, to create a new object, you must first create an object under `suzieq/sqobjects` directory. Then create the engine implementations under `engines/<engine>`. For example, you’d create one for pandas under `suzieq/engines/pandas`. The engine methods inherit from the base engine method. If nothing more than what the base method provides is required, then the object-specific method can be empty.

Accessing these objects via CLI is done by creating a command associated with the object under `cli/sqcmds`. The naming of all these objects and the file names is important to enable automatic discovery of the object and command under the CLI and Jupyter.
