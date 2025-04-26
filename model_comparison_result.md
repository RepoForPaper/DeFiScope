# Training setup

## Model

[microsoft/Phi-3-medium-128k-instruct](https://huggingface.co/microsoft/Phi-3-medium-128k-instruct)

## DeepSpeed config (ds_config.json)

```json
{
    "train_batch_size": 32,
    "gradient_accumulation_steps": 4,
    "train_micro_batch_size_per_gpu": 2,
    "fp16": {
        "enabled": true
    },
    "zero_optimization": {
        "stage": 2,
        "allgather_partitions": true,
        "reduce_scatter": true,
        "allgather_bucket_size": 200000000,
        "overlap_comm": true,
        "contiguous_gradients": true
    }
}
```

## LoRA config

```
r=4,
lora_alpha=8,
target_modules=["o_proj", "qkv_proj"],
lora_dropout=0.1
```

## Hyperparameters

```
max_length = 2000 
lr = 0.0001
num_epochs = 10
batch_size = 2
```

# Comparison between Phi-3 and GPT family

## Inference Setup

```
do_sample=True
top_p=1.0,
temperature=1e-8, # Nearly deterministic, cannot set to 0: ValueError: `temperature` (=0) has to be a strictly positive float, otherwise your next token scores will be invalid.
max_new_tokens=128000 - prompt_length # Adjust this based on your model
```

## Result

![Image](https://github.com/user-attachments/assets/8890b514-2bf9-4883-82b0-bf4e5cf233b7)
