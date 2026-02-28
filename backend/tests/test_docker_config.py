"""Tests for Docker configuration files.

Validates structure and content of Dockerfiles, docker-compose files,
and .dockerignore files by reading them as text and parsing YAML.
Does NOT build or run Docker containers.
"""

from pathlib import Path

import yaml

# Project root is two levels up from backend/tests/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestBackendDockerfile:
    """Tests for backend/Dockerfile."""

    def test_dockerfile_exists(self) -> None:
        """Backend Dockerfile must exist."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        assert dockerfile.exists(), "backend/Dockerfile does not exist"

    def test_multi_stage_build(self) -> None:
        """Backend Dockerfile must use multi-stage build with builder and runtime stages."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        # Must have at least two FROM instructions (multi-stage)
        from_lines = [
            line for line in content.splitlines() if line.strip().upper().startswith("FROM")
        ]
        assert len(from_lines) >= 2, (
            f"Expected at least 2 FROM instructions for multi-stage build, found {len(from_lines)}"
        )

    def test_builder_stage_uses_python_312_slim(self) -> None:
        """Builder stage must use python:3.12-slim base image."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "python:3.12-slim" in content, "Builder stage must use python:3.12-slim"

    def test_builder_stage_named(self) -> None:
        """Builder stage must be named 'builder'."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        # Look for "FROM python:3.12-slim AS builder" (case-insensitive)
        lower_content = content.lower()
        assert "as builder" in lower_content, "Builder stage must be named 'builder'"

    def test_non_root_user(self) -> None:
        """Backend Dockerfile must create and use a non-root user 'appuser'."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "appuser" in content, "Dockerfile must reference non-root user 'appuser'"
        # Must have a USER instruction
        user_lines = [
            line
            for line in content.splitlines()
            if line.strip().upper().startswith("USER")
        ]
        assert len(user_lines) >= 1, "Dockerfile must have at least one USER instruction"

    def test_exposes_port_8000(self) -> None:
        """Backend Dockerfile must expose port 8000."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "EXPOSE 8000" in content, "Dockerfile must expose port 8000"

    def test_cmd_runs_uvicorn(self) -> None:
        """Backend Dockerfile CMD must run uvicorn."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "uvicorn" in content, "CMD must run uvicorn"
        assert "app.main:app" in content, "CMD must reference app.main:app"

    def test_healthcheck(self) -> None:
        """Backend Dockerfile must include a HEALTHCHECK instruction."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content, "Dockerfile must include HEALTHCHECK"
        assert "localhost:8000" in content, "Health check must target localhost:8000"

    def test_copies_requirements(self) -> None:
        """Backend Dockerfile must copy and install requirements.txt."""
        dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "requirements.txt" in content, "Dockerfile must reference requirements.txt"


class TestFrontendDockerfile:
    """Tests for frontend/Dockerfile."""

    def test_dockerfile_exists(self) -> None:
        """Frontend Dockerfile must exist."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        assert dockerfile.exists(), "frontend/Dockerfile does not exist"

    def test_multi_stage_build(self) -> None:
        """Frontend Dockerfile must use multi-stage build with at least 3 stages."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        from_lines = [
            line for line in content.splitlines() if line.strip().upper().startswith("FROM")
        ]
        assert len(from_lines) >= 3, (
            f"Expected at least 3 FROM instructions for multi-stage build, found {len(from_lines)}"
        )

    def test_uses_node_20_alpine(self) -> None:
        """Frontend Dockerfile must use node:20-alpine base image."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "node:20-alpine" in content, "Frontend Dockerfile must use node:20-alpine"

    def test_non_root_user(self) -> None:
        """Frontend Dockerfile must create and use a non-root user 'nextjs'."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "nextjs" in content, "Dockerfile must reference non-root user 'nextjs'"
        user_lines = [
            line
            for line in content.splitlines()
            if line.strip().upper().startswith("USER")
        ]
        assert len(user_lines) >= 1, "Dockerfile must have at least one USER instruction"

    def test_exposes_port_3000(self) -> None:
        """Frontend Dockerfile must expose port 3000."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "EXPOSE 3000" in content, "Dockerfile must expose port 3000"

    def test_production_env(self) -> None:
        """Frontend Dockerfile must set NODE_ENV=production."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "NODE_ENV" in content, "Dockerfile must set NODE_ENV"
        assert "production" in content, "NODE_ENV must be set to production"

    def test_telemetry_disabled(self) -> None:
        """Frontend Dockerfile must disable Next.js telemetry."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "NEXT_TELEMETRY_DISABLED" in content, "Dockerfile must disable Next.js telemetry"

    def test_cmd_runs_node_server(self) -> None:
        """Frontend Dockerfile CMD must run node server.js."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "server.js" in content, "CMD must reference server.js"

    def test_npm_run_build(self) -> None:
        """Frontend Dockerfile must run npm run build."""
        dockerfile = PROJECT_ROOT / "frontend" / "Dockerfile"
        content = dockerfile.read_text()
        assert "npm run build" in content, "Dockerfile must run npm run build"


