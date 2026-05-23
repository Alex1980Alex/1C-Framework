import os
from huggingface_hub import snapshot_download
p = snapshot_download("Qwen/Qwen3-Embedding-8B", allow_patterns=["1_Pooling/*"])
cfg = os.path.join(p, "1_Pooling", "config.json")
assert os.path.exists(cfg), f"Pooling config missing at {cfg}"
print("pooling OK:", cfg)
