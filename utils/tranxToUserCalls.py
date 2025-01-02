from typing import List, Dict, Tuple, Set, Optional

from utils.config import SUPPORTED_NETWORK
from utils.userCall import UserCall
from utils.account import Account, AccountType, Token
from utils.transfer import Transfer
# @note deal with the callback: userCalls are not sequantial, a userCall is in another userCall (Flatten the structure)

def extract_userCalls_from_tranx(userAccount: Set[str], decoded_transaction: Dict, chain: str) -> List[UserCall]:
    """
    Extract the user calls from the decoded transaction

    Args:
        userAccount (Set): a set of user accounts
        decoded_transaction (Dict): the decoded transaction in Transaction object
        chain (str): the chain of the transaction
    Returns:
        List[UserCall]: a list of UserCall objects
    """
    raw_userCalls, _, _, _ = extract_raw_userCalls(
        userAccount=userAccount, 
        decoded_transaction=decoded_transaction, 
        raw_userCalls=[], 
        transfer_sequence=[], 
        functions=[], 
        balanceOf_query=dict(),
        isFirst=True,
        chain=chain
        )
    
    # print("[+]The number of user calls is {}, try to find and remove repeated action sequences".format(len(raw_userCalls)))
    # # raw_userCalls = filter_raw_userCalls(raw_userCalls)

    if len(raw_userCalls) > 100:
        print("[!]The number of user calls is {}, try to find and remove repeated action sequences".format(len(raw_userCalls)))
        raw_userCalls = filter_raw_userCalls(raw_userCalls)
    else:
        print("[i]The number of user calls is {}".format(len(raw_userCalls)))
    
    userCalls =[
        UserCall(userAccount=userAccount, transfer_sequence=raw_userCall["transfer_sequence"], functions=raw_userCall["functions"], balanceOf_query=raw_userCall["balanceOf_query"], platform=chain) 
        for raw_userCall in raw_userCalls 
        if raw_userCall["transfer_sequence"] or raw_userCall["functions"]
        ]
    return userCalls

def extract_raw_userCalls(
        userAccount: Set, 
        decoded_transaction: Dict, 
        raw_userCalls: List[Dict], 
        transfer_sequence: List[Transfer], 
        functions: List[Tuple[str,str,List[Account]]], 
        balanceOf_query: Dict[str, Set[str]],
        isFirst: bool,
        chain: str
        ) -> Tuple[List[Dict], List[Transfer], List[Tuple[str,str,List[Account]]], Dict[str, Set[str]]]:
    """
    Extract the raw user calls from the decoded transaction

    Returns:
        List[Dict]: [{"transfer_sequence": List[Transfer], {"functions": List[Tuple[contract address, function name,List[Account]]]}}]
    """
    if decoded_transaction["from"] in userAccount:
        if isFirst or (transfer_sequence or functions):
            # sort transfer_sequence
            transfer_sequence = sort_transfer_sequence(transfer_sequence=transfer_sequence)
            raw_userCalls.append({"transfer_sequence": transfer_sequence, "functions": functions, "balanceOf_query": balanceOf_query})
            isFirst = False
        transfer_sequence = []
        functions = []
        balanceOf_query = dict()
    transfer_sequence, functions, balanceOf_query = extract_tranxSeq_and_functions(
        userAccount=userAccount, 
        decoded_transaction=decoded_transaction, 
        transfer_sequence=transfer_sequence, 
        functions=functions,
        balanceOf_query=balanceOf_query,
        chain=chain
        )
    if "calls" in decoded_transaction:
        for call in decoded_transaction["calls"]:
            raw_userCalls, transfer_sequence, functions, balanceOf_query = extract_raw_userCalls(
                userAccount=userAccount, 
                decoded_transaction=call, 
                raw_userCalls=raw_userCalls, 
                transfer_sequence=transfer_sequence, 
                functions=functions, 
                balanceOf_query=balanceOf_query,
                isFirst=isFirst,
                chain=chain
                )
    if decoded_transaction["from"] in userAccount:
        # sort transfer_sequence
        transfer_sequence = sort_transfer_sequence(transfer_sequence=transfer_sequence)
        raw_userCalls.append({"transfer_sequence": transfer_sequence, "functions": functions, "balanceOf_query": balanceOf_query})
        transfer_sequence = []
        functions = []
        balanceOf_query = dict()
    return raw_userCalls, transfer_sequence, functions, balanceOf_query

