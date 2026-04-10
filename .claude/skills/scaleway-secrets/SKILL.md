______________________________________________________________________

## name: scaleway-secrets description: Manage secrets in Scaleway Secret Manager using vals ref+scw:// provider. Use when creating, listing, or referencing secrets for Helmfile deployments, or troubleshooting secret resolution. compatibility: Requires scw CLI, vals, and helmfile metadata: author: homelab version: "1.2"

# Scaleway CLI Secret Management

## Architecture

```
Helmfile with vals -> ref+scw:// -> Scaleway Secret Manager API -> secret value
```

The `vals` tool supports a Scaleway provider that fetches secret values at deploy time, eliminating hardcoded secrets in Helm charts.

## Secret Reference Pattern

The `ref+scw://` provider follows this pattern:

```
ref+scw://<path>/<secret>#<field>
```

**Components:**

- `<path>` — Secret path in Scaleway Secret Manager (e.g., `homelab`). All homelab secrets use path `/homelab`.
- `<secret>` — Secret name (e.g., `rustfs`, `cnpg`, `peanut-influxdb`)
- `<field>` — JSON field name within the secret's data (e.g., `password`, `user`, `api-key`)

**Examples:**

```yaml
# Simple field lookup
password: ref+scw:///homelab/rustfs#/password

# Multiple fields from same secret
username: ref+scw:///homelab/cnpg#/user
password: ref+scw:///homelab/cnpg#/password
host: ref+scw:///homelab/cnpg#/host

# Nested path (multi-level)
apiKey: ref+scw:///homelab/wakatime#/api-key
```

## Environment Variables

Required in `.envrc` for vals to authenticate with Scaleway:

| Variable | Description | Example |
|----------|-------------|---------|
| `SCW_ACCESS_KEY` | Scaleway API access key | `SCWXXXXXXXXXXXXX` |
| `SCW_SECRET_KEY` | Scaleway API secret key | (keep secure) |
| `SCW_PROJECT_ID` | Scaleway project ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `SCW_DEFAULT_REGION` | Scaleway region | `fr-par` |

Configure vals to use the Scaleway provider:

```bash
# In .envrc (already there)
export SCW_ACCESS_KEY="<your-access-key>"
export SCW_SECRET_KEY="<your-secret-key>"
export SCW_PROJECT_ID="<project-id>"
export SCW_DEFAULT_REGION="fr-par"

# Add to PATH if needed
export PATH="/path/to/vals/bin:$PATH"
export HELMFILE_VALS_PATH=/path/to/vals/bin/vals
```

> **Note:** `SCW_REGION` is deprecated. Use `SCW_DEFAULT_REGION` instead.

## How Scaleway Secrets Work

Scaleway Secret Manager uses a two-level structure:

1. **Secret** — A named container (has a UUID, name, tags)
2. **Version** — The actual data payload (JSON blob) stored under a secret, identified by revision number

Each secret can have multiple versions (revisions). The `ref+scw://` provider reads the **latest enabled version** by default.

## Create a New Secret

Creating a secret is a two-step process:

### Step 1: Create the secret container

```bash
scw secret secret create name=my-secret path=/homelab -o json
```

This returns a JSON object with the secret's UUID in the `id` field.

> **IMPORTANT:** Always pass `path=/homelab` when creating secrets. All homelab secrets live under the `/homelab` path. Omitting `path` creates the secret at `/` (root), which breaks `ref+scw:///homelab/...` references.

### Step 2: Create a version with JSON data

```bash
scw secret version create <secret-id >data='{"user":"admin","password":"s3cret"}'
```

The `data` parameter accepts a JSON string. It also supports file loading with `@/path/to/file`:

```bash
# From a file
echo '{"user":"admin","password":"s3cret"}' >/tmp/secret.json
scw secret version create <secret-id >data=@/tmp/secret.json
rm /tmp/secret.json
```

### Full example

```bash
# Create secret under /homelab path and capture ID
SECRET_ID=$(scw secret secret create name=my-app path=/homelab -o json | jq -r .id)

# Create version with data
scw secret version create "$SECRET_ID" data='{"user":"admin","password":"s3cret","api-key":"abc123"}'

# Reference in Helm values
# password: ref+scw:///homelab/my-app#/password
# api-key:  ref+scw:///homelab/my-app#/api-key
```

## List and Inspect Secrets

```bash
# List all secrets
scw secret secret list

# Filter by name
scw secret secret list name=my-app

# Get secret metadata by ID
scw secret secret get <secret-id>

# List versions of a secret
scw secret version list <secret-id>
```

## Read Secret Data

```bash
# Access full JSON data (latest revision)
scw secret version access <secret-id >revision=latest

# Access a specific field (raw value, no JSON wrapper)
scw secret version access field=password raw=true <secret-id >revision=latest

# Access a specific revision
scw secret version access <secret-id >revision=2
```

## Update a Secret (New Version)

To update a secret's data, create a new version. Optionally disable the previous version:

```bash
scw secret version create disable-previous=true <secret-id >data='{"user":"admin","password":"new-password"}'
```

## Use in Helm Values

After secrets are stored in Scaleway, reference them in Helm values using the `ref+scw://` provider. Helmfile resolves these automatically at deploy time:

```yaml
# kubernetes/apps/myapp/values.yaml
app:
  username: ref+scw:///homelab/my-app#/user
  password: ref+scw:///homelab/my-app#/password
  apiKey: ref+scw:///homelab/my-app#/api-key
```

```bash
# Deploy — vals resolves ref+scw:// automatically
cd kubernetes/apps/myapp
helmfile apply
```

## Benefits

- **Security**: Secrets never stored in Git repositories
- **Centralized**: Single source of truth for all secrets
- **Auditable**: Secret access logs in Scaleway console
- **Versioned**: Track secret history with revisions
- **Dynamic**: Secrets resolved at deploy time, not commit time

## Troubleshooting

- **vals not found**: Ensure `HELMFILE_VALS_PATH` is set correctly in `.envrc`
- **Secret not found**: Verify secret exists: `scw secret secret list name=<secret>`
- **Permission denied**: Check `SCW_ACCESS_KEY` and `SCW_SECRET_KEY` in `.envrc` match Scaleway console
- **Wrong project**: Confirm `SCW_PROJECT_ID` matches the project where secrets are stored
- **Stale data**: Check the latest version is enabled: `scw secret version list <secret-id>`

## CLI Quick Reference

| Action | Command |
|--------|---------|
| Create secret | `scw secret secret create name=<name> path=/homelab -o json` |
| Create version | `scw secret version create <secret-id> data='{"key":"val"}'` |
| List secrets | `scw secret secret list` |
| List by name | `scw secret secret list name=<name>` |
| Get secret metadata | `scw secret secret get <secret-id>` |
| List versions | `scw secret version list <secret-id>` |
| Read data | `scw secret version access <secret-id> revision=latest` |
| Read single field | `scw secret version access <secret-id> revision=latest field=<key> raw=true` |
| Update data | `scw secret version create <secret-id> data='...' disable-previous=true` |
