"""Pre-download and cache models for offline operation:
  1. Default embedding model (BAAI/bge-small-en-v1.5) for hybrid RAG & vector search.
  2. Image generation Diffusers pipeline (runwayml/stable-diffusion-v1-5).
"""
import sys
import os
import argparse

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"


def download_default_embedding_model() -> bool:
    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    print(f"[*] Verifying / caching default embedding model '{model_name}'...")
    try:
        from sentence_transformers import SentenceTransformer

        # Check if already present in local cache
        try:
            model = SentenceTransformer(model_name, local_files_only=True)
            print(f"  [OK] Embedding model '{model_name}' is verified in local cache.")
        except Exception:
            print(f"  [*] Downloading '{model_name}' model weights from HuggingFace...")
            model = SentenceTransformer(model_name)
            print(f"  [OK] Embedding model '{model_name}' downloaded and cached successfully.")

        get_dim = getattr(
            model,
            "get_embedding_dimension",
            getattr(model, "get_sentence_embedding_dimension", None),
        )
        dim = get_dim() if get_dim else 384
        print(f"  [OK] Embedding dimension: {dim}d ready.")
        return True
    except Exception as exc:
        print(f"  [ERROR] Failed to download embedding model '{model_name}': {exc}", file=sys.stderr)
        return False


def download_diffusers_image_model(model_name: str = None) -> bool:
    if not model_name:
        model_name = os.getenv("DIFFUSERS_IMAGE_MODEL", "runwayml/stable-diffusion-v1-5")
    print(f"[*] Verifying / caching Diffusers image generation model '{model_name}'...")
    try:
        import torch
        from diffusers import DiffusionPipeline

        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        # Check if already present in local cache
        try:
            pipe = DiffusionPipeline.from_pretrained(
                model_name,
                torch_dtype=torch_dtype,
                local_files_only=True,
            )
            print(f"  [OK] Diffusers model '{model_name}' is verified in local cache.")
            return True
        except Exception:
            print(f"  [*] Downloading '{model_name}' Diffusers weights from HuggingFace...")
            pipe = DiffusionPipeline.from_pretrained(
                model_name,
                torch_dtype=torch_dtype,
            )
            print(f"  [OK] Diffusers model '{model_name}' downloaded and cached successfully.")
            return True
    except Exception as exc:
        print(f"  [ERROR] Failed to download Diffusers model '{model_name}': {exc}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Download AI models for Gen-Transform-AI")
    parser.add_argument("--embeddings", action="store_true", help="Download embedding model only")
    parser.add_argument("--diffusers", action="store_true", help="Download Diffusers image model only")
    parser.add_argument("--all", action="store_true", help="Download all models (embeddings + diffusers)")
    parser.add_argument("--model", type=str, default=None, help="Custom Diffusers model ID")

    args = parser.parse_args()

    # Default behaviour when run with no arguments or --all: download embeddings (and diffusers if requested or in --all)
    if args.diffusers:
        success = download_diffusers_image_model(args.model)
        sys.exit(0 if success else 1)
    elif args.all:
        ok1 = download_default_embedding_model()
        ok2 = download_diffusers_image_model(args.model)
        sys.exit(0 if (ok1 and ok2) else 1)
    elif args.embeddings:
        success = download_default_embedding_model()
        sys.exit(0 if success else 1)
    else:
        # Default: download embeddings, and check diffusers if DOWNLOAD_DIFFUSERS=1 env is set
        ok1 = download_default_embedding_model()
        if os.getenv("DOWNLOAD_DIFFUSERS", "0") == "1":
            ok2 = download_diffusers_image_model(args.model)
            sys.exit(0 if (ok1 and ok2) else 1)
        sys.exit(0 if ok1 else 1)


if __name__ == "__main__":
    main()
