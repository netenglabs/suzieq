###
# Defines the schema class and the associated methods for suzieq tables.
###

import os
import logging
import json
import pyarrow as pa


class Schema(object):

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
                "Schema directory {} does not exist".format(schema_dir))
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

    def tables(self):
        return self._schema.keys()

    def fields_for_table(self, table):
        return [f['name'] for f in self._schema[table]]

    def get_raw_schema(self, table):
        return self._schema[table]

    def field_for_table(self, table, field):
        for f in self._schema[table]:
            if f['name'] == field:
                return f

    def type_for_table(self, table):
        return self._types[table]

    def key_fields_for_table(self, table):
        # return [f['name'] for f in self._schema[table]
        # if f.get('key', None) is not None]
        return self._sort_fields_for_table(table, 'key')

    def augmented_fields_for_table(self, table):
        return [x['name'] for x in self._schema.get(table, [])
                if 'depends' in x]

    def sorted_display_fields_for_table(self, table, getall=False):
        return self._sort_fields_for_table(table, 'display', getall)

    def _sort_fields_for_table(self, table, tag, getall=False):
        fields = self.fields_for_table(table)
        field_weights = {}
        for f_name in fields:
            field = self.field_for_table(table, f_name)
            if field.get(tag, None) is not None:
                field_weights[f_name] = field.get(tag, 1000)
            elif getall:
                field_weights[f_name] = 1000
        return [k for k in sorted(field_weights.keys(),
                                  key=lambda x: field_weights[x])]

    def array_fields_for_table(self, table):
        fields = self.fields_for_table(table)
        arrays = []
        for f_name in fields:
            field = self.field_for_table(table, f_name)
            if (isinstance(field['type'], dict) and
                    field['type'].get('type', None) == 'array'):
                arrays.append(f_name)
        return arrays

    def get_phy_table_for_table(self, table):
        """Return the name of the underlying physical table"""
        if self._phy_tables:
            return self._phy_tables.get(table, table)

    def get_partition_columns_for_table(self, table):
        """Return the list of partition columns for table"""
        if self._phy_tables:
            return self._sort_fields_for_table(table, 'partition')

    def get_arrow_schema(self, table):
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

    def get_parent_fields(self, table, field):
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


class SchemaForTable(object):
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

    @property
    def type(self):
        return self._all_schemas.type_for_table(self._table)

    @property
    def version(self):
        return self._all_schemas.field_for_table(self._table,
                                                 'sqvers')['default']

    @property
    def fields(self):
        return self._all_schemas.fields_for_table(self._table)

    @property
    def array_fields(self):
        return self._all_schemas.array_fields_for_table(self._table)

    def get_phy_table(self):
        return self._all_schemas.get_phy_table_for_table(self._table)

    def get_partition_columns(self):
        return self._all_schemas.get_partition_columns_for_table(self._table)

    def key_fields(self):
        return self._all_schemas.key_fields_for_table(self._table)

    def get_augmented_fields(self):
        return self._all_schemas.augmented_fields_for_table(self._table)

    def sorted_display_fields(self, getall=False):
        return self._all_schemas.sorted_display_fields_for_table(self._table,
                                                                 getall)

    def field(self, field):
        return self._all_schemas.field_for_table(self._table, field)

    def get_display_fields(self, columns: list) -> list:
        """Return the list of display fields for the given table"""
        if columns == ["default"]:
            fields = self.sorted_display_fields()

            if "namespace" not in fields:
                fields.insert(0, "namespace")
        elif columns == ["*"]:
            fields = self.sorted_display_fields(getall=True)
        else:
            fields = [f for f in columns if f in self.fields]

        return fields

    def get_phy_table_for_table(self) -> str:
        """Return the underlying physical table for this logical table"""
        return self._all_schemas.get_phy_table_for_table(self._table)

    def get_raw_schema(self):
        return self._all_schemas.get_raw_schema(self._table)

    def get_arrow_schema(self):
        return self._all_schemas.get_arrow_schema(self._table)

    def get_parent_fields(self, field):
        return self._all_schemas.get_parent_fields(self._table, field)
