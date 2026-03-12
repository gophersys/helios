{{- define "shared-nats.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "shared-nats.fullname" -}}
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

{{- define "shared-nats.labels" -}}
helm.sh/chart: {{ include "shared-nats.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "shared-nats.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: messaging
{{- end }}

{{- define "shared-nats.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shared-nats.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
