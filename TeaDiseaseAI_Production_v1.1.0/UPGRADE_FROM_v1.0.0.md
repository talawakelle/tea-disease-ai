# Upgrade from TeaGuard AI v1.0.0 to v1.1.0

If v1.0.0 has already been used and contains accounts/scans, do not delete it.

1. Stop the v1.0.0 server with `Ctrl+C`.
2. Keep the entire v1.0.0 folder as a backup.
3. Extract v1.1.0 to a new folder.
4. Run:

```powershell
cd "<v1.1.0 folder>"
.\MIGRATE_FROM_v1.0.0.ps1 -OldRoot "<v1.0.0 folder>"
```

5. If using the existing PlantationAI Python environment, run:

```powershell
.\INSTALL_FROM_PLANTATIONAI360.ps1 -PlantationRoot "H:\PlantationAI360"
```

6. Run the OpenCV self-test:

```powershell
.\TEST_OPENCV.ps1 -PythonPath "H:\PlantationAI360\.venv\Scripts\python.exe"
```

7. Start v1.1.0.

The startup creates the new `quality_assessments` table. Existing predictions remain unchanged and appear as **legacy** records without OpenCV evidence. New scans receive the full quality record.