def extract_tranxSeq_and_functions(
        userAccount: Set, 
        decoded_transaction: Dict, 
        transfer_sequence: List[Transfer], 
        functions: List[Tuple[str,str,List[Account]]],
        balanceOf_query: Dict[str, Set[str]],
        chain: str
        ) -> Tuple[List[Transfer], List[Tuple[str,str,List[Account]]], Dict[str, Set[str]]]:
    """
    Extract the transfer sequence and functions from the decoded transaction

    returns:
        List[Transfer]: a list of Transfer objects in the call
        List[Tuple[str str,List[Account]]]: a list of tuple combines contract address, function name, Account objects
        Dict[str, Set[str]]: a dictionary of account address and a set of token addresses queried by balanceOf
    """
    accounts = []
    # tokens_change = {account_address: {token_address: balance_change}}
    tokens_change = record_msgValue(msgSender=decoded_transaction["from"],
                                    msgReceiver=decoded_transaction["to"],
                                    msgValue=decoded_transaction["value"],
                                    chain=chain,
                                    transfer_sequence=transfer_sequence)
    if "logs" in decoded_transaction:
        for log in decoded_transaction["logs"]:
            if "name" in log.keys() \
                and "from" in log.keys() \
                and "to" in log.keys() \
                and "token" in log.keys() \
                and "index" in log.keys() \
                and (log["name"] == "Transfer" or log["name"] == "Withdrawal" or log["name"] == "Deposit"):
                transfer_sequence.append(Transfer(sender_address=log["from"], 
                                                  receiver_address=log["to"], 
                                                  token_address=log["token"], 
                                                  amount=log["amount"],
                                                  index=log["index"]))
                # record the sender's token change
                if log["from"] in tokens_change:
                    if log["token"] in tokens_change[log["from"]]:
                        tokens_change[log["from"]][log["token"]] -= log["amount"]
                    else:
                        tokens_change[log["from"]][log["token"]] = -log["amount"]
                else:
                    tokens_change[log["from"]] = {log["token"]: -log["amount"]}
                # record the receiver's token change
                if log["to"] in tokens_change:
                    if log["token"] in tokens_change[log["to"]]:
                        tokens_change[log["to"]][log["token"]] += log["amount"]
                    else:
                        tokens_change[log["to"]][log["token"]]= log["amount"]
                else:
                    tokens_change[log["to"]] = {log["token"]: log["amount"]}
    # construct Token and Account objects
    for account_address, token_change in tokens_change.items():
        # tokens in one account
        tokens = [Token(address=token_address, balance_change=balance_change) for token_address, balance_change in token_change.items()]
        if account_address in userAccount:
            account_type = AccountType.USER_ACCOUNT
        else:
            account_type = AccountType.PROTOCOL_ACCOUNT
        accounts.append(Account(account_type=account_type, address=account_address, tokens=tokens))
    contract_address = decoded_transaction["to"]
    function_name = decoded_transaction["method"]
    
    # record the balanceOf query
    if function_name is not None and function_name == "balanceOf":
        if decoded_transaction["decoded input"]:
            account_address = list(decoded_transaction["decoded input"].values())[0]
            if account_address not in userAccount:
                if account_address in balanceOf_query:
                    balanceOf_query[account_address].add(contract_address)
                else:
                    balanceOf_query[account_address] = {contract_address}
                
    functions.append((contract_address, function_name, accounts))
    return transfer_sequence, functions, balanceOf_query

