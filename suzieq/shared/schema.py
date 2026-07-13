###
# Defines the schema class and the associated methods for suzieq tables.
###
import os
import logging
import json
from typing import List, Dict, Optional
import pyarrow as pa

# Initialize logger
logger = logging.getLogger(__name__)

class Schema:
    '''Schema class holding schemas of all tables and providing operations on them'''

    def __init__(self, schema_dir: str):
        """
        Initialize the schema manager by loading schemas from the directory.
        :param schema_dir: Directory containing the schema files.
        """
        self._init_schemas(schema_dir)
        if not self._schema:
            raise ValueError("Unable to load schemas")

    def _init_schemas(self, schema_dir: str):
        """Load the schema definitions from schema files in the specified directory"""
        schemas = {}
        phy_tables = {}
        types = {}

        # Ensure schema directory exists
        if not (schema_dir and os.path.exists(schema_dir)):
            logger.error("Schema directory %s does not exist", schema_dir)
            raise ValueError(f"Schema directory {schema_dir} does not exist")

        # Traverse schema files in directory
        for root, _, files in os.walk(schema_dir):
            for topic in files:
                if not topic.endswith(".avsc"):
                    continue
                with open(os.path.join(root, topic), "r") as f:
                    data = json.loads(f.read())
                    table = data["name"]
                    schemas[table] = data["fields"]
                    types[table] = data.get('recordType', 'record')
                    phy_tables[table] = data.get("physicalTable", table)

        self._schema = schemas
        self._phy_tables = phy_tables
        self._types = types

    def tables(self) -> List[str]:
        '''Return a list of tables for which schemas are available'''
        return list(self._schema.keys())

    def fields_for_table(self, table: str) -> List[str]:
        '''Return a list of fields for a given table'''
        return [f['name'] for f in self._schema[table]]

    def get_raw_schema(self, table: str) -> Dict:
        '''Return the raw schema for the given table'''
        return self._schema[table]

    def field_for_table(self, table: str, field: str) -> Optional[Dict]:
        '''Return details about a specific field in the table, or None if it doesn't exist'''
        for f in self._schema[table]:
            if f['name'] == field:
                return f
        return None

    def type_for_table(self, table: str) -> str:
        '''Return the table type (e.g., counter, record, derived)'''
        return self._types[table]

    def key_fields_for_table(self, table: str) -> List[str]:
        '''Return key fields for the given table'''
        return self._sort_fields_for_table(table, 'key')

    def augmented_fields_for_table(self, table: str, fields: List[str], recurse: int = 0) -> List[str]:
        '''Return augmented fields for the given table, resolving dependencies if needed'''
        all_aug_fields = [x['name'] for x in self._schema.get(table, []) if 'depends' in x]
        aug_fields = [x for x in all_aug_fields if not fields or x in fields]
        
        if recurse > 0:
            all_parents = []
            for f in aug_fields:
                all_parents += self.get_parent_fields(table, f)
            if all_parents:
                aug_fields += self.augmented_fields_for_table(table, all_parents, recurse - 1)
        
        return aug_fields

    def sorted_display_fields_for_table(self, table: str, getall: bool = False) -> List[str]:
        '''Return sorted list of default display fields for the table'''
        display_fields = self._sort_fields_for_table(table, 'display', getall)
        return [f for f in display_fields if not self.field_for_table(table, f).get('suppress', False)]

    def _sort_fields_for_table(self, table: str, tag: str, getall: bool = False) -> List[str]:
        '''Sort fields for the table based on a tag, optionally returning all fields'''
        fields = self.fields_for_table(table)
        field_weights = {}
        for f_name in fields:
            field = self.field_for_table(table, f_name)
            if field and field.get(tag) is not None:
                field_weights[f_name] = field[tag]
            elif getall:
                field_weights[f_name] = 1000
        return list(sorted(field_weights.keys(), key=lambda x: field_weights[x]))

    def array_fields_for_table(self, table: str) -> List[str]:
        '''Return a list of array fields in the table'''
        return [f['name'] for f in self._schema[table] if isinstance(f['type'], dict) and f['type'].get('type') == 'array']

    def get_phy_table_for_table(self, table: str) -> Optional[str]:
        '''Return the physical table for the logical table'''
        return self._phy_tables.get(table, table)

    def get_partition_columns_for_table(self, table: str) -> List[str]:
        '''Return the partition columns for the table'''
        return self._sort_fields_for_table(table, 'partition')

    def get_arrow_schema(self, table: str) -> pa.Schema:
        '''Convert the AVRO schema to a PyArrow schema'''
        avro_sch = self._schema.get(table)
        if not avro_sch:
            raise AttributeError(f"No schema found for {table}")

        map_type = {
            "string": pa.string(),
            "long": pa.int64(),
            "int": pa.int32(),
            "double": pa.float64(),
            "float": pa.float32(),
            "timestamp": pa.timestamp('ns'),
            "boolean": pa.bool_(),
            "array.string": pa.list_(pa.string()),
            "array.long": pa.list_(pa.int64()),
            "array.float": pa.list_(pa.float32()),
        }

        arrow_fields = [
            pa.field(f["name"], map_type.get(f["type"], pa.string())) for f in avro_sch if "depends" not in f
        ]

        return pa.schema(arrow_fields)

    def get_parent_fields(self, table: str, field: str) -> List[str]:
        '''Return the parent fields for an augmented field in the table'''
        avro_sch = self._schema.get(table)
        if not avro_sch:
            raise AttributeError(f"No schema found for {table}")

        for f in avro_sch:
            if f['name'] == field and 'depends' in f:
                return f['depends'].split()
        return []


