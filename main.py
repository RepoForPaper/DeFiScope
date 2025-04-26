import os
import time
import shutil
import argparse
import jsonlines
from itertools import combinations
import torch

from utils.transaction import Transaction
from utils.detector import Detector
from utils.log import attack_log
from utils.debug_log import *
from utils.tranxToUserCalls import extract_userCalls_from_tranx
from utils.checkFlashloan import flagFlashloan
from utils.matchRelatedActions import matchRelatedActions
from utils.multiThreadHelper import multi_thread, multi_thread_cuda
from utils.fast_filter import fast_filter
from utils.load_model import load_model_for_device

# run nano ~/.bash_profile, write: export OPENAI_API_KEY='your-api-key-here'
# run source ~/.bash_profile to import openAI API key first
# check with: echo $OPENAI_API_KEY

# run with command: python main.py -tx txhash -bp platform
parser = argparse.ArgumentParser()
parser.add_argument("-tx",
                    "--transaction_hash",
                    help="The hash of the transation",
                    action="store", 
                    dest="txhash", 
                    type=str)
parser.add_argument("-bp",
                    "--blockchain_platform",
                    help="The blockchain platform where the test contract is deployed",
                    action="store", 
                    dest="platform", 
                    type=str)
parser.add_argument("--debug",
                    action='store_const',
                    const=True,
                    default=False,
                    help="Enable debug mode",
                    dest="debug_mode")
parser.add_argument("--use_local_model", 
                    action="store_true", 
                    help="Use local model (default: False)")
parser.add_argument("--model_path", 
                    type=str, 
                    help="Local model path / Huggingface model name  (required if --use_huggingface_model)")
args = parser.parse_args()

txhash = args.txhash
platform = args.platform
debug_mode = args.debug_mode
use_local_model = args.use_local_model

if use_local_model:
    if args.model_path is None:
        raise ValueError("Please provide a model path when using --use_local_model.")
    model_path = args.model_path
    device = torch.device("cuda:0") # Ajust this based on your env
else:
    model_path = None

start_time = time.time()
result = ""

if fast_filter(tx=txhash, chain=platform):
    result = "False"
else:
    # Initialization
    if os.path.exists("tmp"):
        shutil.rmtree("tmp")
    os.makedirs("tmp")

    # Detection
    try:
        transaction = Transaction(txhash=txhash, platform=platform)
        userAccount = transaction.user_account
        userCalls = extract_userCalls_from_tranx(userAccount=userAccount, 
                                                            decoded_transaction=transaction.decoded_transaction, 
                                                            chain=transaction.platform)
        matchRelatedActions(userCalls=userCalls)

        flagFlashloan(userCalls=userCalls, userAccount=userAccount)

        old_global_token_balance = dict()
        for userCall in userCalls:
            userCall.update_contract_address_name_mapping(platform=platform)
            userCall.global_token_balance_change = old_global_token_balance.copy()
            old_global_token_balance = userCall.update_gloabl_token_balance_change()

        # for userCall in userCalls:
        #     userCall.priceChangeInference = userCall.generate_price_change_inference(defiActions=userCall.defiActions,functions=userCall.functions)
        
        if use_local_model:
            model, tokenizer = load_model_for_device(model_path=model_path, device=device)
            multi_thread_cuda(userCalls=userCalls, model=model, tokenizer=tokenizer, device=device)
        else:
            multi_thread(userCalls)

        filtered_userCalls = [userCall 
                            for userCall in userCalls 
                            if userCall.userCallPurpose or any(userCall.priceChangeInference.values())]
        
        # Print debug information
        if debug_mode:
            print("#" * 150)
            print("Processed UserCall Details:")
            for userCall in filtered_userCalls:
                log_defiPurpose_sequence(userCall)
                log_defiAction(userCall)
                log_price_calculation_functions(userCall)
                log_functions(userCall)
                log_transfer_details(userCall)
                log_flashloan(userCall)
                log_relatedAction(userCall)
                log_priceChangeTendency(userCall)
            print("Detect Result:")
        
        attack_detected = False
        if len(filtered_userCalls) >= 3:
            for userCall_Combination in combinations(filtered_userCalls, 3):
                detector = Detector(userCalls=list(userCall_Combination), userAccount=userAccount)
                for detect_result in detector.results:
                    if detect_result.isAttack:
                        attack_detected = True
                        if debug_mode:
                            attack_log(detect_result)

        if not attack_detected:
            print("[*]The transaction is a price manipulation attack: False")
            result = "False"
        else:
            print("[*]The transaction is a price manipulation attack: True")
            result = "True"

    except Exception as e:
        print(e)
        result = "Error"

end_time = time.time()
print("[*]Execution Time: ", end_time - start_time, "s")

# Record detection result
print("Write detection result to 'detection_result.jsonl'")
with jsonlines.open("detection_result.jsonl", 'a') as f:
    if result == "True":
        f.write({txhash: "True", "time": end_time - start_time})
    elif result == "False":
        f.write({txhash: "False", "time": end_time - start_time})
    else:
        f.write({txhash: "Error", "time": end_time - start_time})

# Clean up
if os.path.exists("tmp"):
    shutil.rmtree("tmp")
