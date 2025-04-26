from asyncio import futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from utils.userCall import UserCall

def execute(userCall: UserCall):
    userCall.priceChangeInference = userCall.generate_price_change_inference(defiActions=userCall.defiActions,functions=userCall.functions)

def execute_cuda(userCall: UserCall, model, tokenizer, device):
    userCall.priceChangeInference = userCall.generate_price_change_inference(defiActions=userCall.defiActions,
                                                                             functions=userCall.functions, 
                                                                             model=model, 
                                                                             tokenizer=tokenizer, 
                                                                             device=device)

def multi_thread(userCalls: List[UserCall]):
    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(execute, userCalls)

def multi_thread_cuda(userCalls: List[UserCall], model, tokenizer, device):
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(execute_cuda, userCall, model, tokenizer, device)
                   for userCall in userCalls]
        for future in as_completed(futures):
            future.result()
