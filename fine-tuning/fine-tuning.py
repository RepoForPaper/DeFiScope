import os
import torch
import torch.distributed as dist
from torch.utils.data import DataLoader, DistributedSampler
from transformers import (AutoConfig, AutoModelForCausalLM, AutoTokenizer, 
                          default_data_collator, get_linear_schedule_with_warmup)
from peft import get_peft_model, LoraConfig, PeftConfig, PeftModel, TaskType
from tqdm import tqdm
import deepspeed
import argparse

from build_dataset import load_csv_dataset

print("🏃 Running DDP + Deepspeed training script (LoRA fine-tuning)")

# ------------------- Setup -------------------

parser = argparse.ArgumentParser(description="LoRA fine-tuning script arguments")
parser.add_argument("--base_model_name", type=str, required=True, help="Base model name")
parser.add_argument("--model_name_or_path", type=str, required=True, help="Model name or path")
parser.add_argument("--tokenizer_name_or_path", type=str, required=True, help="Tokenizer name or path")
parser.add_argument("--version", type=str, required=True, help="Version identifier")
parser.add_argument("--continue_ft", action="store_true", help="Switch to continue fine-tuning (default false)")
parser.add_argument("--ckpt_path", type=str, help="Checkpoint path (required if --continue_ft is set)")
parser.add_argument("--num_epochs", type=int, required=True, help="Number of epochs to train")
parser.add_argument("--lr", type=float, required=True, help="Learning rate for optimizer")
parser.add_argument("--save_per_x_epochs", type=int, default=50, help="Save checkpoint every x epochs")
parser.add_argument("--local_rank", type=int, default=0, help="Local rank passed by DeepSpeed")

args = parser.parse_args()

base_model_name = args.base_model_name
model_name_or_path = args.model_name_or_path
tokenizer_name_or_path = args.tokenizer_name_or_path
version = args.version
continue_ft = args.continue_ft
num_epochs = args.num_epochs
lr = args.lr
save_periodic = args.save_per_x_epochs

if continue_ft:
    if args.ckpt_path is None:
        parser.error("--ckpt_path is required when --continue_ft is set.")
    ckpt_path = args.ckpt_path
else:
    ckpt_path = None  # or leave it unset as needed

print("-"*50 + " Setup " + "-"*50)
device = "cuda"

# Create the LoRA configuration (adjust hyperparameters as needed)
lora_config = LoraConfig(
    r=4,
    lora_alpha=8,
    target_modules=["o_proj", "qkv_proj"],
    lora_dropout=0.1,
    task_type=TaskType.CAUSAL_LM
)

# File paths for datasets and checkpoint directory.
train_csv = os.path.join("dataset", "training_set.csv")
eval_csv  = os.path.join("dataset", "eval_set.csv")
checkpoint_dir = f"checkpoints/{base_model_name}/{version}"
os.makedirs(checkpoint_dir, exist_ok=True)
training_dataset_name = os.path.splitext(os.path.basename(train_csv))[0]
raw_checkpoint_name = f"{training_dataset_name}_{model_name_or_path}_{lora_config.__class__.__name__}_{version}.pt".replace("/", "_")
checkpoint_name = os.path.join(checkpoint_dir, raw_checkpoint_name)

print(f"checkpoint_name: {checkpoint_name}")
print("[✅ Done] Setup")

# ------------------- Load Dataset -------------------
print("-"*50 + " Load Dataset " + "-"*50)
train_dataset = load_csv_dataset("train", train_csv)
eval_dataset  = load_csv_dataset("test", eval_csv)
print("🏋️ ℹ️")
print(f"train_dataset sample: {train_dataset[0]}")
print(f"train_dataset features: {train_dataset.features}")
print(f"train_dataset length: {len(train_dataset)}")
print("🧐 ℹ️")
print(f"eval_dataset sample: {eval_dataset[0]}")
print(f"eval_dataset features: {eval_dataset.features}")
print(f"eval_dataset length: {len(eval_dataset)}")

# For generation tasks, the prompt and expected response are in these CSV columns.
prompt_column = "input"
response_column = "response"
max_length = 2000  
batch_size = 2

print("-"*50 + " Preprocess Dataset " + "-"*50)
tokenizer = AutoTokenizer.from_pretrained(tokenizer_name_or_path)
if tokenizer.pad_token_id is None:
    tokenizer.pad_token_id = tokenizer.eos_token_id

