# Data Connectors Documentation

The `connectors` package (`apps/api/packages/connectors`) provides unified data access abstractions for reading schemas, getting samples, and streaming data batches from multiple storage engines.

## Connectors Supported
- **PostgreSQL**: `PostgresConnector`
- **MSSQL**: `MSSQLConnector`
- **CSV**: `CSVConnector`
- **Excel**: `ExcelConnector`

## Connector Abstraction Interface

```python
class DataConnector(ABC):
    def test_connection(self) -> bool: ...
    def get_tables(self) -> List[str]: ...
    def get_schema(self, table_name: str) -> TableSchema: ...
    def get_row_count(self, table_name: str) -> int: ...
    def get_sample(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]: ...
    def stream_batches(self, table_name: str, batch_size: int = 10_000) -> Generator: ...
```
