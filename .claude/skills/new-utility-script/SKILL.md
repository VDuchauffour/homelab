______________________________________________________________________

## name: new-utility-script description: Scaffold a new Python utility script package under scripts/ following project conventions (Typer CLI, Pydantic models, structlog, httpx, pytest with MagicMock). Use when creating new CLI tools for the homelab. compatibility: Requires Python 3.12+ and uv metadata: author: homelab version: "1.0"

# Create New Utility Script Package

## Conventions

All script packages **must** use:

| Concern | Convention |
|---------|-----------|
| CLI | Typer (`typer.Typer()` + `@app.command()`) |
| Models | Pydantic v2 (`BaseModel`, `Field`, `model_config = {"frozen": True}`) |
| HTTP | httpx (sync `Client` or async `AsyncClient`) |
| Logging | structlog (copy `configure()` block from `warden/helper.py`) |
| Testing | pytest + `unittest.mock` (`MagicMock`, `patch`) |
| Config | Environment variables via `os.environ` in a `load_config_from_env()` function |

Reference implementations: `scripts/warden/` and `scripts/passbolt/`.

## Package Structure

```
scripts/<package-name>/
├── __init__.py
├── helper.py
├── <command>.py
└── tests/
    ├── __init__.py
    └── test_<module>.py
```

## Steps

1. Create the package directory:

   ```shell
   mkdir -p scripts/<package-name>/tests
   ```

2. Create `__init__.py`:

   ```python
   """<Package description>."""

   __version__ = "0.1.0"
   ```

3. Create `helper.py` with shared models, API client, and logging:

   ```python
   import os
   from typing import Optional

   import httpx
   import structlog
   from pydantic import BaseModel, Field

   structlog.configure(
       processors=[
           structlog.contextvars.merge_contextvars,
           structlog.processors.add_log_level,
           structlog.processors.StackInfoRenderer(),
           structlog.dev.set_exc_info,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.dev.ConsoleRenderer(),
       ],
       wrapper_class=structlog.make_filtering_bound_logger(20),
       context_class=dict,
       logger_factory=structlog.PrintLoggerFactory(),
       cache_logger_on_first_use=False,
   )


   def get_logger(name: str = __name__) -> structlog.BoundLogger:
       return structlog.get_logger(name)


   def configure_log_level(verbose: bool = False):
       level = 10 if verbose else 20
       structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))


   def load_config_from_env() -> dict:
       # Load required env vars, raise ValueError if missing
       ...
   ```

4. Create CLI entry point `<command>.py`:

   ```python
   import typer
   from <package>.helper import configure_log_level, get_logger

   log = get_logger(__name__)
   app = typer.Typer(help="<description>")

   @app.command()
   def main(
       verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
   ):
       configure_log_level(verbose)
       ...

   if __name__ == "__main__":
       app()
   ```

5. Create `tests/__init__.py` (empty file).

6. Create tests in `tests/test_<module>.py` using `pytest` + `unittest.mock`:

   ```python
   import pytest
   from unittest.mock import MagicMock, patch
   ```

7. Update `scripts/pyproject.toml`:

   ```toml
   # [project.scripts]
   <cli-name> = "<package>.<command>:app"

   # [tool.hatch.build.targets.wheel]
   packages = ["warden", "passbolt", "<package>"]

   # [tool.pytest.ini_options]
   testpaths = ["warden/tests", "passbolt/tests", "<package>/tests"]

   # [tool.coverage.run]
   source = ["warden", "passbolt", "<package>"]
   omit = [
     ...
     "<package>/<command>.py",
     "<package>/tests/*",
   ]

   # [project].dependencies -- add any new deps
   ```

8. Install and verify:

   ```shell
   cd scripts
   uv sync
   uv run pytest <package>/tests/ -v
   ```
