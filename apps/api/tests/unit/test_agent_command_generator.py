"""
Unit Tests for Agent Docker Command Generator
Tests command generation for multi-source DB merge, database dialects, collision handling, shell escaping, and multi-platform syntax.
"""

import uuid
import pytest
import app.main
from app.modules.agents.agents_command_generator import AgentCommandGenerator
from app.modules.agents.agents_models import Agent
from app.modules.sources.sources_models import DataSource




def test_command_generator_multi_source_merge():
    """
    Test generating Docker commands for merging 2 source databases (Postgres + MySQL)
    into 1 destination database (Postgres).
    """
    agent = Agent(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Production Multi-Source Merge Agent",
        agent_identifier="agent_merge_prod_01",
        version="1.2.0",
        status="offline",
    )

    src1 = DataSource(
        id=uuid.uuid4(),
        agent_id=agent.id,
        name="Legacy Postgres DB",
        type="postgresql",
        role="source",
        identifier="legacy_pg",
    )
    src2 = DataSource(
        id=uuid.uuid4(),
        agent_id=agent.id,
        name="Inventory MySQL DB",
        type="mysql",
        role="source",
        identifier="inventory_mysql",
    )
    dest = DataSource(
        id=uuid.uuid4(),
        agent_id=agent.id,
        name="Consolidated Postgres DWH",
        type="postgresql",
        role="target",
        identifier="dwh_postgres",
    )

    data_sources = [src1, src2, dest]
    token = "ag_live_test_token_12345"

    result = AgentCommandGenerator.generate_command_payload(
        agent=agent,
        data_sources=data_sources,
        raw_token=token,
    )

    # 1. Verify required keys
    assert "docker_command" in result
    assert "docker_command_powershell" in result
    assert "docker_command_oneline" in result
    assert "env_template" in result
    assert "environment_variables" in result

    env_vars = result["environment_variables"]

    # 2. Verify Core Agent env vars
    assert env_vars["AGENT_TOKEN"] == token
    assert env_vars["AGENT_ID"] == str(agent.id)
    assert env_vars["AGENT_IDENTIFIER"] == "agent_merge_prod_01"
    assert env_vars["AGENT_VERSION"] == "1.2.0"
    assert "BACKEND_URL" in env_vars

    # 3. Verify Source 1 (Postgres)
    assert env_vars["SRC_LEGACY_PG_TYPE"] == "postgresql"
    assert "postgresql://postgres:<SRC_LEGACY_PG_PASSWORD>@host.docker.internal:5432/<SRC_LEGACY_PG_NAME>" == env_vars["SRC_LEGACY_PG_URL"]

    # 4. Verify Source 2 (MySQL)
    assert env_vars["SRC_INVENTORY_MYSQL_TYPE"] == "mysql"
    assert "mysql+pymysql://root:<SRC_INVENTORY_MYSQL_PASSWORD>@host.docker.internal:3306/<SRC_INVENTORY_MYSQL_NAME>" == env_vars["SRC_INVENTORY_MYSQL_URL"]

    # 5. Verify Destination (Postgres)
    assert env_vars["DEST_DWH_POSTGRES_TYPE"] == "postgresql"
    assert "postgresql://postgres:<DEST_DWH_POSTGRES_PASSWORD>@host.docker.internal:5432/<DEST_DWH_POSTGRES_NAME>" == env_vars["DEST_DWH_POSTGRES_URL"]
    assert env_vars["DEST_DB_URL"] == env_vars["DEST_DWH_POSTGRES_URL"]

    # 6. Verify Bash command syntax
    bash_cmd = result["docker_command"]
    assert "docker run -d \\" in bash_cmd
    assert "--name agent_agent_merge_prod_01 \\" in bash_cmd
    assert "--add-host=host.docker.internal:host-gateway \\" in bash_cmd
    assert f'-e AGENT_TOKEN="{token}" \\' in bash_cmd
    assert '-e SRC_LEGACY_PG_URL=' in bash_cmd
    assert '-e SRC_INVENTORY_MYSQL_URL=' in bash_cmd
    assert '-e DEST_DWH_POSTGRES_URL=' in bash_cmd

    # 7. Verify PowerShell command syntax
    ps_cmd = result["docker_command_powershell"]
    assert "docker run -d `" in ps_cmd
    assert f'-e AGENT_TOKEN="{token}" `' in ps_cmd

    # 8. Verify Single-line command
    oneline_cmd = result["docker_command_oneline"]
    assert "\n" not in oneline_cmd
    assert f'-e AGENT_TOKEN="{token}"' in oneline_cmd

    # 9. Verify .env template
    env_tpl = result["env_template"]
    assert f"AGENT_TOKEN={token}" in env_tpl
    assert "SRC_LEGACY_PG_URL=" in env_tpl
    assert "SRC_INVENTORY_MYSQL_URL=" in env_tpl
    assert "DEST_DWH_POSTGRES_URL=" in env_tpl


