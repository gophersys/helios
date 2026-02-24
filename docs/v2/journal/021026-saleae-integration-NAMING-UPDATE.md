# IMPORTANT: Protocol Naming Update

**The main design document (`021026-saleae-integration.md`) uses "Logic" terminology throughout.**

**This terminology is being replaced with "Analyzer" to be vendor-neutral.**

## Quick Reference

| Old Name (Brand-Specific) | New Name (Generic) |
|---------------------------|-------------------|
| `LogicHandler` | `AnalyzerHandler` |
| `LogicCaptureConfig` | `AnalyzerCaptureConfig` |
| `LogicCaptureStart` | `AnalyzerCaptureStart` |
| `LogicStream` | `AnalyzerStream` |
| `LogicSample` | `AnalyzerSample` |
| `logic_capture_start()` | `analyzer_capture_start()` |

See `protocol-changes-analyzer.md` for complete protocol specification.

---

**Action Items:**
1. ✅ Protocol changes documented in `protocol-changes-analyzer.md`
2. ⏳ Update main design doc to use "Analyzer" naming
3. ⏳ Apply changes to `mtib_v2.proto`
4. ⏳ Regenerate protobuf stubs
5. ⏳ Update server implementation
6. ⏳ Update client API
