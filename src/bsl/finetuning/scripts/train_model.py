"""
Fine-tuning Qwen2.5-Coder на BSL коде с Unsloth
Оптимизировано для GPU с 8GB+ VRAM
"""
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import torch
import os

# Конфигурация
MAX_SEQ_LENGTH = 2048
DTYPE = None  # Авто-определение
LOAD_IN_4BIT = True

# Пути
BASE_DIR = "D:/1C-Enterprise_Framework"
DATASET_PATH = f"{BASE_DIR}/data/datasets/bsl_training.json"
OUTPUT_DIR = f"{BASE_DIR}/finetuning/checkpoints"
MODEL_OUTPUT = f"{BASE_DIR}/data/models/bsl-coder-lora"
GGUF_OUTPUT = f"{BASE_DIR}/data/models/gguf"


def main():
    print("=" * 60)
    print("BSL Coder Fine-tuning")
    print("=" * 60)

    # Проверка CUDA
    print(f"\nCUDA доступна: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # Загрузка модели
    print("\n1. Загрузка базовой модели...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit",
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=DTYPE,
        load_in_4bit=LOAD_IN_4BIT,
    )

    # Настройка LoRA
    print("\n2. Настройка LoRA адаптеров...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # Загрузка датасета
    print(f"\n3. Загрузка датасета: {DATASET_PATH}")
    dataset = load_dataset("json", data_files=DATASET_PATH)
    print(f"   Примеров в датасете: {len(dataset['train'])}")

    # Промпт-шаблон
    alpaca_prompt = """### Instruction:
{instruction}

### Input:
{input}

### Response:
{output}"""

    def formatting_prompts_func(examples):
        instructions = examples["instruction"]
        inputs = examples["input"]
        outputs = examples["output"]
        texts = []
        for instruction, input_text, output in zip(instructions, inputs, outputs):
            text = alpaca_prompt.format(
                instruction=instruction,
                input=input_text,
                output=output
            )
            texts.append(text)
        return {"text": texts}

    dataset = dataset.map(formatting_prompts_func, batched=True)

    # Настройка тренировки
    print("\n4. Настройка тренировки...")

    # Определение количества шагов
    num_examples = len(dataset["train"])
    batch_size = 2
    gradient_accumulation = 4
    effective_batch_size = batch_size * gradient_accumulation

    # Для полной эпохи
    steps_per_epoch = num_examples // effective_batch_size
    max_steps = min(steps_per_epoch, 500)  # Максимум 500 шагов для первого прогона

    print(f"   Примеров: {num_examples}")
    print(f"   Effective batch size: {effective_batch_size}")
    print(f"   Шагов: {max_steps}")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation,
            warmup_steps=10,
            max_steps=max_steps,
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=10,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="cosine",
            seed=3407,
            output_dir=OUTPUT_DIR,
            save_steps=100,
            save_total_limit=3,
        ),
    )

    # Обучение
    print("\n5. Начало обучения...")
    trainer.train()

    # Сохранение LoRA адаптеров
    print(f"\n6. Сохранение модели в {MODEL_OUTPUT}")
    os.makedirs(MODEL_OUTPUT, exist_ok=True)
    model.save_pretrained(MODEL_OUTPUT)
    tokenizer.save_pretrained(MODEL_OUTPUT)

    # Экспорт в GGUF для Ollama
    print(f"\n7. Экспорт в GGUF: {GGUF_OUTPUT}")
    os.makedirs(GGUF_OUTPUT, exist_ok=True)
    model.save_pretrained_gguf(
        GGUF_OUTPUT,
        tokenizer,
        quantization_method="q4_k_m"
    )

    print("\n" + "=" * 60)
    print("Обучение завершено!")
    print("=" * 60)
    print(f"\nФайлы:")
    print(f"  LoRA адаптеры: {MODEL_OUTPUT}")
    print(f"  GGUF модель: {GGUF_OUTPUT}")
    print(f"\nДля загрузки в Ollama:")
    print(f"  ollama create bsl-coder -f {BASE_DIR}/data/models/Modelfile")


if __name__ == "__main__":
    main()
