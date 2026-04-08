{{- define "shared-couchdb.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "shared-couchdb.fullname" -}}
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

{{- define "shared-couchdb.labels" -}}
helm.sh/chart: {{ include "shared-couchdb.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "shared-couchdb.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: database
{{- end }}

{{- define "shared-couchdb.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shared-couchdb.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
