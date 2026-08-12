# Docker Agent Application

This application is the standalone Docker Agent runner for customer-on-premise data migration operations.

## Architecture
- Runs as an autonomous Docker container on customer networks.
- Connects securely to the Platform API control plane.
- Reuses core connector and loader abstractions for isolated database operations.

> Note: Operational agent logic (polling, job execution, authentication) will be implemented in subsequent phases.
