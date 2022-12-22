###
# Defines the schema class and the associated methods for suzieq tables.
###

import os
import logging
import json
from typing import List, Dict, Optional
import pyarrow as pa


class Schema:
    '''Schema class holding schemas of all tables and providing ops on them'''

    def __init__(self, schema_dir):

        self._init_schemas(schema_dir)
        if not self._schema:
            raise ValueError("Unable to get schemas")

    def _init_schemas(self, schema_dir: str):
        """Returns the schema definition which is the fields of a table"""

        schemas = {}
        phy_tables = {}
        types = {}

        logger = logging.getLogger(__name__)
        if not (schema_dir and os.path.exists(schema_dir)):
            logger.error(
                "Schema directory %s does not exist", schema_dir)
            raise Exception(f"Schema directory {schema_dir} does not exist")

        for root, _, files in os.walk(schema_dir):
            for topic in files:
                if not topic.endswith(".avsc"):
                    continue
                with open(root + "/" + topic, "r") as f:
                    data = json.loads(f.read())
                    table = data["name"]
                    schemas[table] = data["fields"]
                    types[table] = data.get('recordType', 'record')
                    phy_tables[data["name"]] = data.get("physicalTable", table)
            break

        self._schema = schemas
        self._phy_tables = phy_tables
        self._types = types

    def tables(self) -> List[str]:
        '''Returns list of tables for which we have schemas'''
        return list(self._schema.keys())

    def fields_for_table(self, table: str) -> List[str]:
        '''Returns list of fields in given table'''
        return [f['name'] for f in self._schema[table]]

    def get_raw_schema(self, table: str) -> Dict:
        '''Raw schema for given table, JSON'''
        return self._schema[table]

    def field_for_table(self, table: str, field: str) -> Optional[str]:
        '''Returns info about field in table if present'''
        for f in self._schema[table]:
            if f['name'] == field:
                return f
        return None

    def type_for_table(self, table: str) -> str:
        '''Return table type: counter, record, derived etc.'''
        return self._types[table]

    def key_fields_for_table(self, table: str) -> List[str]:
        '''Return key fields for given table'''
        # return [f['name'] for f in self._schema[table]
        # if f.get('key', None) is not None]
        return self._sort_fields_for_table(table, 'key')

    def augmented_fields_for_table(self, table: str,
                                   fields: List[str],
                                   recurse: int) -> List[str]:
        '''Return all augmented fields in given list of fields (all if empty)
        If recurse is non-zero, continue to recurse till all fields are
        resolved
        '''
        all_aug_fields = [x['name'] for x in self._schema.get(table, [])
                          if 'depends' in x]
        if not fields:
            aug_fields = all_aug_fields
        else:
            aug_fields = [x for x in all_aug_fields if x in fields]

        if not (fields or recurse):
            return aug_fields

        all_parents = []
        new_aug_fields = []
        for f in aug_fields:
            all_parents += self.get_parent_fields(table, f)
        if all_parents:
            new_aug_fields = self.augmented_fields_for_table(
                table, all_parents, recurse-1)
        if not new_aug_fields:
            return aug_fields
        else:
            aug_fields.extend([x for x in new_aug_fields
                               if x not in aug_fields])
            return aug_fields

    def sorted_display_fields_for_table(self,
                                        table: str,
                                        getall: bool = False) -> List[str]:
        '''Returns sorted list of default display fields'''
        display_fields = self._sort_fields_for_table(table, 'display', getall)
        return [f for f in display_fields
                if not self.field_for_table(table, f).get('suppress', False)]

    def _sort_fields_for_table(self,
                               table: str,
                               tag: str,
                               getall: bool = False) -> List[str]:
        '''Returns sorted list of fields in table with given tag'''
        fields = self.fields_for_table(table)
        field_weights = {}
        for f_name in fields:
            field = self.field_for_table(table, f_name)
            if field.get(tag, None) is not None:
                field_weights[f_name] = field.get(tag, 1000)
            elif getall:
                field_weights[f_name] = 1000
        return list(sorted(field_weights.keys(),
                           key=lambda x: field_weights[x]))

    def array_fields_for_table(self, table: str) -> List[str]:
        '''Returns list of fields which are lists in table'''
        fields = self.fields_for_table(table)
        arrays = []
        for f_name in fields:
            field = self.field_for_table(table, f_name)
            if (isinstance(field['type'], dict) and
                    field['type'].get('type', None) == 'array'):
                arrays.append(f_name)
        return arrays

    def get_phy_table_for_table(self, table: str) -> Optional[str]:
        """Return the name of the underlying physical table"""
        if self._phy_tables:
            return self._phy_tables.get(table, table)
        return None

    def get_partition_columns_for_table(self, table: str) -> List[str]:
        """Return the list of partition columns for table"""
        if self._phy_tables:
            return self._sort_fields_for_table(table, 'partition')
        return []

    def get_arrow_schema(self, table: str) -> pa.schema:
        """Convert internal AVRO schema into PyArrow schema"""

        avro_sch = self._schema.get(table, None)
        if not avro_sch:
            raise AttributeError(f"No schema found for {table}")

        arsc_fields = []

        map_type = {
            "string": pa.string(),
            "long": pa.int64(),
            "int": pa.int32(),
            "double": pa.float64(),
            "float": pa.float32(),
            "timestamp": pa.int64(),
            "timedelta64[s]": pa.float64(),
            "boolean": pa.bool_(),
            "array.string": pa.list_(pa.string()),
            "array.nexthopList": pa.list_(pa.struct([('nexthop', pa.string()),
                                                     ('oif', pa.string()),
                                                     ('weight', pa.int32())])),
            "array.long": pa.list_(pa.int64()),
            "array.float": pa.list_(pa.float32()),
            "array.double": pa.list_(pa.float64()),
        }

        for fld in avro_sch:
            if "depends" in fld:
                # These are augmented fields, not in arrow"
                continue
            if isinstance(fld["type"], dict):
                if fld["type"]["type"] == "array":
                    if fld["type"]["items"]["type"] == "record":
                        avtype: str = "array.{}".format(fld["name"])
                    else:
                        avtype: str = "array.{}".format(
                            fld["type"]["items"]["type"])
                else:
                    # We don't support map yet
                    raise AttributeError
            else:
                avtype: str = fld["type"]

            arsc_fields.append(pa.field(fld["name"], map_type[avtype]))

        return pa.schema(arsc_fields)

    def get_parent_fields(self, table: str, field: str) -> List[str]:
        '''Get list of fields this augmented field depends upon'''
        avro_sch = self._schema.get(table, None)
        if not avro_sch:
            raise AttributeError(f"No schema found for {table}")

        for fld in avro_sch:
            if fld['name'] == field:
                if "depends" in fld:
                    return fld['depends'].split()
                else:
                    return []
        return []


