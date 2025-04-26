def generate_completion(prompt: str, model, tokenizer, device):
    # Prepare input
    inputs = tokenizer(f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n", return_tensors="pt") # Phi-3 inference template, adjust this based on your model
    inputs = {k: v.to(device) for k, v in inputs.items()}

    # Compute the prompt length and determine the tokens available for new output
    prompt_length = inputs['input_ids'].shape[1]
    new_tokens = 128000 - prompt_length # Adjust this based on your model
    if new_tokens <= 0:
        raise ValueError("The prompt length exceeds or equals 128k tokens!")
    
    # Generate output
    outputs = model.generate(
        input_ids=inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=1e-8, # Nearly deterministic, cannot set to 0: ValueError: `temperature` (=0) has to be a strictly positive float, otherwise your next token scores will be invalid.
        top_p=1.0,
        max_new_tokens=new_tokens
    )

    # Decode and only return the generated text
    decoded_output = tokenizer.decode(outputs[0][prompt_length:], skip_special_tokens=True)
    return decoded_output
