#!/usr/bin/env python3
"""
Utility script to run database migrations
"""
import sys
import os
from alembic.config import Config
from alembic import command

def main():
    """Run database migrations"""
    alembic_cfg = Config("alembic.ini")
    
    print("Running database migrations...")
    try:
        command.upgrade(alembic_cfg, "head")
        print("✓ Migrations completed successfully")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
