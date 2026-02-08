#!/bin/sh
# Set torizon password to "corekinect" and fix shadow expiry
# SHA-512 hash of "corekinect":
HASH='$6$M4IwM0kR0nAo.3yq$QMzqm3a4CmlIvZyjR/GH9yUMPQzzXsS13EBugQ8nPWTij7C40VD0Xgh8H6nuqbvk26Ce/g3WaFFQj3gUO5JiK.'
echo "torizon:${HASH}" | chpasswd -e
chage -d 20089 torizon
rm -f /etc/corekinect-password-pending
