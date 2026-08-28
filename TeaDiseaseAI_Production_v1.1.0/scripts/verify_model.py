from pathlib import Path
import hashlib
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
model_dir = ROOT / "models" / "tea_disease" / "v1.0.0"
pt = model_dir / "tea_disease_yolo26n_v1.0.0.pt"
onnx = model_dir / "tea_disease_yolo26n_v1.0.0.onnx"
for p in (pt, onnx):
    print(f"{p.name}: {'FOUND' if p.exists() else 'MISSING'}")
    if p.exists():
        print("  SHA256:", hashlib.sha256(p.read_bytes()).hexdigest())
if pt.exists():
    model = YOLO(str(pt))
    print("PT LOAD: PASSED")
    print("Classes:", model.names)
