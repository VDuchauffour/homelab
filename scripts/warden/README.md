# Warden Utilities

Kubernetes-to-Warden monitoring integration scripts.

## Installation

```bash
uv sync --directory scripts
```

## Features

- **Auto-discovery from Apps Directory** - Dynamically discovers namespaces from `kubernetes/apps/` helmfiles
- **Deployment Verification** - Only monitors namespaces that actually exist in the cluster
- **Cleanup Mode** - Removes monitors/groups not in the target scope with `--cleanup`
- **Upsert Logic** - Creates or updates monitors (idempotent)
- **Type Safety** - Pydantic models with validation
- **Structured Logging** - JSON-ready logs with structlog
- **Dry-Run Mode** - Preview changes before applying
- **Namespace Filtering** - Target specific namespaces
- **Error Handling** - Graceful failure with detailed errors
- **CLI Scripts** - Installed as `warden-*` commands

## Usage

### Quick Start (Using Make)

From the project root:

```bash
make warden-seed         # Seed app monitors
make warden-seed-cleanup # Seed with cleanup
make warden-delete       # Delete all monitors
make warden-compare      # Compare K8s vs Warden
```

### Advanced Usage

#### Seed Monitors

Discover Kubernetes deployments with HTTP liveness probes and register them in Warden:

```bash
export WARDEN_API_KEY="your-api-key"

# Seed only user-facing apps (recommended - auto-discovers from kubernetes/apps/)
uv run --directory scripts warden-seed --apps-only --host http://warden.home.arpa

# Seed with cleanup (removes monitors not in apps directory)
uv run --directory scripts warden-seed --apps-only --cleanup --host http://warden.home.arpa

# Seed all namespaces
uv run --directory scripts warden-seed --host http://warden.home.arpa

# Seed specific namespace
uv run --directory scripts warden-seed --namespace media-center --host http://warden.home.arpa

# Seed multiple namespaces
uv run --directory scripts warden-seed --namespaces arr,media-center,n8n --host http://warden.home.arpa

# Seed with cleanup for specific namespaces
uv run --directory scripts warden-seed --namespaces arr,n8n --cleanup --host http://warden.home.arpa

# Override check interval
uv run --directory scripts warden-seed --interval 60 --apps-only --host http://warden.home.arpa

# Dry-run (preview without creating)
uv run --directory scripts warden-seed --dry-run --apps-only --host http://warden.home.arpa

# Verbose logging
uv run --directory scripts warden-seed -v --apps-only --host http://warden.home.arpa
```

### Delete All Monitors

Delete all monitors and groups from Warden:

```bash
# Preview what would be deleted
uv run --directory scripts warden-delete --dry-run --host http://warden.home.arpa

# Delete with confirmation prompts
uv run --directory scripts warden-delete --host http://warden.home.arpa

# Delete without prompts (dangerous!)
uv run --directory scripts warden-delete --force --host http://warden.home.arpa
```

### Compare Kubernetes vs Warden

See which deployments have HTTP probes and which are monitored in Warden:

```bash
uv run --directory scripts warden-compare
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

## Development

```bash
# Install in editable mode
uv pip install -e .

# Run tests (if you add them)
pytest warden/
```