class TestDockerCompose:
    """Tests for docker-compose.yml."""

    def test_file_exists(self) -> None:
        """docker-compose.yml must exist at project root."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml does not exist"

    def test_valid_yaml(self) -> None:
        """docker-compose.yml must be valid YAML."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        content = compose_file.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "docker-compose.yml must parse to a dict"

    def test_has_services(self) -> None:
        """docker-compose.yml must define services."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        assert "services" in parsed, "docker-compose.yml must have a 'services' key"

    def test_db_service(self) -> None:
        """docker-compose.yml must define a 'db' service with pgvector."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        services = parsed["services"]
        assert "db" in services, "Must have a 'db' service"
        db = services["db"]
        assert "image" in db, "db service must have an image"
        assert "pgvector" in db["image"], "db service must use pgvector image"

    def test_db_healthcheck(self) -> None:
        """db service must have a health check."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        db = parsed["services"]["db"]
        assert "healthcheck" in db, "db service must have a healthcheck"

    def test_db_volume(self) -> None:
        """db service must persist data with a volume."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        db = parsed["services"]["db"]
        assert "volumes" in db, "db service must have volumes"

    def test_redis_service(self) -> None:
        """docker-compose.yml must define a 'redis' service."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        services = parsed["services"]
        assert "redis" in services, "Must have a 'redis' service"
        redis = services["redis"]
        assert "image" in redis, "redis service must have an image"
        image = redis["image"]
        assert "redis" in image, "redis service must use a redis image"

    def test_redis_healthcheck(self) -> None:
        """redis service must have a health check."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        redis = parsed["services"]["redis"]
        assert "healthcheck" in redis, "redis service must have a healthcheck"

    def test_backend_service(self) -> None:
        """docker-compose.yml must define a 'backend' service."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        services = parsed["services"]
        assert "backend" in services, "Must have a 'backend' service"
        backend = services["backend"]
        assert "build" in backend, "backend service must have a build config"
        assert "depends_on" in backend, "backend service must have depends_on"

    def test_backend_depends_on_db_and_redis(self) -> None:
        """backend service must depend on db and redis."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        backend = parsed["services"]["backend"]
        depends_on = backend["depends_on"]
        # Our compose uses dict-style depends_on with conditions
        assert isinstance(depends_on, dict), "depends_on must be a dict with conditions"
        dep_names = list(depends_on.keys())
        assert "db" in dep_names, "backend must depend on db"
        assert "redis" in dep_names, "backend must depend on redis"

    def test_backend_environment(self) -> None:
        """backend service must have environment variables for DATABASE_URL and REDIS_URL."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        backend = parsed["services"]["backend"]
        assert "environment" in backend, "backend service must have environment vars"
        env = backend["environment"]
        # Our compose uses dict-style environment
        assert isinstance(env, dict), "environment must be a dict"
        env_keys = list(env.keys())
        assert "DATABASE_URL" in env_keys, "backend must have DATABASE_URL env var"
        assert "REDIS_URL" in env_keys, "backend must have REDIS_URL env var"

    def test_frontend_service(self) -> None:
        """docker-compose.yml must define a 'frontend' service."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        services = parsed["services"]
        assert "frontend" in services, "Must have a 'frontend' service"
        frontend = services["frontend"]
        assert "build" in frontend, "frontend service must have a build config"
        assert "depends_on" in frontend, "frontend service must have depends_on"

    def test_frontend_depends_on_backend(self) -> None:
        """frontend service must depend on backend."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        frontend = parsed["services"]["frontend"]
        depends_on = frontend["depends_on"]
        # Our compose uses dict-style depends_on with conditions
        assert isinstance(depends_on, dict), "depends_on must be a dict with conditions"
        dep_names = list(depends_on.keys())
        assert "backend" in dep_names, "frontend must depend on backend"

    def test_frontend_exposes_port_3000(self) -> None:
        """frontend service must expose port 3000."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        frontend = parsed["services"]["frontend"]
        assert "ports" in frontend, "frontend service must expose ports"
        ports_str = str(frontend["ports"])
        assert "3000" in ports_str, "frontend must expose port 3000"

    def test_named_volumes(self) -> None:
        """docker-compose.yml must define named volumes postgres_data and redis_data."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        assert "volumes" in parsed, "docker-compose.yml must have a top-level 'volumes' key"
        volumes = parsed["volumes"]
        assert "postgres_data" in volumes, "Must define postgres_data volume"
        assert "redis_data" in volumes, "Must define redis_data volume"


class TestDockerComposeDev:
    """Tests for docker-compose.dev.yml."""

    def test_file_exists(self) -> None:
        """docker-compose.dev.yml must exist at project root."""
        compose_file = PROJECT_ROOT / "docker-compose.dev.yml"
        assert compose_file.exists(), "docker-compose.dev.yml does not exist"

    def test_valid_yaml(self) -> None:
        """docker-compose.dev.yml must be valid YAML."""
        compose_file = PROJECT_ROOT / "docker-compose.dev.yml"
        content = compose_file.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "docker-compose.dev.yml must parse to a dict"

    def test_backend_volume_mount(self) -> None:
        """Dev backend must mount local code for live reload."""
        compose_file = PROJECT_ROOT / "docker-compose.dev.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        services = parsed.get("services", {})
        assert "backend" in services, "dev compose must have backend service"
        backend = services["backend"]
        assert "volumes" in backend, "dev backend must have volume mounts"
        volumes_str = str(backend["volumes"])
        assert "./backend" in volumes_str, "dev backend must mount ./backend"

    def test_backend_reload_command(self) -> None:
        """Dev backend must use uvicorn --reload."""
        compose_file = PROJECT_ROOT / "docker-compose.dev.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        backend = parsed["services"]["backend"]
        assert "command" in backend, "dev backend must override command"
        command_str = str(backend["command"])
        assert "--reload" in command_str, "dev backend must use --reload"

    def test_frontend_volume_mount(self) -> None:
        """Dev frontend must mount local code for hot reload."""
        compose_file = PROJECT_ROOT / "docker-compose.dev.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        services = parsed.get("services", {})
        assert "frontend" in services, "dev compose must have frontend service"
        frontend = services["frontend"]
        assert "volumes" in frontend, "dev frontend must have volume mounts"
        volumes_str = str(frontend["volumes"])
        assert "./frontend" in volumes_str, "dev frontend must mount ./frontend"

    def test_frontend_dev_command(self) -> None:
        """Dev frontend must use npm run dev."""
        compose_file = PROJECT_ROOT / "docker-compose.dev.yml"
        parsed = yaml.safe_load(compose_file.read_text())
        frontend = parsed["services"]["frontend"]
        assert "command" in frontend, "dev frontend must override command"
        command_str = str(frontend["command"])
        assert "npm run dev" in command_str, "dev frontend must use npm run dev"


class TestDockerignore:
    """Tests for .dockerignore files."""

    def test_backend_dockerignore_exists(self) -> None:
        """backend/.dockerignore must exist."""
        dockerignore = PROJECT_ROOT / "backend" / ".dockerignore"
        assert dockerignore.exists(), "backend/.dockerignore does not exist"

    def test_backend_dockerignore_excludes_venv(self) -> None:
        """backend/.dockerignore must exclude .venv."""
        dockerignore = PROJECT_ROOT / "backend" / ".dockerignore"
        content = dockerignore.read_text()
        assert ".venv" in content, "backend/.dockerignore must exclude .venv"

    def test_backend_dockerignore_excludes_pycache(self) -> None:
        """backend/.dockerignore must exclude __pycache__."""
        dockerignore = PROJECT_ROOT / "backend" / ".dockerignore"
        content = dockerignore.read_text()
        assert "__pycache__" in content, "backend/.dockerignore must exclude __pycache__"

    def test_backend_dockerignore_excludes_git(self) -> None:
        """backend/.dockerignore must exclude .git."""
        dockerignore = PROJECT_ROOT / "backend" / ".dockerignore"
        content = dockerignore.read_text()
        assert ".git" in content, "backend/.dockerignore must exclude .git"

    def test_backend_dockerignore_excludes_coverage(self) -> None:
        """backend/.dockerignore must exclude .coverage."""
        dockerignore = PROJECT_ROOT / "backend" / ".dockerignore"
        content = dockerignore.read_text()
        assert ".coverage" in content, "backend/.dockerignore must exclude .coverage"

    def test_frontend_dockerignore_exists(self) -> None:
        """frontend/.dockerignore must exist."""
        dockerignore = PROJECT_ROOT / "frontend" / ".dockerignore"
        assert dockerignore.exists(), "frontend/.dockerignore does not exist"

    def test_frontend_dockerignore_excludes_node_modules(self) -> None:
        """frontend/.dockerignore must exclude node_modules."""
        dockerignore = PROJECT_ROOT / "frontend" / ".dockerignore"
        content = dockerignore.read_text()
        assert "node_modules" in content, "frontend/.dockerignore must exclude node_modules"

    def test_frontend_dockerignore_excludes_git(self) -> None:
        """frontend/.dockerignore must exclude .git."""
        dockerignore = PROJECT_ROOT / "frontend" / ".dockerignore"
        content = dockerignore.read_text()
        assert ".git" in content, "frontend/.dockerignore must exclude .git"

    def test_frontend_dockerignore_excludes_next(self) -> None:
        """frontend/.dockerignore must exclude .next."""
        dockerignore = PROJECT_ROOT / "frontend" / ".dockerignore"
        content = dockerignore.read_text()
        assert ".next" in content, "frontend/.dockerignore must exclude .next"
