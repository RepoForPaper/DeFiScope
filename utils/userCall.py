from ast import mod
import re
from typing import List, Dict, Tuple, Set, Optional
from itertools import combinations
import json
import requests

from utils.transaction import TOKEN_NAME
from utils.function import Function, CONTRACT_CACHE
from utils.priceChangeInference import PriceChangeInferenceUnit, Tendency, PriceChangeInferenceKey
from utils.actionType import DeFiActionType
from utils.defiAction import DeFiAction
from utils.transfer import Transfer
from utils.transferGraph import TransferGraph, Edge
from utils.actionType import TransferActionType
from utils.account import AccountType, Account
from utils.flashLoan import FlashLoan
from utils.config import SUPPORTED_NETWORK

PRICE_CALCULATION_KEYWORDS = [r"price", r"getAmount", r"latestAnswer", r"swap\w*For\w*", r"swap\w*To\w*", r"swap\w*From\w*", r"reward", r"mintFor", r"valueOf", r"get\w*Price", r"buy", r"purchase", r"sell", r"supply", r"performanceFee", r"wantLockedTotal", r"refresh", r"pledgein", r"joinswapPoolAmountIn", r"unstake", r"calcLiquidityShare", r"borrowSC", r"getTotalAvailableCollateralValue", r"cacheAssetPrice"]

# Liquidity pools and their tokens
POOLS = dict() # {pool_address: set(token_address)}

# All price calculation functions in the transaction
PRICE_CALCULATION_FUNCTION: Dict[str, Dict[str, Tuple[str, List[str], Set[str]]]] = dict() # {contract_address: {entry_point: (code_snippet, [invovled tokens], {involved contract})}}

# Mapping between contract address and contract name
CONTRACT_NAME: Dict[str, str] = CONTRACT_CACHE.copy() # {contract_address: contract_name}
#@todo-done we need a map to record all balance change before the price calculation function