class SchemaForTable:
    '''Class supporting operations on the schema for a given table'''

    def __init__(self, table, schema: Schema = None, schema_dir=None):
        if schema:
            if isinstance(schema, Schema):
                self._all_schemas = schema
            else:
                raise ValueError("Passing non-Schema type for schema")
        else:
            self._all_schemas = Schema(schema_dir=schema_dir)
        self._table = table
        if table not in self._all_schemas.tables():
            raise ValueError(f"Unknown table {table}, no schema found for it")

    @ property
    def type(self):
        '''Type of table'''
        return self._all_schemas.type_for_table(self._table)

    @ property
    def version(self):
        '''DB version for table'''
        return self._all_schemas.field_for_table(self._table,
                                                 'sqvers')['default']

    @ property
    def fields(self):
        '''Returns list of fields for table'''
        return self._all_schemas.fields_for_table(self._table)

    @ property
    def array_fields(self):
        '''Return list of array fields in table'''
        return self._all_schemas.array_fields_for_table(self._table)

    def get_phy_table(self):
        '''Get the name of the physical table backing this table'''
        return self._all_schemas.get_phy_table_for_table(self._table)

    def get_partition_columns(self):
        '''Get the Parquet partitioning columns'''
        return self._all_schemas.get_partition_columns_for_table(self._table)

    def key_fields(self) -> List[str]:
        '''Returns list of key fields for table'''
        return self._all_schemas.key_fields_for_table(self._table)

    def get_augmented_fields(self, fields) -> List[str]:
        '''Returns list of augmented fields, recursively resolving'''
        MAX_AUGMENTED_RECURSE = 2

        return self._all_schemas.augmented_fields_for_table(
            self._table, fields, MAX_AUGMENTED_RECURSE)

    def sorted_display_fields(self,
                              getall: bool = False) -> List[str]:
        '''Returns sorted list of default display fields'''
        return self._all_schemas.sorted_display_fields_for_table(
            self._table, getall)

    def field(self, field):
        '''Returns info about the specified field in table'''
        return self._all_schemas.field_for_table(self._table, field)

    def get_display_fields(self,
                           columns: list) -> list:
        """Return the list of display fields for the given table"""
        if columns == ["default"]:
            fields = self.sorted_display_fields()

        elif columns == ["*"]:
            fields = self.sorted_display_fields(getall=True)
        else:
            wrong_fields = [f for f in columns if f not in self.fields]
            if wrong_fields:
                raise ValueError(
                    f'Unknown fields {wrong_fields} in {self._table}')
            fields = columns.copy()

        return fields

    def get_phy_table_for_table(self) -> str:
        """Return the underlying physical table for this logical table"""
        return self._all_schemas.get_phy_table_for_table(self._table)

    def get_raw_schema(self) -> Dict:
        '''Return the raw schema of table'''
        return self._all_schemas.get_raw_schema(self._table)

    def get_arrow_schema(self) -> pa.Schema:
        '''Get Pyarrow schema of table'''
        return self._all_schemas.get_arrow_schema(self._table)

    def get_parent_fields(self, field) -> List[str]:
        '''Get dependent fields for a given augmented field in table'''
        return self._all_schemas.get_parent_fields(self._table, field)
