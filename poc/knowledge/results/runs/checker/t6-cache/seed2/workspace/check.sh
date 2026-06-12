#!/bin/bash
# Deterministic quality gate. Exit 0 = all green. Fix every finding.
set -o pipefail
status=0
go build ./... || status=1
go vet ./... || status=1
/Users/mateo/helios/poc/knowledge/bin/rulecheck -dir . -format text -rules /Users/mateo/helios/poc/knowledge/rules || status=1
exit $status
