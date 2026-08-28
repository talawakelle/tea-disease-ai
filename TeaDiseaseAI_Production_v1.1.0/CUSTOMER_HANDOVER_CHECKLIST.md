# Customer Handover Checklist

## Deliverables
- Custom web application source code
- Database schema and first-run setup
- Validated model `.pt` artifact
- ONNX export
- Model SHA-256 fingerprint
- Six-class label definition
- Held-out benchmark report
- **OpenCV capture-quality engine source code**
- OpenCV threshold configuration in `.env`
- Original + processed image evidence paths
- Capture-quality metrics and engine version per new scan
- Batch capture-quality audit script
- OpenCV field-device validation protocol
- Image/prediction audit trail
- Role-based user management
- Estate/division/field registry
- Human review workflow
- CSV export including capture-quality columns
- Installation and startup scripts
- Environment template
- Production deployment notes

## Acceptance gates
- Owner account can be created without a default password
- Login/session/logout operate correctly
- Camera/upload works from a supported browser
- OpenCV preflight runs automatically after image selection
- Grossly unusable image is blocked before disease inference
- Usable image passes OpenCV preflight and can be analysed
- EXIF orientation is corrected
- Inference preprocessing preserves colour and only resizes conservatively
- Original normalized image is retained separately from processed inference image
- Capture-quality score, grade, warnings and engine version are saved
- Valid image produces a disease prediction
- Invalid/non-image uploads are rejected
- Prediction saves model version and SHA-256 evidence
- Review queue catches model uncertainty and weak-but-passable capture quality
- Corrected class is retained separately from AI prediction
- Dashboard refreshes from saved data
- CSV export includes capture-quality evidence
- Database + `uploads/` backup/restore is proven together
- Model file hash matches signed handover record
- Customer device/field capture-quality calibration is documented
- Customer-specific disease-model field validation is documented separately
- Third-party licence review is completed for the final commercial deployment
