# MTIB Proto Changelog

## 1.0.0 (2026-04-23)

Initial versioned release. Baseline wire format for all existing RPCs:

- HealthCheck, GPIO, ADC, Sensors, Motion, Firmware, UART, Power, NFC, Observability
- Power channels: DUT, Charger, Joulescope
- ADC streaming, GPIO watch, Power streaming
- Package declaration changed from `mtib` to `mtib.v1`

### Versioning Policy

- **Patch**: documentation, comment-only changes
- **Minor**: additive changes (new fields, new RPCs, new enum values)
- **Major**: breaking changes (removed/renamed fields, changed field types/numbers)
