"""Download the multilingual-e5-small ONNX (int8 quantized) model files at build time.

Avoids committing large binaries to git (GitHub blocks files over 100 MB).
Run this after `pip install -r requirements.txt` as part of Render's build command.
"""

from pathlib import Path

from huggingface_hub import hf_hub_download

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "multilingual-e5-small"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

REPO_ID = "Xenova/multilingual-e5-small"

# (filename in the HF repo, filename we want it saved as locally)
FILES = [
    ("tokenizer.json", "tokenizer.json"),
    ("onnx/model_quantized.onnx", "model_quantized.onnx"),
]


def main() -> None:
    for repo_filename, local_filename in FILES:
        target = MODEL_DIR / local_filename
        if target.exists():
            print(f"Already present, skipping: {target}")
            continue
        print(f"Downloading {repo_filename} from {REPO_ID} ...")
        downloaded_path = hf_hub_download(repo_id=REPO_ID, filename=repo_filename)
        # hf_hub_download caches to its own dir; copy/rename into our expected location.
        import shutil

        shutil.copyfile(downloaded_path, target)
        print(f"Saved to {target}")

    print("Model files ready.")


if __name__ == "__main__":
    main()