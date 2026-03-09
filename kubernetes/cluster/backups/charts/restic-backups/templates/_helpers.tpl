{{/*
Chart labels
*/}}
{{- define "restic-backups.labels" -}}
helm.sh/chart: {{ .Chart.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Resource name — unique suffix when app shares a namespace with another backup
*/}}
{{- define "restic-backups.resourceName" -}}
{{- if .app.uniqueNames -}}
restic-backup-{{ .appName }}
{{- else -}}
restic-backup
{{- end -}}
{{- end }}

{{/*
Secret name — unique suffix when app shares a namespace with another backup
*/}}
{{- define "restic-backups.secretName" -}}
{{- if .app.uniqueNames -}}
restic-rustfs-credentials-{{ .appName }}
{{- else -}}
restic-rustfs-credentials
{{- end -}}
{{- end }}

{{/*
Restic repository URL
*/}}
{{- define "restic-backups.resticRepo" -}}
s3:{{ .global.rustfs.endpoint }}/{{ .global.rustfs.bucket }}/{{ .appName }}
{{- end }}

{{/*
RBAC resource types needed for this app's targets
*/}}
{{- define "restic-backups.scaleResources" -}}
{{- $types := dict -}}
{{- range .targets -}}
  {{- $_ := set $types (printf "%ss/scale" .type) true -}}
{{- end -}}
{{- keys $types | sortAlpha | toYaml }}
{{- end }}
