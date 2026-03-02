"""
Export fine-tuned LoRA adapters to Ollama-compatible GGUF format.

Usage:
    python -m Jarvis.sft.export_to_ollama

This will:
    1. Load base model + merge LoRA adapters
    2. Save merged model in HuggingFace format
    3. Convert to GGUF using llama.cpp
    4. Create Ollama Modelfile and import
"""

import argparse
import subprocess
import sys
from pathlib import Path


def merge_lora(base_model: str, lora_path: str, output_path: str):
    """Merge LoRA adapters into base model."""
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        print("Missing packages. Install: pip install torch transformers peft")
        sys.exit(1)

    print(f"Loading base model: {base_model}")
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        device_map="cpu",  # merge on CPU to avoid VRAM issues
        trust_remote_code=True,
    )

    print(f"Loading LoRA adapters: {lora_path}")
    model = PeftModel.from_pretrained(model, lora_path)

    print("Merging weights...")
    model = model.merge_and_unload()
    model.to("cpu")

    print(f"Saving merged model to: {output_path}")
    model.save_pretrained(output_path)

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    tokenizer.save_pretrained(output_path)

    print(f"Merged model saved to {output_path}")
    return output_path


def convert_to_gguf(merged_path: str, gguf_output: str):
    """Convert HuggingFace model to GGUF format using llama.cpp."""
    # Check if llama.cpp convert script exists
    convert_script = Path("llama.cpp/convert_hf_to_gguf.py")

    if not convert_script.exists():
        print("\nllama.cpp not found. Cloning...")
        subprocess.run(
            ["git", "clone", "https://github.com/ggerganov/llama.cpp.git"],
            check=True,
        )
        # Filter out torch from requirements.txt to avoid overwriting CUDA version
        req_path = Path("llama.cpp/requirements.txt")
        if req_path.exists():
            reqs = req_path.read_text(encoding="utf-8").splitlines()
            reqs = [r for r in reqs if not r.lower().startswith("torch")]
            req_path.write_text("\n".join(reqs), encoding="utf-8")

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "llama.cpp/requirements.txt"],
            check=True,
        )

    print(f"\nConverting to GGUF: {merged_path} -> {gguf_output}")
    subprocess.run(
        [
            sys.executable,
            str(convert_script),
            merged_path,
            "--outfile", gguf_output,
            "--outtype", "f16",  # f16 quantization to avoid quality loss
        ],
        check=True,
    )
    print(f"GGUF saved to {gguf_output}")


def import_to_ollama(gguf_path: str, model_name: str):
    """Create Ollama Modelfile and import the model."""
    # Use absolute path for GGUF so Ollama can find it
    abs_gguf = str(Path(gguf_path).resolve())
    modelfile_content = f'''FROM {abs_gguf}

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.3
PARAMETER num_ctx 2048

SYSTEM """You are Jarvis, an autonomous AI assistant. You execute system commands using structured tags.

For shell commands: [SHELL]command here[/SHELL]
For app actions use colon format: [ACTION]launch_app: notepad[/ACTION]

Available action types:
- launch_app: <app_name>
- open_url: <url>
- system_info
- notification: <title> | <message>

For dangerous commands (shutdown, format, delete system files), ask for confirmation first.
For safe commands, execute directly.
For conversational queries, respond naturally without any tags."""
'''
    modelfile_path = "Modelfile.jarvis"
    with open(modelfile_path, "w") as f:
        f.write(modelfile_content)

    print(f"\nImporting to Ollama as '{model_name}'...")
    subprocess.run(
        ["ollama", "create", model_name, "-f", modelfile_path],
        check=True,
    )
    print(f"\nDone! Model available as: {model_name}")
    print(f"Test with: ollama run {model_name} \"open notepad\"")


def main():
    parser = argparse.ArgumentParser(description="Export LoRA to Ollama")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct",
                        help="Base model name on HuggingFace")
    parser.add_argument("--lora-path", default="output/jarvis-gemma-lora",
                        help="Path to LoRA adapter directory")
    parser.add_argument("--merged-path", default="output/jarvis-merged",
                        help="Path to save merged model")
    parser.add_argument("--gguf-path", default="output/jarvis-action.gguf",
                        help="Path to save GGUF file")
    parser.add_argument("--ollama-name", default="jarvis-action",
                        help="Name for the Ollama model")
    parser.add_argument("--skip-ollama", action="store_true",
                        help="Skip Ollama import (just merge + convert)")
    args = parser.parse_args()

    # Step 1: Merge LoRA into base
    merge_lora(args.base_model, args.lora_path, args.merged_path)

    # Step 2: Convert to GGUF
    convert_to_gguf(args.merged_path, args.gguf_path)

    # Step 3: Import to Ollama
    if not args.skip_ollama:
        import_to_ollama(args.gguf_path, args.ollama_name)
    else:
        print(f"\nSkipped Ollama import. GGUF at: {args.gguf_path}")
        print(f"To import manually:")
        print(f"  ollama create {args.ollama_name} -f Modelfile.jarvis")

    print(f"\n{'='*60}")
    print(f"  Next: Update your .env to use the fine-tuned model")
    print(f"  OLLAMA_MODEL={args.ollama_name}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