class UserCall:
    """
    UserCall class is used to store the user's call information
    The smallest unit for price manipulation detection
   
    Args:
        set[str]: a set of detected user accounts
        list(Transfer): a list of transfer actions
        list(tuple(str,str,list(Account))): a list of functions called in the user call (contract address, function name, a list of tokens transfered in the function)
    
    Attributes:
        defiActions: a list of DeFiAction objects
        userCallPurpose: a list of tuple combines index and possible purposes of the user call(DeFiActionType != UNDEFINED)
        price_calculation_function (list(index, Function)): a list of tuple combines index and function objects supposed to calculate the price in this call
        token_address_list: tokens transfered in the user call
        price_change_inference: a list of PriceChangeUnit objects
    """
    def __init__(self, userAccount: Set[str], transfer_sequence: List[Transfer], functions: List[Tuple[str,str,List[Account]]], balanceOf_query: Dict[str, Set[str]], platform: str) -> None:
        self.userAccount = userAccount
        self.functions = functions
        self.balanceOf_query = balanceOf_query
        self.transfer_sequence = transfer_sequence
        self.cumulatedBalanceChange = self.cumulateBalanceChangeInAccounts(transfer_sequence=transfer_sequence)
        self.global_token_balance_change = dict() # Global balance change of all accounts in the transaction: {pool_address: {token_address: balance_change}}
        self.defiActions = self.match_DeFiAction(userAccount=userAccount,transfer_sequence=transfer_sequence)
        self.userCallPurpose = [defiAction.defiPurpose
                                for defiAction in self.defiActions 
                                if defiAction.defiPurpose != DeFiActionType.UNDEFINED]
        #@todo-done allow undefined action and pool address in the price change inference
        self.token_address_list = self.extract_token_address_list(functions=functions)
        self.price_calculation_functions = self.extract_price_calculation_function(functions=functions,platform=platform)
        self.merged_price_calculation_function = self.merge_price_calculation_functions(price_calculation_functions=self.price_calculation_functions)
        #@todo-done bind the token price change to specific DeFi purpose
        # self.priceChangeInference = self.generate_price_change_inference(defiActions=self.defiActions,functions=functions)
        self.priceChangeInference = None
        self.flashLoan = FlashLoan(False)
        self.relatedDeFiAction: Optional[DeFiAction] = None
        
    def match_DeFiAction(self, userAccount: Set[str], transfer_sequence: List[Transfer]) -> List[DeFiAction]:
        # New version
        defiActions = []
        transferGraph = TransferGraph(transfer_sequence=transfer_sequence, userAccount=userAccount)
        # match swap action
        swap_transferSequence = transferGraph.search_swap_transferSequence()
        swap_actions = transferGraph.match_swap_action(swap_transferSequence=swap_transferSequence)
        defiActions.extend(swap_actions)
        # match addLiquidity action
        addLiquidity_transferSequence = transferGraph.search_addLiquidity_transferSequence()
        addLiquidity_actions = transferGraph.match_addLiquidity_action(addLiquidity_transferSequence=addLiquidity_transferSequence)
        defiActions.extend(addLiquidity_actions)
        # match removeLiquidity action
        removeLiquidity_transferSequence = transferGraph.search_removeLiquidity_transferSequence()
        removeLiquidity_actions = transferGraph.match_removeLiquidity_action(removeLiquidity_transferSequence=removeLiquidity_transferSequence)
        defiActions.extend(removeLiquidity_actions)
        # match getToken action
        getToken_transferSequence = transferGraph.search_getToken_transferSequence()
        getToken_actions = transferGraph.match_getToken_action(getToken_transferSequence=getToken_transferSequence)
        defiActions.extend(getToken_actions)
        # match spendToken action
        spendToken_transferSequence = transferGraph.search_spendToken_transferSequence()
        spendToken_actions = transferGraph.match_spendToken_action(spendToken_transferSequence=spendToken_transferSequence)
        defiActions.extend(spendToken_actions)
        # match deposit action
        deposit_transferSequence = transferGraph.search_deposit_transferSequence()
        deposit_actions = transferGraph.match_deposit_action(deposit_transferSequence=deposit_transferSequence)
        defiActions.extend(deposit_actions)
        # match withdraw action
        withdraw_transferSequence = transferGraph.search_withdraw_transferSequence()
        withdraw_actions = transferGraph.match_withdraw_action(withdraw_transferSequence=withdraw_transferSequence)
        defiActions.extend(withdraw_actions)
        # match borrow action
        borrow_transferSequence = transferGraph.search_borrow_transferSequence()
        borrow_actions = transferGraph.match_borrow_action(borrow_transferSequence=borrow_transferSequence)
        defiActions.extend(borrow_actions)

        if not defiActions:
            # If no predefined DeFi action is found, we consider it as a undefined action
            defiActions.append(DeFiAction(transfer_sequence=[], userAccount=userAccount, purpose=DeFiActionType.UNDEFINED))
        else:
            self.recordSwapPool(defiActions=defiActions)
        return defiActions
    def cumulateBalanceChangeInAccounts(self, transfer_sequence: List[Transfer]) -> Dict[str, Dict[str, int]]:
        """
        Return:
            {account: {token: balance change}}: the total balance change of the token in the account (except the user account)
        """
        cumulatedBalanceChange: Dict[str, Dict[str, int]] = {}
        for transfer in transfer_sequence:
            if transfer.sender_address not in self.userAccount:
                if transfer.sender_address not in cumulatedBalanceChange:
                    cumulatedBalanceChange[transfer.sender_address] = {}
                if transfer.token_address not in cumulatedBalanceChange[transfer.sender_address]:
                    cumulatedBalanceChange[transfer.sender_address][transfer.token_address] = -transfer.amount
                else:
                    cumulatedBalanceChange[transfer.sender_address][transfer.token_address] -= transfer.amount
            if transfer.receiver_address not in self.userAccount:
                if transfer.receiver_address not in cumulatedBalanceChange:
                    cumulatedBalanceChange[transfer.receiver_address] = {}
                if transfer.token_address not in cumulatedBalanceChange[transfer.receiver_address]:
                    cumulatedBalanceChange[transfer.receiver_address][transfer.token_address] = transfer.amount
                else:
                    cumulatedBalanceChange[transfer.receiver_address][transfer.token_address] += transfer.amount
        return cumulatedBalanceChange
        
    def calTotalTokenBalanceChangeInPool(self, transfer_sequence: List[Transfer]) -> Dict[str, Dict[str, int]]:
        """
        Return:
            {pool: {token: balance change}}: the total balance change of the token in the pool of the user call
        """
        #@todo-done any user call related to a recorded pool should be considered as a suspicious user call
        tokenBalanceChangeInPool: Dict[str, Dict[str, int]] = {}
        for pool in POOLS.keys():
            #@note we only consider the pool with two tokens
            if len(POOLS[pool]) != 2:
                continue
            tokenBalanceChange: Dict[str, int] = {}
            for token in POOLS[pool]:
                totalAmountOut = sum([transfer.amount for transfer in transfer_sequence if transfer.sender_address == pool and transfer.token_address == token])
                totalAmountIn = sum([transfer.amount for transfer in transfer_sequence if transfer.receiver_address == pool and transfer.token_address == token])
                totalBalanceChange = totalAmountIn - totalAmountOut
                tokenBalanceChange[token] = totalBalanceChange
            if all([balanceChange == 0 for balanceChange in tokenBalanceChange.values()]):
                continue
            tokenBalanceChangeInPool[pool] = tokenBalanceChange
        return tokenBalanceChangeInPool

    def recordSwapPool(self, defiActions: List[DeFiAction]) -> None:
        #@todo-done record all swap pools and their tokens -> could be used to infer the price change manually and define manipulate pool purpose
        for defiAction in defiActions:
            if defiAction.defiPurpose == DeFiActionType.SWAP:
                if defiAction.pool not in POOLS:
                    POOLS[defiAction.pool] = set()
                POOLS[defiAction.pool].add(defiAction.token_in[0])
                POOLS[defiAction.pool].add(defiAction.token_out[0])

    def extract_price_calculation_function(self, functions: List[Tuple[str,Optional[str],List[Account]]], platform: str) -> List[Tuple[int, Function]]:
        # @note currently we use keyword matching to extract the price calculation function:
        # 1. For custom price calculation function: Search for the function that contains the keyword "price"
        # 2. For DEX: Search for the function that contains the keyword "getAmount" (getAmountsIn, getAmountsOut, getAmountIn, getAmountOut)
        # 3. For some Oracle: Search for the function that contains the keyword "latestAnswer"
        #@todo-done if the DeFiActionType is SWAP, we could consider there is price caluclation function in the user call (How to extract this unknown function?)
        price_calculation_functions = []
        for index, (contract_address, function_name, _) in enumerate(functions):
            if function_name is None:
                print("[!]Error: Encounter function with no name in contract {contract_address}".format(contract_address=contract_address))
            else:
                if any([re.search(keyword, function_name, re.IGNORECASE) for keyword in PRICE_CALCULATION_KEYWORDS]):
                    price_calculation_functions.append((index, Function(contract_address=contract_address,entry_point=function_name, platform=platform)))
        
        return price_calculation_functions

    def merge_price_calculation_functions(self, price_calculation_functions: List[Tuple[int, Function]]) -> List[Tuple[int, str]]:
        merged_price_calculation_functions = []
        merged_code_snippet = ""
        entry_contractAddress = ""
        entry_function = ""
        involved_contract = set()
        for _, function in price_calculation_functions:
            if function.code_snippet:
                if entry_contractAddress == "" and entry_function == "":
                    entry_contractAddress = function.contract_address
                    entry_function = function.entry_point
                involved_contract.add(function.contract_address)
                merged_code_snippet += "//" + function.contract_name + ".sol\n" + function.code_snippet
                if function.contract_address not in CONTRACT_NAME:
                    CONTRACT_NAME[function.contract_address] = function.contract_name
        
        if merged_code_snippet:
            involved_contract.union(set(self.balanceOf_query.keys()))
            if entry_contractAddress in PRICE_CALCULATION_FUNCTION:
                if entry_function in PRICE_CALCULATION_FUNCTION[entry_contractAddress]:
                    pass
                else:
                    PRICE_CALCULATION_FUNCTION[entry_contractAddress][entry_function] = (merged_code_snippet, self.token_address_list.copy(), involved_contract)
            else:
                PRICE_CALCULATION_FUNCTION[entry_contractAddress] = {entry_function: (merged_code_snippet, self.token_address_list.copy(), involved_contract)}

            merged_price_calculation_functions.append((price_calculation_functions[-1][0], merged_code_snippet))

        return merged_price_calculation_functions

    def extract_token_address_list(self, functions: List[Tuple[str,str,List[Account]]]) -> List[str]:
        # @todo-done how to extract the involved token address in a price calculation
        # @note currently we suppose all tokens transferred in the user call are involved in the price calculation (Can only infer the price change of the token that is transferred in the user call)
        # @todo-done should bind the token address with the pool address and add the pool address restriction to the price change inference statements
        token_address_list = set()
        for (_, _, accounts) in functions:
            for account in accounts:
                if account.account_type == AccountType.PROTOCOL_ACCOUNT:
                    for token in account.tokens:
                        token_address_list.add(token.address)
        return list(token_address_list)

    def generate_price_change_inference(self, 
                                        defiActions: List[DeFiAction], 
                                        functions: List[Tuple[str,str,List[Account]]],
                                        model=None,
                                        tokenizer=None,
                                        device=None) -> Dict[PriceChangeInferenceKey, Dict[str, Tendency]]:
        """
        Args:
            defiPurpose: a list of DeFiActionType objects
            functions: a list of Function objects
        
        Return:
            Dict[PriceChangeInferenceKey, Dict[str, Tendency]]: a dictionary of price change inference
        
        #@note Price change inference could be done by LLMs(if price calculation function found) or manually (if the transfer happens in a recorded possible pool)
        """
        #@todo-done implement PriceChangeInferenceKey
        price_change_inference = {}
        tokenBalanceChangeInPool = self.calTotalTokenBalanceChangeInPool(transfer_sequence=self.transfer_sequence)
        #@debug-start
        if defiActions:
            print("[i]DeFi purpose of the user call: ",[defiAction.defiPurpose.value for defiAction in defiActions])
        #@debug-end
        # Price calculation function found in this user call
        for defiAction in defiActions:
            tokenPriceChangeTendency = {}
            if self.merged_price_calculation_function and defiAction.pool != "Undefined":
                print("[+]Found price calculation function in the user call, pool address: {pool_address}".format(pool_address=defiAction.pool)) #@debug
                # Price calculation function found
                # if defiAction.pool in CONTRACT_NAME:
                #     pass
                # elif defiAction.pool in CONTRACT_CACHE:
                #     CONTRACT_NAME[defiAction.pool] = CONTRACT_CACHE[defiAction.pool]
                # else:
                #     self.record_contract_name(contract_address=defiAction.pool, platform=platform)
                
                for (target_index, code_snippet) in self.merged_price_calculation_function:
                    variables_change = self.extract_variables_change(functions=functions)
                    
                    # @debug-start
                    # print("Target index: " + str(target_index))
                    # print("Variables change: ")
                    # print(variables_change)
                    #@debug-end
                    # @todo-done should bind the token price change with the pool address (bind the token balance change with the pool address -> bind the token price change with the pool address)
                    priceChangeUnit = PriceChangeInferenceUnit(
                        pool_address=defiAction.pool,
                        token_address_list=self.token_address_list,
                        code_snippet=code_snippet,
                        variables_change=variables_change,
                        contract_name_mapping=CONTRACT_NAME,
                        token_name_mapping=TOKEN_NAME,
                        model=model,
                        tokenizer=tokenizer,
                        device=device
                    )
                    # Cumulate the effect of the price change tendency
                    tokenPriceChangeTendency = self.cumulate_price_change_tendency(priceChangeUnit=priceChangeUnit, tokenPriceChangeTendency=tokenPriceChangeTendency)
                price_change_inference[PriceChangeInferenceKey(defiActionType=defiAction.defiPurpose, manipulated_pool=defiAction.pool)] = tokenPriceChangeTendency
        
        # Price calculation function not found in this user call, but the balance of the token in recorded pool with price calculation function is changed
        if not self.merged_price_calculation_function:
            pool_with_balance_change = set(self.cumulatedBalanceChange.keys())
            pool_with_price_calculation = set(PRICE_CALCULATION_FUNCTION.keys())
            affected_pool = pool_with_balance_change.intersection(pool_with_price_calculation)
            if affected_pool:
                print("[+]Price calculation function not found in the user call, but the balance of the token in recorded pool with price calculation function is changed")
                for pool in affected_pool:
                    # if pool in CONTRACT_NAME:
                    #     pass
                    # elif pool in CONTRACT_CACHE:
                    #     CONTRACT_NAME[pool] = CONTRACT_CACHE[pool]
                    # else:
                    #     self.record_contract_name(contract_address=pool, platform=platform)

                    variables_change = {pool: self.cumulatedBalanceChange[pool].copy()}
                    for _, (code_snippet, involved_tokens, involved_contract) in PRICE_CALCULATION_FUNCTION[pool].items():
                        # Check if there is any token balance change in the involved contract
                        for contract_account in involved_contract:
                            if contract_account in variables_change.keys():
                                pass
                            else:
                                token_balance_change_in_account = self.cumulatedBalanceChange.get(contract_account, {}).copy()
                                if token_balance_change_in_account:
                                    variables_change[contract_account] = token_balance_change_in_account
                        tokenPriceChangeTendency = {}
                        priceChangeUnit = PriceChangeInferenceUnit(
                            pool_address=pool,
                            token_address_list=involved_tokens,
                            code_snippet=code_snippet,
                            variables_change=variables_change,
                            contract_name_mapping=CONTRACT_NAME,
                            token_name_mapping=TOKEN_NAME,
                            model=model,
                            tokenizer=tokenizer,
                            device=device
                        )
                        tokenPriceChangeTendency = self.cumulate_price_change_tendency(priceChangeUnit=priceChangeUnit, tokenPriceChangeTendency=tokenPriceChangeTendency)
                        price_change_inference[PriceChangeInferenceKey(defiActionType=[defiAction.defiPurpose for defiAction in defiActions], manipulated_pool=pool)] = tokenPriceChangeTendency

        # Price calculation function not found in this user call,and the balance of the token in a recorded liquidity pool is changed 
        if not price_change_inference:
            # price calculation function not found
            #@todo-done given total balance change, action purpose, pool address, construct new prompt for the price change inference (lower priority)
            if tokenBalanceChangeInPool:
                for pool, tokenBalanceChange in tokenBalanceChangeInPool.items():
                    # if pool in CONTRACT_NAME:
                    #     pass
                    # elif pool in CONTRACT_CACHE:
                    #     CONTRACT_NAME[pool] = CONTRACT_CACHE[pool]
                    # else:
                    #     self.record_contract_name(contract_address=pool, platform=platform)

                    tokenPriceChangeTendency = self.generate_price_change_inference_in_known_pool(pool=pool, tokenBalanceChange=tokenBalanceChange, model=model, tokenizer=tokenizer, device=device)
                    # print("[+]Price calculation function not found in the user call, token balance in recorded pool {pool_address} is changed".format(pool_address=pool))
                    # tokenPriceChangeTendency = {}
                    # variables_change = {pool: tokenBalanceChange}
                    # priceChangeUnit = PriceChangeInferenceUnit(
                    #     pool_address=pool,
                    #     token_address_list=list(tokenBalanceChange.keys()),
                    #     code_snippet=None,
                    #     variables_change=variables_change
                    # )
                    # tokenPriceChangeTendency = self.cumulate_price_change_tendency(priceChangeUnit=priceChangeUnit, tokenPriceChangeTendency=tokenPriceChangeTendency)
                    price_change_inference[
                        PriceChangeInferenceKey(
                            defiActionType=[defiAction.defiPurpose for defiAction in defiActions], 
                            manipulated_pool=pool)] = tokenPriceChangeTendency
        return self.prune_price_change_inference(price_change_inference=price_change_inference)
    
    def generate_price_change_inference_in_known_pool(self, pool: str, tokenBalanceChange: Dict[str, int], model, tokenizer, device) -> Dict[str, Tendency]:
        print("[+]Price calculation function not found in the user call, token balance in recorded pool {pool_address} is changed".format(pool_address=pool))
        tokenPriceChangeTendency = {}
        variables_change = {pool: tokenBalanceChange}
        priceChangeUnit = PriceChangeInferenceUnit(
            pool_address=pool,
            token_address_list=list(tokenBalanceChange.keys()),
            code_snippet=None,
            variables_change=variables_change,
            contract_name_mapping=CONTRACT_NAME,
            token_name_mapping=TOKEN_NAME,
            model=model,
            tokenizer=tokenizer,
            device=device
        )
        tokenPriceChangeTendency = self.cumulate_price_change_tendency(priceChangeUnit=priceChangeUnit, tokenPriceChangeTendency=tokenPriceChangeTendency)
        return tokenPriceChangeTendency

    def extract_variables_change(self, functions: List[Tuple[str,str,List[Account]]]) -> Dict[str, Dict[str, int]]:
        """
        Return:
            dict(str, dict(str, int)): {account_address: {token_address: balance_change}}
        """
        # @todo-done how to extract the variable change in a price calculation (map balance change to its corresponding variable name)(variable should be in the extracted function)
        # @todo-done connect token name and its address through balanceOf?
        # @todo-done Check if the balance of token is changed in the price calculation function (check if the balance changed while the price is calculated)
        # @todo-done How to deal with the variables change across different user calls: variables changed in one user call but use them to calculate the price in another user call
        # @note currently we suppose the variable change is the balance change of the token before the price calculation function
        variables_change = dict()
        for (_, _, accounts) in functions:
            for account in accounts:
                if account.account_type == AccountType.PROTOCOL_ACCOUNT:
                    if account.address not in variables_change:
                        variables_change[account.address] = dict()
                    for token in account.tokens:
                        if token.address not in variables_change[account.address]:
                            variables_change[account.address][token.address] = token.balance_change
                        else:
                            variables_change[account.address][token.address] += token.balance_change
        return variables_change
    
    def cumulate_price_change_tendency(self, priceChangeUnit: PriceChangeInferenceUnit, tokenPriceChangeTendency: Dict[str, Tendency]) -> Dict[str, Tendency]:
        for token_address, price_change_tendency in priceChangeUnit.price_change_inference.items():
            if price_change_tendency == Tendency.INCREASE or price_change_tendency == Tendency.DECREASE:
                #@note cumulative effect of the price change tendency: decrease + increase = uncertain
                #@todo-done could we just use the overall transfer amount at the end of the user call to infer the price change tendency (done in the low priority inference)
                #@note currently we only record the increase and decrease tendency of the token price
                if token_address not in tokenPriceChangeTendency:
                    tokenPriceChangeTendency[token_address] = price_change_tendency
                else:
                    if (price_change_tendency == Tendency.INCREASE and tokenPriceChangeTendency[token_address] == Tendency.DECREASE) or \
                        (price_change_tendency == Tendency.DECREASE and tokenPriceChangeTendency[token_address] == Tendency.INCREASE):
                        tokenPriceChangeTendency[token_address] = Tendency.UNCERTAIN
                    else:
                        tokenPriceChangeTendency[token_address] = price_change_tendency
        return tokenPriceChangeTendency

    def prune_price_change_inference(self, price_change_inference: Dict[PriceChangeInferenceKey, Dict[str, Tendency]]) -> Dict[PriceChangeInferenceKey, Dict[str, Tendency]]:
        """
        Prune the price change inference by removing the redundant price change inference (Empty, Uncertain, Replicated)
        """
        # Remove the Empty and Uncertain tendency
        del_keys = []
        for priceChangeInferenceKey, tendency_dict in price_change_inference.items():
            if not tendency_dict:
                del_keys.append(priceChangeInferenceKey)
            else:
                if all(tendency == Tendency.UNCERTAIN for _, tendency in tendency_dict.items()):
                    del_keys.append(priceChangeInferenceKey)
        
        for priceChangeInferenceKey in del_keys:
            price_change_inference.pop(priceChangeInferenceKey)
        
        # Remove the Replicated tendency
        poolTokenTendency_actionType: Dict[Tuple, List[DeFiActionType]] = dict()
        new_price_change_inference = {}
        for priceChangeInferenceKey, tendency_dict in price_change_inference.items():
            poolTokenTendency = tuple(tendency_dict.items())
            poolTokenTendency += (priceChangeInferenceKey.manipulated_pool, )
            if poolTokenTendency not in poolTokenTendency_actionType:
                poolTokenTendency_actionType[poolTokenTendency] = [priceChangeInferenceKey.defiActionType]
            else:
                poolTokenTendency_actionType[poolTokenTendency].append(priceChangeInferenceKey.defiActionType)
        
        for poolTokenTendency, actionType in poolTokenTendency_actionType.items():
            if len(actionType) > 1:
                new_price_change_inference[PriceChangeInferenceKey(
                    defiActionType=actionType, 
                    manipulated_pool=poolTokenTendency[-1])
                    ] = {token: tendency for token, tendency in poolTokenTendency[:-1]}
            else:
                new_price_change_inference[PriceChangeInferenceKey(
                    defiActionType=actionType[0], 
                    manipulated_pool=poolTokenTendency[-1])
                    ] = {token: tendency for token, tendency in poolTokenTendency[:-1]}
        
        return new_price_change_inference
            
    def record_contract_name(self, contract_address: str, platform: str):
        explorer_api_key = SUPPORTED_NETWORK[platform]["api_key"]
        api_prefix = SUPPORTED_NETWORK[platform]["api_prefix"]
        abi_endpoint = \
                    f"https://api{api_prefix}/api?module=contract&action=getsourcecode&address={contract_address}&apikey={explorer_api_key}"
        try:
            ret = json.loads(requests.get(abi_endpoint).text)
            contract_name = ret["result"][0]["ContractName"]
            if not contract_name:
                CONTRACT_NAME[contract_address] = "Unknown"
            else:
                CONTRACT_NAME[contract_address] = contract_name
        except:
            CONTRACT_NAME[contract_address] = "Unknown"
    
    def update_gloabl_token_balance_change(self) -> Dict[str, Dict[str, int]]:
        updated_global_token_balance_change = self.global_token_balance_change.copy()
        for account in self.cumulatedBalanceChange.keys():
            if account in updated_global_token_balance_change:
                for token in self.cumulatedBalanceChange[account].keys():
                    if token in updated_global_token_balance_change[account]:
                        updated_global_token_balance_change[account][token] += self.cumulatedBalanceChange[account][token]
                    else:
                        updated_global_token_balance_change[account][token] = self.cumulatedBalanceChange[account][token]
            else:
                updated_global_token_balance_change[account] = self.cumulatedBalanceChange[account].copy()
        return updated_global_token_balance_change.copy()
    
    def update_contract_address_name_mapping(self, platform:str) -> None:
        tokenBalanceChangeInPool = self.calTotalTokenBalanceChangeInPool(transfer_sequence=self.transfer_sequence)
        for defiAction in self.defiActions:
            if self.merged_price_calculation_function and defiAction.pool != "Undefined":
                if defiAction.pool in CONTRACT_NAME:
                    pass
                elif defiAction.pool in CONTRACT_CACHE:
                    CONTRACT_NAME[defiAction.pool] = CONTRACT_CACHE[defiAction.pool]
                else:
                    self.record_contract_name(contract_address=defiAction.pool, platform=platform)
        if not self.merged_price_calculation_function:
            pool_with_balance_change = set(self.cumulatedBalanceChange.keys())
            pool_with_price_calculation = set(PRICE_CALCULATION_FUNCTION.keys())
            affected_pool = pool_with_balance_change.intersection(pool_with_price_calculation)
            if affected_pool:
                for pool in affected_pool:
                    if pool in CONTRACT_NAME:
                        pass
                    elif pool in CONTRACT_CACHE:
                        CONTRACT_NAME[pool] = CONTRACT_CACHE[pool]
                    else:
                        self.record_contract_name(contract_address=pool, platform=platform)
        if tokenBalanceChangeInPool:
            for pool, _ in tokenBalanceChangeInPool.items():
                if pool in CONTRACT_NAME:
                    pass
                elif pool in CONTRACT_CACHE:
                    CONTRACT_NAME[pool] = CONTRACT_CACHE[pool]
                else:
                    self.record_contract_name(contract_address=pool, platform=platform)
        for account, _ in self.cumulatedBalanceChange.items():
            if account in CONTRACT_NAME or account in self.userAccount:
                pass
            elif account in CONTRACT_CACHE:
                CONTRACT_NAME[account] = CONTRACT_CACHE[account]
            else:
                self.record_contract_name(contract_address=account, platform=platform)

    def getDeFiAction(self, defiActionType: DeFiActionType) -> Optional[DeFiAction]:
        """
        Search the DeFi action from the list of DeFi actions
        """
        for defiAction in self.defiActions:
            if defiAction.defiPurpose == defiActionType:
                return defiAction
        return None
