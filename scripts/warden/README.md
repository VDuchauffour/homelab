# Warden Utilities

Kubernetes-to-Warden monitoring integration scripts.

## Installation

```bash
cd scripts
uv sync
```

## Usage

### Seed Monitors

Discover Kubernetes deployments with HTTP liveness probes and register them in Warden:

```bash
export WARDEN_API_KEY="your-api-key"

# Seed all namespaces
uv run warden-seed --host http://warden.home.arpa

# Seed specific namespace
uv run warden-seed --namespace media-center --host http://warden.home.arpa

# Override check interval
uv run warden-seed --interval 60 --host http://warden.home.arpa

# Dry-run (preview without creating)
uv run warden-seed --dry-run --host http://warden.home.arpa

# Verbose logging
uv run warden-seed -v --host http://warden.home.arpa
```

### Delete All Monitors

Delete all monitors and groups from Warden:

```bash
# Preview what would be deleted
uv run warden-delete --dry-run --host http://warden.home.arpa

# Delete with confirmation prompts
uv run warden-delete --host http://warden.home.arpa

# Delete without prompts (dangerous!)
uv run warden-delete --force --host http://warden.home.arpa
```

### Compare Kubernetes vs Warden

See which deployments have HTTP probes and which are monitored in Warden:

```bash
uv run warden-compare
```

## Architecture

```
warden/
├── __init__.py          # Package metadata
├── helper.py            # Shared models, clients, and utilities
├── seed_monitors.py     # Main seeding script
├── delete_monitors.py   # Deletion script
└── compare.py           # Comparison script
```

### helper.py

Common code shared across all scripts:

- **Pydantic Models**: `Monitor`, `ExistingMonitor`, `GroupResponse`, etc.
- **KubernetesDiscovery**: Discovers deployments with HTTP liveness probes
- **WardenClient**: API client for Warden operations
- **Logging**: Structured logging with structlog

## Features

✅ **Upsert Logic** - Creates or updates monitors (idempotent)
✅ **Type Safety** - Pydantic models with validation
✅ **Structured Logging** - JSON-ready logs with structlog
✅ **Dry-Run Mode** - Preview changes before applying
✅ **Namespace Filtering** - Target specific namespaces
✅ **Error Handling** - Graceful failure with detailed errors
✅ **CLI Scripts** - Installed as `warden-*` commands

## Development

```bash
# Install in editable mode
uv pip install -e .

# Run tests (if you add them)
pytest warden/
```
