______________________________________________________________________

## name: scaleway-secrets description: Manage secrets in Scaleway Secret Manager using vals ref+scw:// provider. Use when creating, listing, or referencing secrets for Helmfile deployments, or troubleshooting secret resolution. compatibility: Requires scw CLI, vals, and helmfile metadata: author: homelab version: "1.0"

# Scaleway CLI Secret Management

## Architecture

```
Helmfile with vals -> ref+scw:// -> Scaleway Secret Manager API -> secret value
```

The `vals` tool supports a Scaleway provider that fetches secret values at deploy time, eliminating hardcoded secrets in Helm charts.

## Secret Reference Pattern

The `ref+scw://` provider follows this pattern:

```
ref+scw://<project>/<secret>#<field>
```

**Components:**

- `<project>` — Scaleway project name (e.g., `homelab`)
- `<secret>` — Secret name in the project (e.g., `rustfs`, `cnpg`, `passbolt`)
- `<field>` — Specific field value within the secret (e.g., `password`, `user`, `api-key`)

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
| `SCW_REGION` | Scaleway region | `fr-par` |

Configure vals to use the Scaleway provider:

```bash
# In .envrc (already there)
export SCW_ACCESS_KEY="<your-access-key>"
export SCW_SECRET_KEY="<your-secret-key>"
export SCW_PROJECT_ID="<project-id>"
export SCW_REGION="fr-par"

# Add to PATH if needed
export PATH="/path/to/vals/bin:$PATH"
export HELMFILE_VALS_PATH=/path/to/vals/bin/vals
```

## Create a New Secret in Scaleway

1. Install Scaleway CLI:

```bash
# macOS
brew install scaleway/scaleway-cli/scw

# Linux
curl -sSL https://github.com/scaleway/scaleway-cli/releases/download/v3.0.0/scw_3.0.0_linux_amd64.deb -o scw.deb
sudo dpkg -i scw.deb

# Verify installation
scw version
```

2. Configure CLI:

```bash
scw init
# Follow prompts for API keys and default region
```

3. Create a secret:

```bash
scw secret create name=rustfs
# Add fields interactively or via flags:
#   --field name=user --field value="admin"
#   --field name=password --field value="s3cret"
#   --field name=region --field value="fr-par"
```

4. List secrets:

```bash
scw secret list
scw secret get name=rustfs
```

5. Use in Helm values:

```yaml
# kubernetes/apps/myapp/values.yaml
app:
  username: ref+scw:///homelab/rustfs#/user
  password: ref+scw:///homelab/rustfs#/password
  region: ref+scw:///homelab/rustfs#/region
```

## Deploy with vals

```bash
# Vals automatically resolves ref+scw:// references
cd kubernetes/apps/myapp
helmfile apply
```

## Benefits

- **Security**: Secrets never stored in Git repositories
- **Centralized**: Single source of truth for all secrets
- **Auditable**: Secret access logs in Scaleway console
- **Versioned**: Track secret history with Scaleway revisions
- **Dynamic**: Secrets resolved at deploy time, not commit time

## Troubleshooting

- **vals not found**: Ensure `HELMFILE_VALS_PATH` is set correctly in `.envrc`
- **Secret not found**: Verify secret exists: `scw secret get name=<secret>`
- **Permission denied**: Check `SCW_ACCESS_KEY` and `SCW_SECRET_KEY` in `.envrc` match Scaleway console
- **Wrong project**: Confirm `SCW_PROJECT_ID` matches the project where secrets are stored

## vals Provider Reference

For detailed vals Scaleway provider documentation:

```bash
vals help scw
vals provider scw --help
```

The Scaleway provider for vals is maintained separately from the core vals project. Check the [vals documentation](https://github.com/helmfile/vals) for provider-specific options.
