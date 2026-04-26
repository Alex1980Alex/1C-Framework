from huggingface_hub import snapshot_download
p = snapshot_download("Qwen/Qwen3-Embedding-8B", resume_download=True)
print("downloaded to:", p)
