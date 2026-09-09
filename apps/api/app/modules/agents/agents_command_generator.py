"""
Agent Docker Command Generator Service
Constructs copy-paste ready Docker run commands (Bash, PowerShell, Single-line)
and .env file templates with credential placeholders for multi-source to destination migration agents.
"""

import re
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.modules.agents.agents_models import Agent


class AgentCommandGenerator:
    """Service to generate parameterized Docker commands and environment configurations for agents."""

    @staticmethod
    def _sanitize_identifier(identifier: str) -> str:
        """Converts an identifier to a clean UPPER_SNAKE_CASE string for environment variables."""
        cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", identifier.strip()).strip("_").upper()
        return cleaned or "DB"

    @staticmethod
    def _escape_bash(val: str) -> str:
        """Escapes special characters in string values for safe double-quoted Bash embedding."""
        return val.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")

    @staticmethod
    def _escape_powershell(val: str) -> str:
        """Escapes special characters in string values for safe double-quoted PowerShell embedding."""
        return val.replace("`", "``").replace('"', '`"').replace("$", "`$")

    @classmethod
    def _get_db_url_template(cls, db_type: str, prefix: str, clean_id: str = "") -> str:
        """
        Returns connection URL template string for a given database dialect.
        EVERY connection detail (host, port, username, password, database name)
        is a generic placeholder here -- this backend never knows or stores a
        user's actual connection info. The frontend fills these in locally,
        in the browser only, using values the user typed into the connection
        form. Only the password placeholder is left for the user to fill in
        manually after copying the command (host/port/username/database are
        auto-substituted by the frontend before the command is ever shown).
        """
        db_type_lower = db_type.lower()
        tag_prefix = f"{prefix}_{clean_id}" if clean_id else prefix
        host_placeholder = f"<{tag_prefix}_HOST>"
        port_placeholder = f"<{tag_prefix}_PORT>"
        user_placeholder = f"<{tag_prefix}_USER>"
        pwd_placeholder = f"<{tag_prefix}_PASSWORD>"
        db_placeholder = f"<{tag_prefix}_NAME>"

        if db_type_lower in ("postgresql", "postgres"):
            return f"postgresql://{user_placeholder}:{pwd_placeholder}@{host_placeholder}:{port_placeholder}/{db_placeholder}"
        elif db_type_lower in ("mysql", "mariadb"):
            return f"mysql+pymysql://{user_placeholder}:{pwd_placeholder}@{host_placeholder}:{port_placeholder}/{db_placeholder}"
        elif db_type_lower in ("mongodb", "mongo"):
            return f"mongodb://{user_placeholder}:{pwd_placeholder}@{host_placeholder}:{port_placeholder}/{db_placeholder}?authSource=admin"
        elif db_type_lower in ("mssql", "sqlserver"):
            return f"mssql+pyodbc://{user_placeholder}:{pwd_placeholder}@{host_placeholder}:{port_placeholder}/{db_placeholder}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
        elif db_type_lower in ("csv", "excel", "parquet"):
            return f"</path/to/{tag_prefix.lower()}_files>"
        else:
            return f"{db_type_lower}://{user_placeholder}:{pwd_placeholder}@{host_placeholder}:{port_placeholder}/{db_placeholder}"

    @classmethod
    def generate_command_payload(
        cls,
        agent: Agent,
        data_sources: Optional[List[Any]] = None,
        raw_token: Optional[str] = None,
        backend_url: Optional[str] = None,
        docker_image: Optional[str] = None,
    ) -> Dict[str, Any]:
        r"""
        Builds complete Docker command payload including:
        - docker_command (Bash multi-line with \)
        - docker_command_powershell (PowerShell multi-line with `)
        - docker_command_oneline (Single-line)
        - env_template (.env file content)
        - environment_variables (Dictionary map)
        """
        token_str = raw_token if raw_token else "<YOUR_AGENT_API_TOKEN>"
        resolved_backend_url = backend_url or settings.BACKEND_URL
        resolved_image = docker_image or settings.AGENT_DOCKER_IMAGE
        container_name = f"agent_{re.sub(r'[^a-zA-Z0-9_-]', '_', agent.agent_identifier).lower()}"

        sources_list = data_sources if data_sources is not None else (agent.data_sources or [])

        env_vars: Dict[str, str] = {
            "BACKEND_URL": resolved_backend_url,
            "AGENT_TOKEN": token_str,
            "AGENT_ID": str(agent.id),
            "AGENT_IDENTIFIER": agent.agent_identifier,
            "AGENT_VERSION": agent.version or "1.0.0",
        }

        source_count = 0
        target_count = 0
        single_source_url: Optional[str] = None
        single_target_url: Optional[str] = None

        used_prefixes: set[str] = set()

        for ds in sources_list:
            role = getattr(ds, "role", "source").lower()
            identifier = getattr(ds, "identifier", "db")
            ds_type = getattr(ds, "type", "postgresql")
            clean_id = cls._sanitize_identifier(identifier)

            if role in ("source", "both"):
                source_count += 1
                base_prefix = f"SRC_{clean_id}"
                prefix = base_prefix
                counter = 2
                while prefix in used_prefixes:
                    prefix = f"{base_prefix}_{counter}"
                    counter += 1
                used_prefixes.add(prefix)

                url_template = cls._get_db_url_template(ds_type, prefix)
                env_vars[f"{prefix}_TYPE"] = ds_type
                env_vars[f"{prefix}_URL"] = url_template

                if source_count == 1:
                    single_source_url = url_template
                else:
                    single_source_url = None

            if role in ("target", "both"):
                target_count += 1
                base_prefix = f"DEST_{clean_id}"
                prefix = base_prefix
                counter = 2
                while prefix in used_prefixes:
                    prefix = f"{base_prefix}_{counter}"
                    counter += 1
                used_prefixes.add(prefix)

                url_template = cls._get_db_url_template(ds_type, prefix)
                env_vars[f"{prefix}_TYPE"] = ds_type
                env_vars[f"{prefix}_URL"] = url_template

                if target_count == 1:
                    single_target_url = url_template
                else:
                    single_target_url = None

        # Add single source / single destination convenience aliases if exactly 1 present
        if single_source_url:
            env_vars["SOURCE_DB_URL"] = single_source_url

        if single_target_url:
            env_vars["DEST_DB_URL"] = single_target_url

        # 1. Build Bash command (safely escaped)
        bash_lines = [
            "docker run -d \\",
            f"  --name {container_name} \\",
            "  --restart on-failure \\",
            "  --add-host=host.docker.internal:host-gateway \\",
        ]
        for k, v in env_vars.items():
            bash_lines.append(f'  -e {k}="{cls._escape_bash(v)}" \\')
        bash_lines.append(f"  {resolved_image}")
        docker_command_bash = "\n".join(bash_lines)

        # 2. Build PowerShell command (safely escaped)
        ps_lines = [
            "docker run -d `",
            f"  --name {container_name} `",
            "  --restart on-failure `",
            "  --add-host=host.docker.internal:host-gateway `",
        ]
        for k, v in env_vars.items():
            ps_lines.append(f'  -e {k}="{cls._escape_powershell(v)}" `')
        ps_lines.append(f"  {resolved_image}")
        docker_command_powershell = "\n".join(ps_lines)

        # 3. Build Single-line command
        env_flags = " ".join([f'-e {k}="{cls._escape_bash(v)}"' for k, v in env_vars.items()])
        docker_command_oneline = (
            f"docker run -d --name {container_name} --restart on-failure "
            f"--add-host=host.docker.internal:host-gateway {env_flags} {resolved_image}"
        )

        # 4. Build .env file template
        core_keys = ["BACKEND_URL", "AGENT_TOKEN", "AGENT_ID", "AGENT_IDENTIFIER", "AGENT_VERSION"]
        env_lines = [
            "# ========================================================",
            "# Docker Agent Environment Configuration",
            f"# Agent Name: {agent.name}",
            f"# Agent Identifier: {agent.agent_identifier}",
            f"# Agent ID: {agent.id}",
            "# ========================================================",
            "",
            "# Core Control Plane Settings",
        ]
        for k in core_keys:
            if k in env_vars:
                env_lines.append(f"{k}={env_vars[k]}")

        db_keys = [k for k in env_vars if k not in core_keys]
        if db_keys:
            env_lines.append("")
            env_lines.append("# Database Connections & Credentials (Fill before running agent)")
            for k in db_keys:
                env_lines.append(f"{k}={env_vars[k]}")

        env_template = "\n".join(env_lines)

        return {
            "docker_command": docker_command_bash,
            "docker_command_powershell": docker_command_powershell,
            "docker_command_oneline": docker_command_oneline,
            "env_template": env_template,
            "environment_variables": env_vars,
        }
