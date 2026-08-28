# TeaGuard AI — Tea Disease Identification Production Web App v1.1.0

A customer-handover web application for tea-leaf visual screening using the validated six-class Tea Disease model, now protected by an **OpenCV Capture Quality Gate** before disease inference.

## Production flow

1. Secure sign-in and role-based access.
2. Mobile camera capture or desktop image upload.
3. **OpenCV preflight** checks resolution, sharpness, exposure, contrast and broad leaf framing.
4. Grossly unusable images are blocked and the user is asked to retake the photo.
5. Passed images are EXIF-orientation-corrected and resized conservatively **without recolouring disease symptoms**.
6. Optional Estate → Division → Field context is attached.
7. YOLO26 classification returns the top class and top-3 probabilities.
8. Human review is recommended for low-confidence/close-call predictions and for materially weak but passable capture quality.
9. Original normalized image, inference image, quality metrics, model version, image SHA-256 and model SHA-256 are retained for traceability.
10. Dashboard, review queue, history, CSV export and model/quality governance are available in the web UI.

## OpenCV quality engine

Engine: `opencv_capture_quality_v1.0.0`

The engine checks:

- minimum usable image resolution;
- severe blur / low edge detail using Laplacian variance;
- severe underexposure and overexposure;
- clipped dark/bright pixel ratios;
- low contrast warnings;
- broad leaf-like subject coverage and centre framing as **advisory heuristics only**;
- safe resize for inference.

### What it deliberately does *not* do

The OpenCV layer does **not**:

- diagnose disease;
- identify lesion pixels;
- estimate infected leaf area;
- estimate disease severity;
- alter hue/colour to make lesions more visible;
- claim a leaf is absent solely from colour thresholds.

This separation prevents capture-quality logic from being mistaken for biological diagnosis.

## Six model classes

- Algal Leaf Spot
- Black Blight
- Blister Blight
- Gray Blight
- Healthy
- Spider Mites

## Validation statement

The packaged disease model benchmark is **98.44% Top-1 accuracy on 257 held-out images from the public Sri Lankan tea leaf dataset test split**, with Macro F1 98.61%.

That benchmark must **not** be represented as guaranteed customer-field accuracy. Customer estate photographs require local validation. The OpenCV quality thresholds also require calibration against the customer’s actual phones/cameras and field conditions before being treated as fixed operational limits.

## Fastest installation on the current development PC

Extract the package, then run in PowerShell:

```powershell
cd "<EXTRACTED_PACKAGE_PATH>"
.\INSTALL_FROM_PLANTATIONAI360.ps1 -PlantationRoot "H:\PlantationAI360"
.\RUN_WINDOWS.ps1 -PythonPath "H:\PlantationAI360\.venv\Scripts\python.exe" -Port 8785
```

Open:

```text
http://127.0.0.1:8785
```

On first launch, create the **Owner** account. There are no default passwords embedded in the package.

## Standalone customer installation

1. Install Python 3.11.
2. Run `SETUP_STANDALONE_WINDOWS.ps1`.
3. Copy the validated `.pt` and `.onnx` files into `models\tea_disease\v1.0.0`.
4. Copy `.env.example` to `.env` and configure company/database settings.
5. Run `RUN_WINDOWS.ps1`.

## Recommended production validation sequence

Before customer acceptance:

1. Test OpenCV quality on at least 100–200 real photos from the actual target phones/cameras.
2. Include intentionally poor photos: blur, dark, glare, distant leaves, clutter and rotated images.
3. Confirm the gate rejects clearly unusable captures but does not reject normal field images unnecessarily.
4. Tune only the `.env` quality thresholds; do not hard-code customer-specific values.
5. Validate the disease model separately using representative field images reviewed by qualified personnel.
6. Lock the threshold configuration and model SHA-256 for the accepted production release.

See `OPENCV_CAPTURE_QUALITY_PROTOCOL.md` and `LOCAL_VALIDATION_PROTOCOL.md`.

## Production server notes

For public HTTPS deployment:

- use PostgreSQL rather than SQLite;
- place the app behind Nginx/Apache/IIS with TLS;
- set `COOKIE_SECURE=true`;
- back up the database and `uploads/` together;
- restrict administrative access;
- preserve model and quality-engine versions in audit records;
- deploy new model versions alongside old versions rather than overwriting evidence;
- calibrate OpenCV thresholds before formal field rollout.

## Ownership / third-party software

The custom application can be transferred to the customer under the project agreement. Python, FastAPI, PyTorch/Ultralytics, OpenCV, ONNX Runtime, PostgreSQL and other third-party components remain subject to their own licences. Review `THIRD_PARTY_NOTICES.md` and use qualified legal counsel for final IP-assignment wording.
