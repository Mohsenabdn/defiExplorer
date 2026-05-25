# catalog.py
import json
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime
from typing import Dict


class Catalog:
    """
    A catalog class that generates schemas from Parquet files using PyArrow.
    Preserves column order and includes detailed field information.
    """

    def generate_schema_from_parquet(
            self, parquet_path: str, schema_path: str
    ):
        """
        Generate a schema from a Parquet file using PyArrow.

        Parameters:
        -----------
        parquet_path : str
            Full path to the Parquet file
        schema_name : str
            Full path to the schema name
        """
        parquet_path = Path(parquet_path).resolve()

        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

        # Read Parquet schema
        schema = pq.read_schema(parquet_path)

        # Build schema dictionary (preserving column order from schema.names)
        schema_dict = {
            "file_path": str(parquet_path),
            "file_name": parquet_path.name,
            "format": "parquet",
            "generated_at": datetime.now().isoformat(),
            "fields": []
        }

        # Extract field information in order (preserving Parquet column order)
        for field_name in schema.names:  # schema.names preserves order
            field = schema.field(field_name)

            field_info = {
                "name": field_name,
                "type": str(field.type),
                "nullable": field.nullable,
                "physical_type": self._get_physical_type(field.type),
                "logical_type": self._get_logical_type(field.type),
            }

            # Add metadata if present
            if field.metadata:
                field_info["metadata"] = dict(field.metadata)

            schema_dict["fields"].append(field_info)

        with open(schema_path, 'w') as f:
            json.dump(schema_dict, f, indent=2)

        print(f"✅ Schema saved to {schema_path}")
        print(f"   Columns: {len(schema_dict['fields'])} fields in order:\
{[f['name'] for f in schema_dict['fields']]}")

    def _get_physical_type(self, pyarrow_type) -> str:
        """Get the physical Parquet type."""
        type_str = str(pyarrow_type)

        # Map common PyArrow types to physical types
        if 'int32' in type_str:
            return 'INT32'
        elif 'int64' in type_str:
            return 'INT64'
        elif 'float' in type_str:
            return 'FLOAT'
        elif 'double' in type_str:
            return 'DOUBLE'
        elif 'string' in type_str:
            return 'BYTE_ARRAY'
        elif 'bool' in type_str:
            return 'BOOLEAN'
        elif 'timestamp' in type_str:
            return 'INT64'  # Timestamps are stored as INT64
        elif 'date' in type_str:
            return 'INT32'  # Dates are stored as INT32
        elif 'decimal' in type_str:
            return 'FIXED_LEN_BYTE_ARRAY'
        else:
            return 'UNKNOWN'

    def _get_logical_type(self, pyarrow_type) -> str:
        """Get the logical type annotation."""
        type_str = str(pyarrow_type)

        if 'timestamp' in type_str:
            return 'timestamp'
        elif 'date' in type_str:
            return 'date'
        elif 'decimal' in type_str:
            return 'decimal'
        elif 'string' in type_str:
            return 'string'
        elif 'int' in type_str:
            return 'integer'
        elif 'float' in type_str or 'double' in type_str:
            return 'float'
        elif 'bool' in type_str:
            return 'boolean'
        else:
            return 'unknown'

    def get_schema_summary(self, schema_path: str) -> Dict:
        """Load and summarize a saved schema."""
        with open(schema_path, 'r') as f:
            schema_dict = json.load(f)

        return {
            "file_name": schema_dict["file_name"],
            "num_columns": len(schema_dict["fields"]),
            "num_rows": schema_dict["metadata"]["num_rows"],
            "columns": [field["name"] for field in schema_dict["fields"]],
            "generated_at": schema_dict["generated_at"]
        }


def compare_schemas(schema1_path: str, schema2_path: str) -> Dict:
    """
    Compare two schema files to detect changes.

    Returns a dictionary with added, removed, and changed columns.
    """
    with open(schema1_path, 'r') as f:
        schema1 = json.load(f)

    with open(schema2_path, 'r') as f:
        schema2 = json.load(f)

    # Create dictionaries keyed by column name
    cols1 = {f["name"]: f for f in schema1["fields"]}
    cols2 = {f["name"]: f for f in schema2["fields"]}

    added = set(cols2.keys()) - set(cols1.keys())
    removed = set(cols1.keys()) - set(cols2.keys())

    # Find columns that changed type
    changed = {}
    for name in set(cols1.keys()) & set(cols2.keys()):
        if cols1[name]["type"] != cols2[name]["type"]:
            changed[name] = {
                "old_type": cols1[name]["type"],
                "new_type": cols2[name]["type"]
            }

    return {
        "added_columns": list(added),
        "removed_columns": list(removed),
        "changed_columns": changed,
        "has_changes": bool(added or removed or changed)
    }