prefix = "You are a price oracle of DeFi protocols, your job is to evaluate the price change of assets based on the given information."

max_total_length = 0
for example in train_dataset:
    prompt_text = f"<|user|>\n{prefix}{example[prompt_column]}<|end|>\n<|assistant|>\n"
    response_text = str(example[response_column])
    prompt_tokens = tokenizer(prompt_text)["input_ids"]
    response_tokens = tokenizer(response_text)["input_ids"] + [tokenizer.pad_token_id]
    total_length = len(prompt_tokens + response_tokens)
    if total_length > max_total_length:
        max_total_length = total_length
print(f"📏 Maximum total length (prompt + response): {max_total_length}")

def preprocess_function(examples):
    bs = len(examples[prompt_column])
    inputs = [f"Task: {x}\nResponse:\n" for x in examples[prompt_column]]
    targets = [str(x) for x in examples[response_column]]
    model_inputs = tokenizer(inputs)
    labels = tokenizer(targets)
    for i in range(bs):
        sample_input_ids = model_inputs["input_ids"][i]
        label_input_ids = labels["input_ids"][i] + [tokenizer.pad_token_id]
        model_inputs["input_ids"][i] = sample_input_ids + label_input_ids
        labels["input_ids"][i] = [-100] * len(sample_input_ids) + label_input_ids
        model_inputs["attention_mask"][i] = [1] * len(model_inputs["input_ids"][i])
    for i in range(bs):
        sample_input_ids = model_inputs["input_ids"][i]
        label_input_ids = labels["input_ids"][i]
        model_inputs["input_ids"][i] = [tokenizer.pad_token_id] * (max_length - len(sample_input_ids)) + sample_input_ids
        model_inputs["attention_mask"][i] = [0] * (max_length - len(sample_input_ids)) + model_inputs["attention_mask"][i]
        labels["input_ids"][i] = [-100] * (max_length - len(sample_input_ids)) + label_input_ids
        model_inputs["input_ids"][i] = torch.tensor(model_inputs["input_ids"][i][:max_length])
        model_inputs["attention_mask"][i] = torch.tensor(model_inputs["attention_mask"][i][:max_length])
        labels["input_ids"][i] = torch.tensor(labels["input_ids"][i][:max_length])
    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

processed_train = train_dataset.map(
    preprocess_function,
    batched=True,
    num_proc=1,
    remove_columns=train_dataset.column_names,
    load_from_cache_file=False,
    desc="Tokenizing training dataset",
)
processed_eval = eval_dataset.map(
    preprocess_function,
    batched=True,
    num_proc=1,
    remove_columns=eval_dataset.column_names,
    load_from_cache_file=False,
    desc="Tokenizing evaluation dataset",
)

# print out one sample from the processed training set
# sample = processed_train[0]
# print("Input IDs:", sample["input_ids"])
# attended_tokens = sum(sample["attention_mask"])
# print("Number of attended tokens (non-pad):", attended_tokens)

# ------------------- Initialize Distributed Process Group -------------------
def init_distributed_mode():
    if "RANK" in os.environ and "WORLD_SIZE" in os.environ:
        rank = int(os.environ["RANK"])
        world_size = int(os.environ["WORLD_SIZE"])
        local_rank = int(os.environ["LOCAL_RANK"])
    else:
        print("Not using distributed mode")
        rank = 0
        world_size = 1
        local_rank = 0
    dist.init_process_group(backend="nccl", init_method="env://")
    torch.cuda.set_device(local_rank)
    return rank, world_size, local_rank

rank, world_size, local_rank = init_distributed_mode()

train_sampler = DistributedSampler(processed_train, num_replicas=world_size, rank=rank, shuffle=True)
eval_sampler  = DistributedSampler(processed_eval, num_replicas=world_size, rank=rank, shuffle=False)

train_dataloader = DataLoader(
    processed_train,
    sampler=train_sampler,
    collate_fn=default_data_collator,
    batch_size=batch_size,
    pin_memory=True,
)
eval_dataloader = DataLoader(
    processed_eval,
    sampler=eval_sampler,
    collate_fn=default_data_collator,
    batch_size=batch_size,
    pin_memory=True,
)

print("[✅ Done] Load and preprocess dataset")

