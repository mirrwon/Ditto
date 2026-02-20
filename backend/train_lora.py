import argparse
import json
import os
import random
from typing import Any, Dict, List, Optional

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)

EMOTE_SET = {
    "HAPPY",
    "NEEDY",
    "ANNOYED",
    "SASSY",
    "WORRIED",
    "CALM",
    "PROUD",
    "MAGICAL",
}

ANIMATION_SET = {
    "idle",
    "bounce",
    "shake",
    "wiggle",
    "float",
    "sparkle",
    "droop",
    "pout",
    "wave",
    "nod",
}


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemma2 LoRA trainer for JSONL messages data")
    parser.add_argument("--model_name", type=str, default="google/gemma-2-9b-it")
    parser.add_argument("--train_file", type=str, default="full_dataset_training.jsonl")
    parser.add_argument("--output_dir", type=str, default="/home/ubuntu/artifacts/lora_gemma2_v1")
    parser.add_argument("--max_seq_len", type=int, default=2048)
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--grad_accum", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--max_steps", type=int, default=3000)
    parser.add_argument("--save_steps", type=int, default=100)
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--save_total_limit", type=int, default=3)
    parser.add_argument("--warmup_ratio", type=float, default=0.03)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume_from_checkpoint", type=str, default="")
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument(
        "--target_modules",
        type=str,
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
    )
    parser.add_argument("--trust_remote_code", action="store_true")
    return parser.parse_args()



def make_bnb_config() -> BitsAndBytesConfig:
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )



def safe_apply_chat_template(tokenizer: AutoTokenizer, messages: List[Dict[str, str]], add_generation_prompt: bool) -> str:
    if hasattr(tokenizer, "apply_chat_template"):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
        )

    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"<{role}>\n{content}\n</{role}>")
    if add_generation_prompt:
        lines.append("<assistant>\n")
    return "\n".join(lines)



def build_features(example: Dict[str, Any], tokenizer: AutoTokenizer, max_seq_len: int) -> Dict[str, Any]:
    messages = example.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return {"input_ids": [], "attention_mask": [], "labels": []}

    if messages[-1].get("role") != "assistant":
        return {"input_ids": [], "attention_mask": [], "labels": []}

    prompt_messages = messages[:-1]
    answer_text = messages[-1].get("content", "")
    if not isinstance(answer_text, str):
        answer_text = str(answer_text)

    prompt_text = safe_apply_chat_template(
        tokenizer=tokenizer,
        messages=prompt_messages,
        add_generation_prompt=True,
    )
    full_text = f"{prompt_text}{answer_text}{tokenizer.eos_token or ''}"

    prompt_ids = tokenizer(
        prompt_text,
        truncation=True,
        max_length=max_seq_len,
        add_special_tokens=False,
    )["input_ids"]

    tokenized = tokenizer(
        full_text,
        truncation=True,
        max_length=max_seq_len,
        add_special_tokens=False,
    )

    input_ids = tokenized["input_ids"]
    attention_mask = tokenized["attention_mask"]

    labels = input_ids.copy()
    prompt_len = min(len(prompt_ids), len(labels))
    for i in range(prompt_len):
        labels[i] = -100

    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels,
    }



class Seq2SeqCollator:
    def __init__(self, tokenizer: AutoTokenizer):
        self.tokenizer = tokenizer

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        features = [f for f in features if len(f.get("input_ids", [])) > 0]
        if not features:
            raise ValueError("No valid features after preprocessing")

        pad_id = self.tokenizer.pad_token_id
        if pad_id is None:
            pad_id = self.tokenizer.eos_token_id

        max_len = max(len(f["input_ids"]) for f in features)

        input_ids = []
        attention_mask = []
        labels = []

        for f in features:
            cur_len = len(f["input_ids"])
            pad_len = max_len - cur_len
            input_ids.append(f["input_ids"] + [pad_id] * pad_len)
            attention_mask.append(f["attention_mask"] + [0] * pad_len)
            labels.append(f["labels"] + [-100] * pad_len)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }



def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    if not os.path.exists(args.train_file):
        raise FileNotFoundError(f"train_file not found: {args.train_file}")

    os.makedirs(args.output_dir, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=args.trust_remote_code)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    bnb_config = make_bnb_config()
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=args.trust_remote_code,
    )

    model = prepare_model_for_kbit_training(model)

    target_modules = [x.strip() for x in args.target_modules.split(",") if x.strip()]
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    raw_ds = load_dataset("json", data_files=args.train_file, split="train")
    tokenized_ds = raw_ds.map(
        lambda x: build_features(x, tokenizer=tokenizer, max_seq_len=args.max_seq_len),
        remove_columns=raw_ds.column_names,
        num_proc=1,
        desc="Tokenizing",
    )

    tokenized_ds = tokenized_ds.filter(lambda x: len(x["input_ids"]) > 0)

    if len(tokenized_ds) == 0:
        raise RuntimeError("No valid training samples after preprocessing")

    bf16_ok = torch.cuda.is_available() and torch.cuda.is_bf16_supported()

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=args.warmup_ratio,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        bf16=bf16_ok,
        fp16=not bf16_ok,
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        report_to="none",
        remove_unused_columns=False,
        dataloader_num_workers=2,
        dataloader_pin_memory=True,
        run_name="gemma2_lora_train",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_ds,
        tokenizer=tokenizer,
        data_collator=Seq2SeqCollator(tokenizer),
    )

    resume_ckpt: Optional[str] = args.resume_from_checkpoint.strip() or None
    trainer.train(resume_from_checkpoint=resume_ckpt)

    final_adapter_dir = os.path.join(args.output_dir, "final_adapter")
    os.makedirs(final_adapter_dir, exist_ok=True)
    trainer.model.save_pretrained(final_adapter_dir)
    tokenizer.save_pretrained(final_adapter_dir)

    metrics_path = os.path.join(args.output_dir, "train_meta.json")
    meta = {
        "model_name": args.model_name,
        "train_file": args.train_file,
        "num_samples": len(tokenized_ds),
        "max_seq_len": args.max_seq_len,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "lr": args.lr,
        "max_steps": args.max_steps,
        "save_steps": args.save_steps,
        "target_modules": target_modules,
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[DONE] final adapter saved: {final_adapter_dir}")
    print(f"[DONE] meta saved: {metrics_path}")


if __name__ == "__main__":
    main()
