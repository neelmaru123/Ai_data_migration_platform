"""
Seed Default Admin User Script
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.modules.agents.agents_models  # noqa: F401
import app.modules.execution.execution_models  # noqa: F401
import app.modules.metadata.metadata_models  # noqa: F401
import app.modules.sources.sources_models  # noqa: F401
import app.modules.migration_plans.migration_plans_models  # noqa: F401
import app.modules.users.users_models  # noqa: F401

from app.core.db import AsyncSessionLocal
from app.modules.users.users_services import UserService
from app.modules.users.users_schemas import UserRegister

async def main():
    async with AsyncSessionLocal() as session:
        try:
            user = await UserService.create_user(
                session, 
                UserRegister(
                    email="admin@example.com", 
                    password="Password123!", 
                    name="Admin User"
                )
            )
            print(f"Admin user successfully created! (ID: {user.id}, Email: {user.email})")
        except Exception as e:
            print(f"User creation status: {e}")

if __name__ == "__main__":
    asyncio.run(main())
