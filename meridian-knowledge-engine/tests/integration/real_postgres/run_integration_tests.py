#!/usr/bin/env python
"""
Run integration tests against real PostgreSQL + pgvector.

Prerequisites:
1. docker-compose up -d postgres redis
2. Wait for health checks to pass
3. Run this script

Usage:
    python tests/integration/real_postgres/run_integration_tests.py
    python tests/integration/real_postgres/run_integration_tests.py --verbose
    python tests/integration/real_postgres/run_integration_tests.py --test TestFullIngestionPipeline
"""
import argparse
import subprocess
import sys
import time
import os
from pathlib import Path


def run_command(cmd, capture=False, env=None):
    """Run a shell command."""
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        env={**os.environ, **(env or {})}
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def check_docker():
    """Check if Docker is available."""
    result = run_command(["docker", "version"], capture=True)
    if result.returncode != 0:
        print("ERROR: Docker not available")
        return False
    return True


def start_postgres():
    """Start PostgreSQL with pgvector using docker-compose."""
    print("\n=== Starting PostgreSQL with pgvector ===")
    
    # Check if already running
    result = run_command(
        ["docker", "ps", "--filter", "name=meridian-postgres", "--format", "{{.Names}}"],
        capture=True
    )
    if "meridian-postgres" in result.stdout:
        print("PostgreSQL already running")
        return True
    
    # Start postgres
    result = run_command([
        "docker-compose", "up", "-d", "postgres", "redis"
    ])
    if result.returncode != 0:
        print("Failed to start postgres")
        return False
    
    # Wait for health check
    print("Waiting for PostgreSQL to be healthy...")
    for i in range(30):
        result = run_command([
            "docker", "exec", "meridian-postgres", "pg_isready", "-U", "meridian", "-d", "meridian"
        ], capture=True)
        if result.returncode == 0:
            print("PostgreSQL is ready!")
            return True
        time.sleep(2)
        print(f"  Waiting... ({i+1}/30)")
    
    print("ERROR: PostgreSQL did not become healthy in time")
    return False


def run_tests(test_path=None, verbose=False, specific_test=None):
    """Run pytest with the integration tests."""
    print("\n=== Running Integration Tests ===")
    
    # Set test database URL
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://meridian:meridian@localhost:5432/meridian"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    
    cmd = [
        "python", "-m", "pytest",
        "tests/integration/real_postgres/test_full_pipeline.py",
        "-v",
        "--tb=short",
    ]
    
    if specific_test:
        cmd.extend(["-k", specific_test])
    
    if not verbose:
        cmd.append("--tb=line")
    
    # Run tests
    result = run_command(cmd)
    return result.returncode == 0


def stop_postgres():
    """Stop PostgreSQL (optional)."""
    print("\n=== Stopping PostgreSQL ===")
    run_command(["docker-compose", "down"])


def main():
    parser = argparse.ArgumentParser(description="Run integration tests against real PostgreSQL")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--test", "-k", help="Run specific test (pytest -k pattern)")
    parser.add_argument("--no-stop", action="store_true", help="Don't stop postgres after tests")
    parser.add_argument("--no-start", action="store_true", help="Don't start postgres (assume running)")
    args = parser.parse_args()
    
    # Check Docker
    if not check_docker():
        sys.exit(1)
    
    # Start PostgreSQL
    if not args.no_start:
        if not start_postgres():
            print("Failed to start PostgreSQL")
            sys.exit(1)
    
    # Wait a bit for pgvector extension to be ready
    time.sleep(2)
    
    # Run tests
    success = run_tests(
        test_path=args.test,
        verbose=args.verbose,
        specific_test=args.test
    )
    
    # Stop PostgreSQL
    if not args.no_stop:
        stop_postgres()
    
    if success:
        print("\n✅ All integration tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some integration tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()