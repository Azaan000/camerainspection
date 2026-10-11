from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

MODEL = Path("models/station_1/model.onnx")
TEST = Path("data/leather/test")

sess = ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])
in_name = sess.get_inputs()[0].name


def score(path: Path) -> tuple[float, bool]:
    img = Image.open(path).convert("RGB").resize((256, 256))
    x = np.asarray(img, dtype=np.float32).transpose(2, 0, 1) / 255.0
    out = sess.run(None, {in_name: np.stack([x, x])})  # batch is fixed at 2
    return float(out[0][0]), bool(out[1][0])


groups = {"good": [], "defect": []}
for p in sorted(TEST.rglob("*.png")):
    kind = "good" if "good" in p.parent.name.lower() or p.name.lower().startswith("good") else "defect"
    s, flagged = score(p)
    groups[kind].append((s, flagged))
    print(f"{kind:7} {p.name:28} score={s:.3f}  {'FAIL' if flagged else 'ok'}")

for kind, rows in groups.items():
    if rows:
        flagged = sum(f for _, f in rows)
        mean_score = np.mean([s for s, _ in rows])
        print(f"\n{kind}: {len(rows)} images | mean score {mean_score:.3f} | flagged {flagged}/{len(rows)}")

