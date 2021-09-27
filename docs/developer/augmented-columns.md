## Augmented Columns

Augmented columns are columns that are computed based on other columns, typically from the same table, but possibly from other tables as well. Examples of augmented columns are peerHostname in case of OSPF to name the peer by hostname, and prefixlen in case of routes. Examples of augmented columns taken from other tables include os type or vendor. 

Augmented columns MUST be:

* Visible as a valid field when the user looks at a table’s schema
* Selectable as a column in show and unique
* Filterable (via a pandas query string for example)
* Definable as a default display field.

Augmented columns MUST NOT be:

* populated in the parquet DB. 

Augmented columns MAY be:

* Nested (defining an augmented column that is derived from other augmented columns)
* User-defined
* key fields
	
### Phase 1 Version

In the initial version, we DO NOT allow:

* Nested augmented columns
* Augmented columns from other tables i.e. you cannot define a column from table X as an augmented column in table Y
* User-defined augmented columns
* Augmented columns as key fields
* Checking for these may not exist, and so its upto the user to not use unsupported features

We define an augmented column in a table by adding a field called “depends”. Here’s an example of an augmented column in the BGP table:

```
{
    "name": "afiSafi",
    "type": "string",
    "description": "space separated concat of afi and safi fields",
    "depends": "afi safi"
}
```

This indicates that the column is augmented and depends on the fields “afi” and “safi”. The model is such that we can support adding fields from other tables as follows:

```
{
    "name": "os",
    "type": "string",
    "description": "network os that created this entry",
    "depends": "device:os"
}
```

This indicates that the os field comes from the device table’s os field. While this second format is not supported in the initial version, it shows what’s possible.

Allowing the function to derive the augmented column reside in the schema itself feels dangerous and so is not allowed at this point.

### Phase 1 Implementation

The minimal amount of changes to code involves:

* Defining the augmented column identification to be in the `Schema/SchemaForTable` classes
* Adding the dependent fields to the augmented column as additional fields to be extracted in `engineobj.py`
* Not including augmented columns in the `get_arrow_schema()` output
* Adding code for each table that an augmented column is defined in to handle the specifics of constructing the augmented column.

We must return augmented columns as a normal column from the schema in the `get_fields`.
