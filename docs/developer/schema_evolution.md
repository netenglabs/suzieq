# Schema Evolution in Suzieq

Anything that intends to live for a long time has to evolve. Data is no different. Normalized data from multiple vendors even more so. During the course of Suzieq's brief life of about 3-4 months, the schema for one resource or the other has evolved. It has evolved in response as new, more sophisticated analysis has emerged to solve problems such as path, and it has evolved in response to new NOS being added to the system. A simple example is how the MAC table evolved when we added support for JunOS MX's VPLS MAC table support. VPLS on JunOS doesn't have a VLAN field, but only a bridging instance field that is a name, not a number. So, we needed to (i) add a new column and (ii) change the key to account for this new column to uniquify MAC addresses. This document addresses schema evolution.

## When Does a Schema Change?

In Suzieq, the schema has changed when:
- One or more fields are added or removed
- The type of the field changes
- The name of the field changes (say due to typos)

## Goals of Schema Evolution

The primary goal of schema evolution is to preserve the existing user data with the schema change. An equally important goal is to ensure that the analysis code doesn't get too complex and thereby buggy, as a result of handling schema changes. This second goal is also a user-facing goal, as the ability for developers to add code easily, write tests etc. all decrese if the schema evolution solution doesn't handle the issue in a simple way, and as a consequence the quality of the software goes down.

## Schema Evolution Principles

Schema evolution is a much researched topic. The best practices that can be distilled from it are as follows:
- Version schema
- Only add fields, don't delete. As much as possible.
- Don't change key fields
- Don't change type. Everything is a string if uncertain, as that's the most flexible type.

Here is a common table that's presented in many schema evolution discussions.
| Compatibility | Definition | Allowed Changes | Check Against | Upgrade First| 
|---------------|------------|-----------------|---------------|--------------|
| Always Compatible | No schema checking | All changes | All prev versions | Any order |
| Always incompatible | No schema evolution | No changes | N/A | N/A |
| Backward | New readers can read prev version | Add optional fields, del fields | Latest | Readers |
| Backward Transitive | New readers can read all prev version | Add optional fields, del fields | All prev versions | Readers |
| Forwards | Readers of prev version can read new version | Add fields, del optional | Latest | Writers |
| Forwards Transitive | Readers of all prev version can read new version | Add fields, del optional | All prev versions | Writers |
| Full | Backward & Forward compatible with prev version | Modify optional fields | Latest | Any order |
| Full Transitive | Backward & Forward compatible with all prev versions | Modify optional | All prev versions | Any order |


In Suzieq, we'll aim for "Full Transitive" compatibility from the matrix above.

## Schema Evolution in Suzieq

With Suzieq using a pull model by default, schema evolution between readers and writers is not as interesting. I expect the **sq-poller** and the **suzieq-cli** to be released together. The REST API will similarly be released at the same time as the updated schema. In either case, the solution proposed should address make the reader vs writer update model irrelevant.

To meet the goals defined in the simplest possible way, we propose the following design:
- All resources (tables) will be versioned. 
- In the initial state, this version will be 0. In version 0 state, the fields can be modified as to add and delete fields. Once a resource data model becomes stable, we move it to version 1. Once a resource moves to version 1, we will ensure that the data can be preserved despite changes to the data model. 
- Once a resource reaches version 1, we cannot delete fields or change their type. We can only add new fields. Whenever we add new fields, we bump up the version.
- Tools will be written to handle this version bump in a user-unaware way.
- We enforce the schema on write. 
- The on-disk partition columns used for parquet will always be the tuple: **{version, namespace, hostname}**. All other fields are just ordinary fields. This ensures we don't break on-disk format in an incompatible way (handling changes in the parquet internal format itself is a separate discussion). 
- On read, the only routine that needs to know how to handle different versions is the parquet reader routine (the file `suzieq/engines/pandas/engine.py` in the current code. Will be renamed to `dbread.py` in the upcoming release). This routine will ensure that all the fields missing from the on-disk version but present in the current schema version, are added to the dataframe (if required) before returning the dataframe to the upper layers. This addition will ensure the values take on default values, as defined by the schema, and not make it pandas NaN value. This ensures many of pandas operations including type-casting the column succeeds.
- Since all the fields present in the dataframe are as per the schema, and no fields are deleted, the remainder of the analysis code works as expected with no additional checking required.

### Disambiguating Fields in Suzieq

In Suzieq, there are certain fields, which are used to disambiguate older entries from newer entries.

For example, in case of an interface, the combination of **{namespace, hostname, interface name}** always uniquely identify an interface. You cannot add the operational state or the MTU to this key list because then you'd have no way of knowing which entry is duplicate and which is not. If you had an interface with state up at time t0, and it later changed to down at time t1 (t1 > t0), if we included operational state as a key field, you'd end up with both entries as being valid. Again, the key fields are for disambiguation only.

Since we do not delete any field by default, we can assume that the fields used for disambiguation can change. Consider the behavior if we add a new field to disambiguate entries, for example, adding the bridging instance along with VLAN. Since the older schema entries worked fine without the need for a bridging instance, a default value for the bridging instance will continue to make the disambiguation logic work as expected. 

It must be ensured by the reader (or the upper layer calling the reader routine) that the disambiguating fields are always read!
