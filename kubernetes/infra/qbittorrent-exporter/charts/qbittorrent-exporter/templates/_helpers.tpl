{{- define "qbittorrent-exporter.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "qbittorrent-exporter.fullname" -}}
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

{{- define "qbittorrent-exporter.labels" -}}
helm.sh/chart: {{ include "qbittorrent-exporter.name" . }}
app.kubernetes.io/name: {{ include "qbittorrent-exporter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "qbittorrent-exporter.selectorLabels" -}}
app.kubernetes.io/name: {{ include "qbittorrent-exporter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
