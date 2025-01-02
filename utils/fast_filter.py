# Filter out the overly simply transactions that are not possible to be price manipulation
from utils.config import SUPPORTED_NETWORK
from web3 import Web3, HTTPProvider

def fast_filter(tx: str, chain: str) -> bool:
    if chain == "ethereum":
        w3 = Web3(HTTPProvider(SUPPORTED_NETWORK["ethereum"]["quick_node"]))
    elif chain == "bsc":
        w3 = Web3(HTTPProvider(SUPPORTED_NETWORK["bsc"]["quick_node"]))
    else:
        return False
    
    receipt = w3.eth.get_transaction_receipt(tx)

    # Only have one event, which means at most one transfer, this transaction cannot be price manipulation
    if len(receipt.logs) <= 1:
        print(f"[*]Fast filter: Transaction has {len(receipt.logs)} log, overly simple to be price manipulation")
        print("[*]Filter out")
        return True
    else:
        return False