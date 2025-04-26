import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
from peft import PeftModel, PeftConfig

def load_model_for_device(model_path: str, device):
    print(f"🕤 Loading model {model_path} on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # config = AutoConfig.from_pretrained(model_path) # For base models. Comment this line for PEFT models
    # model = AutoModelForCausalLM.from_pretrained(model_path) # For base models. Comment this line for PEFT models
    
    peft_ckpt_config = PeftConfig.from_pretrained(model_path) # For PEFT models. Comment this line for non-PEFT models
    model = AutoModelForCausalLM.from_pretrained(peft_ckpt_config.base_model_name_or_path) # For PEFT models. Comment this line for non-PEFT models
    model = PeftModel.from_pretrained(model, model_path) # For PEFT models. Comment this line for non-PEFT models

    model.to(device)
    model.eval()
    print("✅ Model loaded successfully.")
    return model, tokenizer
