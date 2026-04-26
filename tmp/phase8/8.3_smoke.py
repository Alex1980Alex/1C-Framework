import torch
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("Qwen/Qwen3-Embedding-8B", device="cuda", model_kwargs={"torch_dtype": torch.float16})
v = m.encode(["test"], convert_to_numpy=True)
print("shape:", v.shape, "dtype:", v.dtype)
assert v.shape == (1, 4096), f"Unexpected shape: {v.shape}"
