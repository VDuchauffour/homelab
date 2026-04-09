______________________________________________________________________

## name: new-custom-helm-chart description: Create a custom Helm chart when no upstream chart exists. Use when scaffolding a new app that needs its own chart with deployment, service, ingress, and optional configmap/pvc templates. compatibility: Requires helmfile, helm, kubectl, and vals metadata: author: homelab version: "1.0"

# Create Custom Helm Chart

## Chart Structure

```
kubernetes/apps/<app-name>/
├── helmfile.yaml
├── values.yaml
└── charts/
    └── <app-name>/
        ├── Chart.yaml
        ├── values.yaml
        └── templates/
            ├── _helpers.tpl
            ├── deployment.yaml
            ├── service.yaml
            ├── ingress.yaml
            ├── configmap.yaml (optional)
            └── pvc.yaml (optional)
```

## Steps

1. Create directory structure:

   ```shell
   mkdir -p kubernetes/apps/<app-name>/charts/<app-name>/templates
   ```

2. Create `charts/<app-name>/Chart.yaml`:

   ```yaml
   apiVersion: v2
   name: <app-name>
   description: A Helm chart for <app-name>
   type: application
   version: 0.1.0
   appVersion: "1.0.0"
   ```

3. Create `charts/<app-name>/values.yaml` with defaults

4. Create `charts/<app-name>/templates/_helpers.tpl`:

   ```yaml
   {{- define "<app-name>.name" -}}
   {{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
   {{- end }}

   {{- define "<app-name>.fullname" -}}
   {{- if .Values.fullnameOverride }}
   {{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
   {{- else }}
   {{- $name := default .Chart.Name .Values.nameOverride }}
   {{- if contains $name .Release.Name }}
   {{- .Release.Name | trunc 63 | trimSuffix "-" }}
   {{- else }}
   {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
   {{- end }}
   {{- end }}
   {{- end }}

   {{- define "<app-name>.labels" -}}
   helm.sh/chart: {{ include "<app-name>.name" . }}
   app.kubernetes.io/name: {{ include "<app-name>.name" . }}
   app.kubernetes.io/instance: {{ .Release.Name }}
   app.kubernetes.io/managed-by: {{ .Release.Service }}
   {{- end }}

   {{- define "<app-name>.selectorLabels" -}}
   app.kubernetes.io/name: {{ include "<app-name>.name" . }}
   app.kubernetes.io/instance: {{ .Release.Name }}
   {{- end }}
   ```

5. Create `templates/deployment.yaml`, `templates/service.yaml`, `templates/ingress.yaml`

6. Create top-level `helmfile.yaml`:

   ```yaml
   ---
   releases:
     - name: <app-name>
       namespace: <namespace>
       createNamespace: true
       chart: ./charts/<app-name>
       values:
         - values.yaml
   ```

## Post-Deployment Checklist

After deploying the new app, complete ALL of the following steps:

### 1. Update Glance Dashboard

Add a bookmark entry to `kubernetes/apps/glance/values-common.yaml` in the appropriate group:

- **`instanceBookmarkGroups`**: Infrastructure/cluster tools (Proxy, Cluster, Monitoring groups)
- **`commonBookmarkGroups`**: User-facing apps (Productivity, Tools, Sharing, Media, Arr, AI groups)

```yaml
- title: MyApp
  subdomain: myapp
  icon: di:myapp  # or sh:myapp, or a raw URL
```

Icon conventions (**PNG only** — Glance does not render SVG reliably):

- `di:<name>` — [Dashboard Icons](https://github.com/walkxcode/dashboard-icons) (preferred, resolves to PNG)
- `sh:<name>` — [Selfh.st Icons](https://selfh.st/icons/) (resolves to PNG)
- Raw URL — `https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/<name>.png` or `https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/<name>.png`. **Never use SVG.**

Redeploy Glance:

```shell
make glance-update
```

### 2. Update Pangolin Blueprint (if externally accessible)

Add a resource block to `kubernetes/infra/pangolin-newt/manifests/blueprint.yaml`, maintaining **alphabetical order** by resource key:

```yaml
myapp:
  name: MyApp
  protocol: http
  full-domain: myapp.ref+envsubst://$PUBLIC_DOMAIN_NAME
  auth:
    sso-enabled: true
    whitelist-users:
      - ref+envsubst://$EMAIL_ADDRESS
  targets:
    - hostname: myapp.myapp.svc.cluster.local
      method: http
      port: 8080
      healthcheck:
        hostname: myapp.myapp.svc.cluster.local
        port: 8080
        enabled: true
        path: /
        interval: 30
        timeout: 5
```

For public apps (no auth), omit the `auth` block.

Apply and restart Newt:

```shell
vals eval -f kubernetes/infra/pangolin-newt/manifests/blueprint.yaml | kubectl apply -f -
kubectl rollout restart deployment/fossorial-newt-main-tunnel -n fossorial
```

### 3. Update README

Update `README.md` to include the app in the deployed components tables. Run `make check-readme` to verify.

## Reference

See `kubernetes/apps/glance/` for a complete custom chart example.