def test_command_generator_mongo_and_mssql():
    """Test generating Docker commands with MongoDB and MSSQL database types."""
    agent = Agent(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Mongo MSSQL Agent",
        agent_identifier="agent_mongo_mssql",
        status="offline",
    )

    mongo_src = DataSource(
        id=uuid.uuid4(),
        agent_id=agent.id,
        name="Customer Mongo",
        type="mongodb",
        role="source",
        identifier="customer_mongo",
    )
    mssql_dest = DataSource(
        id=uuid.uuid4(),
        agent_id=agent.id,
        name="Enterprise MSSQL",
        type="mssql",
        role="target",
        identifier="enterprise_mssql",
    )

    result = AgentCommandGenerator.generate_command_payload(
        agent=agent,
        data_sources=[mongo_src, mssql_dest],
        raw_token="ag_live_token_mongo_mssql",
    )

    env_vars = result["environment_variables"]
    assert "mongodb://" in env_vars["SRC_CUSTOMER_MONGO_URL"]
    assert "mssql+pyodbc://" in env_vars["DEST_ENTERPRISE_MSSQL_URL"]
    assert env_vars["SOURCE_DB_URL"] == env_vars["SRC_CUSTOMER_MONGO_URL"]
    assert env_vars["DEST_DB_URL"] == env_vars["DEST_ENTERPRISE_MSSQL_URL"]


def test_command_generator_identifier_collision_handling():
    """
    Test that two data sources with identifiers normalizing to the same uppercase name
    (e.g., 'my-db' and 'my_db') do not overwrite each other and are assigned unique suffixes.
    """
    agent = Agent(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Collision Test Agent",
        agent_identifier="agent_collision",
        status="offline",
    )

    src1 = DataSource(
        id=uuid.uuid4(),
        agent_id=agent.id,
        name="Source DB 1",
        type="postgresql",
        role="source",
        identifier="my-db",
    )
    src2 = DataSource(
        id=uuid.uuid4(),
        agent_id=agent.id,
        name="Source DB 2",
        type="mysql",
        role="source",
        identifier="my_db",
    )

    result = AgentCommandGenerator.generate_command_payload(
        agent=agent,
        data_sources=[src1, src2],
        raw_token="ag_live_collision_test",
    )

    env_vars = result["environment_variables"]
    assert "SRC_MY_DB_URL" in env_vars
    assert "SRC_MY_DB_2_URL" in env_vars
    assert env_vars["SRC_MY_DB_TYPE"] == "postgresql"
    assert env_vars["SRC_MY_DB_2_TYPE"] == "mysql"


def test_command_generator_shell_escaping():
    """
    Test that special characters in tokens or configuration values
    are safely escaped in bash and powershell commands.
    """
    agent = Agent(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Special \"Agent\" $Test",
        agent_identifier="agent_special",
        status="offline",
    )

    result = AgentCommandGenerator.generate_command_payload(
        agent=agent,
        data_sources=[],
        raw_token="token_with_\"quote\"_and_$dollar_and_`backtick`",
    )

    bash_cmd = result["docker_command"]
    ps_cmd = result["docker_command_powershell"]

    # In bash: double quotes, dollar signs, and backticks should be escaped
    assert '\\"quote\\"' in bash_cmd
    assert '\\$dollar' in bash_cmd
    assert '\\`backtick\\`' in bash_cmd

    # In powershell: double quotes and backticks should be escaped
    assert '`"quote`"' in ps_cmd
    assert '`$dollar' in ps_cmd
    assert '``backtick``' in ps_cmd