# ------------------- Model, Optimizer and DeepSpeed Setup -------------------
print("="*30 + " Load Model " + "="*30)
# If continuing fine-tuning, load the model from the local checkpoint.
if continue_ft:
    peft_ckpt_config = PeftConfig.from_pretrained(ckpt_path)
    model = AutoModelForCausalLM.from_pretrained(peft_ckpt_config.base_model_name_or_path)
    model = PeftModel.from_pretrained(model, ckpt_path)
    print("ℹ️ Loaded model from checkpoint:", ckpt_path)
else:
    # Otherwise, load model from Hugging Face Hub and apply LoRA fine-tuning.
    config = AutoConfig.from_pretrained(model_name_or_path)
    model = AutoModelForCausalLM.from_pretrained(model_name_or_path)

    model = get_peft_model(model, lora_config)
    print("ℹ️ Load model and applied LoRA fine-tuning on", model_name_or_path)
    print("ℹ️ Configuration:\n", config)

print("ℹ️ Trainable parameters:")
model.print_trainable_parameters()

print("[✅ Done] Load model")

print("="*30 + " Setup Optimizer and Scheduler " + "="*30)
optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
lr_scheduler = get_linear_schedule_with_warmup(
    optimizer=optimizer,
    num_warmup_steps=0,
    num_training_steps=(len(train_dataloader) * num_epochs),
)
print("[✅ Done] Setup optimizer and scheduler")

# ----- Begin DeepSpeed Integration -----
ds_config_path = os.path.join(os.path.dirname(__file__), "lora_ds_config.json")
model, optimizer, _, lr_scheduler = deepspeed.initialize(
    config=ds_config_path,
    model=model,
    optimizer=optimizer,
    model_parameters=[p for p in model.parameters() if p.requires_grad]
)
# ----- End DeepSpeed Integration -----

# ------------------- Training Loop -------------------
print("="*30 + " Training Loop Start " + "="*30)
for epoch in range(num_epochs):
    if rank == 0:
        print("🌟 "*10 + f"Epoch {epoch+1}/{num_epochs}" + "🌟 "*10)
    train_sampler.set_epoch(epoch)
    model.train()
    total_loss = 0
    for step, batch in enumerate(tqdm(train_dataloader)):
        batch = {k: v.to(local_rank) for k, v in batch.items()}
        outputs = model(**batch)
        loss = outputs.loss
        total_loss += loss.detach().float()
        model.backward(loss)
        model.step()
        model.zero_grad()

    model.eval()
    eval_loss = 0
    for step, batch in enumerate(tqdm(eval_dataloader)):
        batch = {k: v.to(local_rank) for k, v in batch.items()}
        with torch.no_grad():
            outputs = model(**batch)
        loss = outputs.loss
        eval_loss += loss.detach().float()

    eval_epoch_loss = eval_loss / len(eval_dataloader)
    train_epoch_loss = total_loss / len(train_dataloader)
    print(f"Epoch {epoch}: train_loss: {train_epoch_loss.item():.4f}, eval_loss: {eval_epoch_loss.item():.4f}")

    if rank == 0:
        if lr_scheduler is not None:
            current_lr = lr_scheduler.get_last_lr()[0]
        else:
            current_lr = optimizer.param_groups[0]['lr']
        print(f"Current learning rate: {current_lr}")

    # Save periodic checkpoint (every x epochs)
    if (epoch + 1) % save_periodic == 0 and rank == 0:
        name_without_ext, ext = os.path.splitext(checkpoint_name)
        epoch_checkpoint = f"{name_without_ext}_epoch{epoch+1}{ext}"
        model.save_pretrained(epoch_checkpoint)
        tokenizer.save_pretrained(epoch_checkpoint)
        print(f"Checkpoint saved at {epoch_checkpoint}")

    # Save latest checkpoint at end of every epoch
    if rank == 0:
        name_without_ext, ext = os.path.splitext(checkpoint_name)
        latest_checkpoint = f"{name_without_ext}_latest_epoch{ext}"
        model.save_pretrained(latest_checkpoint)
        tokenizer.save_pretrained(latest_checkpoint)

if rank == 0:
    model.save_pretrained(checkpoint_name)
    tokenizer.save_pretrained(checkpoint_name)
    print(f"Model and tokenizer saved to {checkpoint_name}")