def record_msgValue(msgSender: str, msgReceiver: str, msgValue: Optional[str], chain: str, transfer_sequence: List[Transfer]) -> Dict[str, Dict[str, int]]:
    # msgValue = None | 0x0 | > 0x0
    tokens_change = {}
    if msgValue is None:
        return tokens_change
    else:
        msgValue_int = int(msgValue, 16)
        if msgValue_int == 0:
            return tokens_change
        else:
            # if msgValue > 0: update the transfer_sequence and the tokens_change
            try:
                token_address = SUPPORTED_NETWORK[chain]["stable_coin"]
                transfer_sequence.append(Transfer(sender_address=msgSender, 
                                                  receiver_address=msgReceiver, 
                                                  token_address=token_address, 
                                                  amount=msgValue_int))
                tokens_change[msgSender] = {token_address: -msgValue_int}
                tokens_change[msgReceiver] = {token_address: msgValue_int}
                return tokens_change
            except KeyError:
                print("[!]Could not find the stable coin of {}".format(chain))
                return tokens_change

def sort_transfer_sequence(transfer_sequence: List[Transfer]) -> List[Transfer]:
    last_known_index = 0
    for transfer in transfer_sequence:
        if transfer.index is None:
            transfer.index = last_known_index + 0.5
        else:
            last_known_index = transfer.index
    transfer_sequence.sort(key=lambda x: x.index)
    return transfer_sequence

def filter_raw_userCalls(raw_userCalls: List[Dict]) -> List[Dict]:
    #@todo-done the filterring should also depend on the tokens' addresses, account addresses involved in the user call
    #@note Currently we detect cyclic functions' name combine with accounts' address to remove cyclic user calls
    #@debug-start
    # for raw_userCall in raw_userCalls:
    #     functions: List[Tuple[str, str, List[Account]]] = raw_userCall["functions"]
    #     print([function[1] for function in functions])
    #     # for function in functions:
    #     #     accounts = function[2]
    #     #     account_address = [account.address for account in accounts]
    #     #     if account_address:
    #     #         print(account_address)
    #@debug-end
    filtered_raw_userCalls  = []
    raw_userCalls_len = len(raw_userCalls)
    i = 0
    while i < raw_userCalls_len:
        pattern_max_len = int((raw_userCalls_len - i) / 2)
        flag = False
        for pattern_len in range(1, pattern_max_len+1):
            pattern = list()
            pattern_accounts = set()
            for j in range(i, i + pattern_len):
                pattern.extend([function[1] for function in raw_userCalls[j]["functions"]])
                for function in raw_userCalls[j]["functions"]:
                    pattern_accounts.update(set([account.address for account in function[2]]))
            for j in range(i + pattern_len, raw_userCalls_len, pattern_len):
                function_sequence = []
                accounts = set()
                #@debug-start
                # print("j: ", j)
                # print("pattern_len: ", pattern_len)
                # print("j + pattern_len: ", j + pattern_len)
                # print("raw_userCalls_len: ", raw_userCalls_len)
                #@debug-end
                for k in range(j, min(j + pattern_len, raw_userCalls_len)):
                    function_sequence.extend([function[1] for function in raw_userCalls[k]["functions"]])
                    for function in raw_userCalls[k]["functions"]:
                        accounts.update(set([account.address for account in function[2]]))
                if pattern == function_sequence and pattern_accounts == accounts:
                    if not flag:
                        flag = True
                        #@debug-start
                        # print("Pattern matched")
                        # print("Pattern: ", pattern)
                        #@debug-end
                        filtered_raw_userCalls.extend(raw_userCalls[i: i + pattern_len])
                    i = j + pattern_len
                else:
                    break
            if flag:
                break
        if not flag:
            filtered_raw_userCalls.append(raw_userCalls[i])
            i += 1
    
    #@debug-start
    # print("#" * 150)
    # for raw_userCall in filtered_raw_userCalls:
    #     functions: List[Tuple[str, str, List[Account]]] = raw_userCall["functions"]
    #     print([function[1] for function in functions])
    #     # for function in functions:
    #     #     accounts = function[2]
    #     #     account_address = [account.address for account in accounts]
    #     #     if account_address:
    #     #         print(account_address)
    # exit()
    #@debug-end
    print("[*]The number of user calls after filterring: ", len(filtered_raw_userCalls)) #@debug
    return filtered_raw_userCalls
    
