# TODO: Microsoft SQL Server connector — not yet implemented.
# When ready, implement MySQLConnector-style class using:
#   - Driver: sqlalchemy + aioodbc (or asyncio-compatible pyodbc wrapper)
#   - Register with: @ConnectorFactory.register("mssql") / @ConnectorFactory.register("sqlserver")
#   - Query information_schema.TABLES and information_schema.COLUMNS (same as MySQL)
#   - Remember to add "aioodbc" or equivalent to pyproject.toml dependencies.