class SchemaForTable:
    '''Class supporting operations on the schema for a specific table'''

    def __init__(self, table: str, schema: Schema = None, schema_dir: str = None):
        '''Initialize SchemaForTable with an existing Schema instance or schema directory'''
        if schema:
            if isinstance(schema, Schema):
                self._all_schemas = schema
            else:
                raise ValueError("Invalid schema object")
        else:
            self._all_schemas = Schema(schema_dir=schema_dir)
        
        self._table = table
        if table not in self._all_schemas.tables():
            raise ValueError(f"Unknown table {table}, no schema found for it")

    @property
    def type(self) -> str:
        '''Return the type of the table'''
        return self._all_schemas.type_for_table(self._table)

    @property
    def version(self) -> str:
        '''Return the version of the schema'''
        return self._all_schemas.field_for_table(self._table, 'sqvers')['default']

    @property
    def fields(self) -> List[str]:
        '''Return the fields for the table'''
        return self._all_schemas.fields_for_table(self._table)

    @property
    def array_fields(self) -> List[str]:
        '''Return the array fields for the table'''
        return self._all_schemas.array_fields_for_table(self._table)

    def get_phy_table(self) -> str:
        '''Return the physical table backing this logical table'''
        return self._all_schemas.get_phy_table_for_table(self._table)

    def get_partition_columns(self) -> List[str]:
        '''Return the partition columns for the table'''
        return self._all_schemas.get_partition_columns_for_table(self._table)

    def key_fields(self) -> List[str]:
        '''Return the key fields for the table'''
        return self._all_schemas.key_fields_for_table(self._table)

    def get_augmented_fields(self, fields: List[str]) -> List[str]:
        '''Return augmented fields for the table'''
        MAX_AUGMENTED_RECURSE = 2
        return self._all_schemas.augmented_fields_for_table(self._table, fields, MAX_AUGMENTED_RECURSE)

    def sorted_display_fields(self, getall: bool = False) -> List[str]:
        '''Return sorted list of display fields for the table'''
        return self._all_schemas.sorted_display_fields_for_table(self._table, getall)

    def field(self, field: str) -> Optional[Dict]:
        '''Return details for a specific field in the table'''
        return self._all_schemas.field_for_table(self._table, field)

    def get_display_fields(self) -> List[str]:
        '''Return the default display fields for the table'''
        return self.sorted_display_fields(getall=False)
