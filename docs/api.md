# API Endpoints Documentation

## Base URL
`/api/v1`

## Endpoints

- `GET /health`: Health check and service status.
- `GET /sources`: List registered data sources.
- `POST /sources`: Add a new database or file data source.
- `POST /datasets/{table_name}/profile`: Profile a dataset table/file.
- `POST /plans/generate`: Generate an AI transformation plan.
- `POST /jobs`: Submit a migration job.
- `GET /jobs/download-script/{plan_id}`: Download a self-contained local migration ZIP bundle.
