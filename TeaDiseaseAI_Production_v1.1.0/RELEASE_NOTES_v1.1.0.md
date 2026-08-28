# TeaGuard AI v1.1.0 — OpenCV Production Quality Gate

## Added

- OpenCV capture-quality engine `opencv_capture_quality_v1.0.0`.
- Automatic quality preflight immediately after image selection.
- Hard rejection for grossly unusable resolution, blur and extreme exposure.
- Advisory warnings for borderline focus, exposure, contrast and broad leaf framing.
- EXIF orientation correction before OpenCV analysis.
- Colour-preserving inference preprocessing; no CLAHE/white-balance/hue manipulation.
- Separate normalized-original and processed-inference image storage.
- Per-scan capture quality score, grade, warnings, metrics and engine version.
- OpenCV quality evidence in scan results, history, review queue and CSV export.
- Capture-quality governance information on the Model page.
- Capture quality dashboard metric.
- Human-review escalation for Fair/Poor but passable capture quality.
- Structured `CAPTURE_QUALITY_REJECTED` API response.
- `/api/quality/check` preflight endpoint.
- `/api/predictions/{id}/processed-image` evidence endpoint.
- Batch field-image quality audit script.
- Local OpenCV threshold validation protocol.
- Automated tests for good, tiny and dark captures.

## Safety design

- Leaf-like coverage is advisory and is not lesion segmentation.
- No disease severity is inferred from OpenCV pixel counts.
- No colour enhancement is applied before inference until it has been locally validated.
- The existing disease-model benchmark remains scoped to the held-out public dataset.

## Backward compatibility

Existing v1.0.0 prediction rows continue to display as legacy scans without capture-quality evidence. `Base.metadata.create_all()` adds the new `quality_assessments` table without requiring changes to legacy prediction columns.
