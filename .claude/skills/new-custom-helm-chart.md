# Create Custom Helm Chart

Create a custom Helm chart when no suitable upstream chart exists.

## Usage

```
/new-custom-helm-chart <app-name> <namespace>
```

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

## Reference

See `kubernetes/apps/glance/` for a complete custom chart example.
