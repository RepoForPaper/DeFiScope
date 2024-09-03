from concurrent.futures import ThreadPoolExecutor
from typing import List

from utils.userCall import UserCall

def execute(userCall: UserCall):
    userCall.priceChangeInference = userCall.generate_price_change_inference(defiActions=userCall.defiActions,functions=userCall.functions)

def multi_thread(userCalls: List[UserCall]):
    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(execute, userCalls)