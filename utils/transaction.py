from web3 import HTTPProvider, Web3
from web3._utils.abi import (
    get_abi_output_types, map_abi_data, 
    named_tree,
)
from web3._utils.events import get_event_data
from web3.exceptions import (
    InvalidEventABI,
    LogTopicError,
    MismatchedABI,
)
from web3.logs import (
    DISCARD,
    IGNORE,
    STRICT,
    WARN,
)
from hexbytes import (
    HexBytes,
)
from eth_abi.codec import (
    ABICodec,
)
from eth_abi.registry import (
    registry as default_registry,
)
from web3._utils.normalizers import (
    BASE_RETURN_NORMALIZERS,
)
from typing import List, Dict, Tuple, Set
import requests
import warnings
import json
import sys
import os

from utils.config import SUPPORTED_NETWORK

TOKEN_NAME: Dict[str, str] = dict() # {token_address: token_name}

class Transaction:
    def __init__(self, txhash: str, platform: str, init_userAccount: Set = set()) -> None:
        self.contract_cache = dict()
        self.delegate_call_cache = dict()
        self.user_account = init_userAccount
        self.event_sig_hex_cache = dict()
        self.not_verified_contract = set()
        self.beginning_flag = True
        self.txhash = txhash
        self.platform = platform
        self.raw_transaction, self.url, self.explorer_api_key = self.getRawTransaction()
        self.w3 = Web3(HTTPProvider(self.url))
        self.decoded_transaction = self.decode_raw_transaction(self.raw_transaction)
        # self.balance_map = dict()
        # self.generate_balance_map(self.balance_map, self.decoded_transaction)
        # self.incorporated_balance_change_map = list()
        # self.incorporate_actions(self.balance_map)

    def getRawTransaction(self) -> Tuple[Dict, str, str]:
        url, explorer_api_key = self.setPlatform()
        self.download_raw_transaction(url)
        with open("Data/{}_raw_transaction.json".format(self.txhash), 'r') as f:
            raw_transaction = json.load(f)
        raw_transaction = raw_transaction["result"]
        if not raw_transaction:
            print("[!]Error in downloading transaction")
            sys.exit(0)
        return raw_transaction, url, explorer_api_key

    def setPlatform(self) -> Tuple[str, str]:
        if self.platform == "ethereum":
            url = SUPPORTED_NETWORK["ethereum"]["quick_node"] #https://methodical-orbital-grass.quiknode.pro/fe07745a7483ec72082179b92c20cd104938bc8b/
            explorer_api_key = SUPPORTED_NETWORK["ethereum"]["api_key"]
            return url, explorer_api_key
        elif self.platform == "bsc":
            url = SUPPORTED_NETWORK["bsc"]["quick_node"]
            explorer_api_key = SUPPORTED_NETWORK["bsc"]["api_key"]
            return url, explorer_api_key
        else:
            print("[!]Unsupported blockchain platform: {}".format(self.platform))
            sys.exit(0)

    def download_raw_transaction(self, url: str) -> None:
        path = "Data/{}_raw_transaction.json".format(self.txhash)
        if os.path.exists(path):
            return
        else:
            client = HTTPProvider(url)
            params = [self.txhash,{ "tracer": "callTracer", "tracerConfig": {"withLog" : True}}]
            raw_transaction = client.make_request('debug_traceTransaction', params)
            if not os.path.exists("Data"):
                os.mkdir("Data")
            with open(path, 'w') as f:
                json.dump(raw_transaction, f)
    
    def decode_raw_transaction(self, raw_transaction: Dict) -> Dict:
        decode_flag = False
        if raw_transaction["type"] == "CREATE":
            raw_transaction["method"] = None
            raw_transaction["decoded input"] = None
            raw_transaction["decoded output"] = None
            raw_transaction["from"] = str(Web3.to_checksum_address(raw_transaction["from"]))
            raw_transaction["to"] = str(Web3.to_checksum_address(raw_transaction["to"]))

            if self.beginning_flag:
                # EOA
                self.user_account.add(raw_transaction["from"])
                # The contract created by the EOA at the beginning
                self.user_account.add(raw_transaction["to"])
                self.beginning_flag = False
            
            elif raw_transaction["from"] in self.user_account:
                # the contract created by the user contract is also a user contract
                self.user_account.add(raw_transaction["to"])
                # print("Current user account: {}".format(self.user_account)) #@debug
            
            readable_call = "call type:{calltype},from:{sender},{receiver}".format(
                calltype = raw_transaction["type"],
                sender = raw_transaction["from"],
                receiver = raw_transaction["to"],
            )

        else:
            contract_address = str(Web3.to_checksum_address(raw_transaction["to"]))
            if contract_address in self.contract_cache:
                # Get contract from cache
                contract = self.contract_cache[contract_address]
                decode_flag = True
                # print("contract from cache")
            else:
                # Not in cache
                if contract_address in self.not_verified_contract:
                    pass
                else:
                    abi = self.get_abi(contract_address)
                    try:
                            contract = self.w3.eth.contract(address = contract_address, abi = abi['result'])
                            decode_flag = True
                    except:
                        # Contract not verified
                        print("[!]Contract {} code not verified".format(contract_address))
                        self.not_verified_contract.add(contract_address)
            # Decode input and output
            if decode_flag:
                # Decode input
                fn_name = None
                try:
                    func_obj, func_params = contract.decode_function_input(raw_transaction["input"])
                    # Extract function name from func_obj
                    fn_name = str(func_obj).split(" ")[1].split("(")[0]
                    # Add to cache
                    self.contract_cache[contract_address] = contract

                    decodedInput = func_params
                except:
                    # Delegate call
                    print("[!]Contract {} could not find corresponding ABI".format(contract_address))
                    self.not_verified_contract.add(contract_address)
                    decodedInput = None
                # decode output
                if "output" in raw_transaction:
                    try:
                        # Find ABI events
                        abi_actions = [abi for abi in contract.abi if abi["type"] == "function"]
                        # print(abi_actions)
                        fn_abi = dict()
                        for abi in abi_actions:
                            if abi["name"] == fn_name:
                                fn_abi = abi
                                break
                        output = raw_transaction["output"]
                        decodedOutput = self.decode_output_data(fn_abi, output)
                    except:
                        decodedOutput = None
                else:
                    decodedOutput = None
            else:
                fn_name = None
                decodedInput = None
                decodedOutput = None
            
            raw_transaction["from"] = str(Web3.to_checksum_address(raw_transaction["from"]))
            raw_transaction["to"] = str(Web3.to_checksum_address(raw_transaction["to"]))
            if not "value" in raw_transaction:
                raw_transaction["value"] = None

            if not fn_name:
                raw_transaction["method"] = raw_transaction["input"][:10]
            else:
                raw_transaction["method"] = fn_name
            
            if not "input" in raw_transaction:
                raw_transaction["input"] = None
            if not "output" in raw_transaction:
                raw_transaction["output"] = None

            if self.beginning_flag:
                # EOA
                self.user_account.add(raw_transaction["from"])
                # The contract called by the EOA at the beginning
                self.user_account.add(raw_transaction["to"])
                self.beginning_flag = False
                # print("Current user account: {}".format(self.user_account)) #@debug
            
            if raw_transaction["type"] == "DELEGATECALL":
                if raw_transaction["from"] in self.delegate_call_cache:
                    self.delegate_call_cache[raw_transaction["from"]].add(raw_transaction["to"])
                else:
                    self.delegate_call_cache[raw_transaction["from"]] = {raw_transaction["to"]}

            readable_call = "call type:{calltype},from:{sender},{receiver}.{function}".format(
                calltype = raw_transaction["type"],
                sender = raw_transaction["from"],
                receiver = raw_transaction["to"],
                function = raw_transaction["method"],
            )

            raw_transaction["decoded input"] = decodedInput
            raw_transaction["decoded output"] = decodedOutput

            if decodedInput != None and decodedInput:
                readable_input = ""
                for key in decodedInput.keys():
                    if key == "":
                        readable_input += "{},".format(str(decodedInput[key]))
                    else:
                        readable_input += "{arg}={val},".format(arg = str(key), val = str(decodedInput[key]))
                readable_input = readable_input[:-1]
                readable_call += "({input})".format(input = readable_input)

            if decodedOutput != None and decodedOutput:
                readable_output = ""
                for key in decodedOutput.keys():
                    if key == "":
                        readable_output += "{},".format(str(decodedOutput[key]))
                    else:
                        readable_output += "{arg}={val},".format(arg = str(key), val = str(decodedOutput[key]))
                readable_output = readable_output[:-1]
                readable_call += " return({output})".format(output=readable_output)
        raw_transaction["readable action"] = readable_call

        if "logs" in raw_transaction:
            decoded_logs = list()
            for log in raw_transaction["logs"]:
                decoded_log = self.decode_log(log)
                # if decode log failed, try decode if it is a transfer event
                if "topics" in decoded_log:
                    if len(decoded_log["topics"]) > 0 and (decoded_log["topics"][0] == HexBytes("0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef") or decoded_log["topics"][0] == HexBytes("0x7df4d829704e19a12c4538a64d608b12d7b43a60fa92de3a91c81c4e9110cd0a")):
                            decoded_log = self.decode_transfer(log=log)
                decoded_logs.append(decoded_log)

            raw_transaction["logs"] = decoded_logs

        if "calls" in raw_transaction:
            for call in raw_transaction["calls"]:
                self.decode_raw_transaction(call)
        return raw_transaction

    def decode_output_data(self, fn_abi, data, normalizers=BASE_RETURN_NORMALIZERS):
        # type ignored b/c expects data arg to be HexBytes
        data = HexBytes(data)  # type: ignore
        types = get_abi_output_types(fn_abi)
        abi_codec = ABICodec(default_registry)
        decoded = abi_codec.decode(types, HexBytes(data))
        if normalizers:
            decoded = map_abi_data(normalizers, types, decoded)
        return named_tree(fn_abi["outputs"], decoded)

    def decode_log(self, log:Dict) -> Dict:
        processed_log = log
        contract_address = str(Web3.to_checksum_address(log["address"]))
        contract_address_collection = [contract_address]
        
        log["address"] = HexBytes(log["address"])
        log["topics"] = [HexBytes(i) for i in log["topics"]]
        log["data"] = HexBytes(log["data"])

        if contract_address in self.delegate_call_cache:
            contract_address_collection += list(self.delegate_call_cache[contract_address])
        else:
            pass
        
        for contract_address in contract_address_collection:
            if contract_address in self.contract_cache:
                contract = self.contract_cache[contract_address]
            else:
                abi = self.get_abi(contract_address)
                try:
                    contract = self.w3.eth.contract(address = contract_address, abi=abi["result"])
                    self.contract_cache[contract_address] = contract
                except:
                    print("[!]Contract {} code not verified".format(contract_address))
                    self.not_verified_contract.add(contract_address)
                    continue
            abi_events = [abi for abi in contract.abi if abi["type"] == "event"]
            receipt_event_signature_hex = self.w3.to_hex(log["topics"][0])
            if receipt_event_signature_hex in self.event_sig_hex_cache:
                event_name = self.event_sig_hex_cache[receipt_event_signature_hex]
            else:
                event_name = ""
                for event in abi_events:
                    # Get event signature components
                    name = event["name"]
                    inputs = [param["type"] for param in event["inputs"]]
                    inputs = ",".join(inputs)
                    # Hash event signature
                    event_signature_text = f"{name}({inputs})"
                    event_signature_hex = self.w3.to_hex(self.w3.keccak(text=event_signature_text))
                    # Find match between log's event signature and ABI's event signature
                    if event_signature_hex == receipt_event_signature_hex:
                        event_name = event["name"]
                        # Add to cache
                        self.event_sig_hex_cache[receipt_event_signature_hex] = event_name
                        # print("event_name from api")
                        break
            if event_name != "":
                try:
                    abi_codec = contract.events[event_name]().w3.codec
                    event_abi = contract.events[event_name]().abi
                    processed_log = self.decode_log_data(abi_codec, event_abi,log)
                    break
                except:
                    print("[!]{contract_address}: Encountering error while decoding {event_name}".format(
                        contract_address=contract_address, 
                        event_name=event_name))
                    continue
            else:
                # delegate call
                print("[!]{contract_address}: Could not find corresponding event".format(contract_address=contract_address))
                continue
        return processed_log

    def get_abi(self, address: str) -> Dict:
        if self.platform == "bsc":
            abi_endpoint = \
                f"https://api.bscscan.com/api?module=contract&action=getabi&address={address}&apikey={self.explorer_api_key}"
        elif self.platform == "ethereum":
            abi_endpoint = \
                f"https://api.etherscan.io/api?module=contract&action=getabi&address={address}&apikey={self.explorer_api_key}"
        elif self.platform == "fantom":
            abi_endpoint = \
                f"https://api.ftmscan.com/api?module=contract&action=getabi&address={address}&apikey={self.explorer_api_key}"
        abi = json.loads(requests.get(abi_endpoint).text)
        return abi

    def decode_log_data(self, abi_codec, event_abi:dict, log:dict, errors = WARN) -> Dict:
        # @todo-done data on BSC does not have index, need to insert (check if index is necessary)
        if "index" in log:
            log["logIndex"] = log["index"]
        else:
            log["logIndex"] = None
        log["transactionIndex"] = None
        log["transactionHash"] = None
        log["blockHash"] = None
        log["blockNumber"] = None
        
        try:
            decoded_event = get_event_data(abi_codec, event_abi, log)
        except (MismatchedABI, LogTopicError, InvalidEventABI, TypeError) as e:
            if errors == DISCARD:
                pass
                # print("errors == DISCARD")
            elif errors == IGNORE:
                # type ignores b/c rich_log set on 1092 conflicts with mutated types
                new_log = MutableAttributeDict(log)  # type: ignore
                new_log["errors"] = e
                rich_log = AttributeDict(new_log)  # type: ignore
            elif errors == STRICT:
                raise e
            else:
                warnings.warn(
                    f"The log with transaction hash: {log['transactionHash']!r} "
                    f"and logIndex: {log['logIndex']} encountered the following "
                    f"error during processing: {type(e).__name__}({e}). It has "
                    "been discarded."
                )
        if decoded_event['event'] == "Transfer":
            processed_log = self.transafer_event(decoded_event)
        elif decoded_event['event'] == "Withdrawal" and Web3.to_checksum_address(decoded_event['address']) == SUPPORTED_NETWORK[self.platform]["stable_coin"]:
            processed_log = self.withdrawal_event(decoded_event)
        elif decoded_event['event'] == "Deposit" and Web3.to_checksum_address(decoded_event['address']) == SUPPORTED_NETWORK[self.platform]["stable_coin"]:
            processed_log = self.deposit_event(decoded_event)
        else:
            processed_log = self.other_event(decoded_event)
        return processed_log

    def transafer_event(self, decoded_event: Dict) -> Dict:
        event_name = decoded_event['event']
        token_address = Web3.to_checksum_address(decoded_event['address'])
        args = list(decoded_event['args'].keys())
        from_address = "Unknown"
        to_address = "Unknown"
        amount = "Unknown"
        try:
            from_address = Web3.to_checksum_address(decoded_event['args'][args[0]])
            to_address = Web3.to_checksum_address(decoded_event['args'][args[1]])
            amount = decoded_event['args'][args[2]]
        except:
            print("[!]Unexpected Transfer event format: {}".format(str(decoded_event['args'])))
            processed_log = self.other_event(decoded_event)
            return processed_log

        readable_event = \
            "{token_address}.{event_name}(from:{from_address}, to:{to_address}, amount:{amount})"\
            .format(token_address = str(token_address), 
                    event_name = event_name, 
                    from_address = str(from_address), 
                    to_address = str(to_address), 
                    amount = str(amount))
        processed_log = {
            "name" : event_name, 
            "token": token_address, 
            "from": from_address, 
            "to": to_address, 
            "amount": amount,
            "readable event": readable_event,
            "index": decoded_event['logIndex'],
        }

        if token_address not in TOKEN_NAME:
            self.record_token_name(token_address=token_address)

        return processed_log
    
    def withdrawal_event(self, decoded_event: Dict) -> Dict:
        event_name = decoded_event['event']
        token_address = Web3.to_checksum_address(decoded_event['address'])
        args = list(decoded_event['args'].keys())
        from_address = "Unknown"
        to_address = "Unknown"
        amount = "Unknown"
        try:
            from_address = Web3.to_checksum_address(decoded_event['args'][args[0]])
            to_address = token_address
            amount = decoded_event['args'][args[1]]
        except:
            print("[!]Unexpected Transfer event format: {}".format(str(decoded_event['args'])))
            processed_log = self.other_event(decoded_event)
            return processed_log
        
        readable_event = \
            "{token_address}.{event_name}(from:{from_address}, to:{to_address}, amount:{amount})"\
            .format(token_address = str(token_address), 
                    event_name = event_name, 
                    from_address = str(from_address), 
                    to_address = str(to_address), 
                    amount = str(amount))
        processed_log = {
            "name" : event_name, 
            "token": token_address, 
            "from": from_address, 
            "to": to_address, 
            "amount": amount,
            "readable event": readable_event,
            "index": decoded_event['logIndex'],
        }
        
        if token_address not in TOKEN_NAME:
            self.record_token_name(token_address=token_address)
        
        return processed_log
        
    def deposit_event(self, decoded_event: Dict) -> Dict:
        event_name = decoded_event['event']
        token_address = Web3.to_checksum_address(decoded_event['address'])
        args = list(decoded_event['args'].keys())
        from_address = "Unknown"
        to_address = "Unknown"
        amount = "Unknown"
        try:
            from_address = token_address
            to_address = Web3.to_checksum_address(decoded_event['args'][args[0]])
            amount = decoded_event['args'][args[1]]
        except:
            print("[!]Unexpected Transfer event format: {}".format(str(decoded_event['args'])))
            processed_log = self.other_event(decoded_event)
            return processed_log
        
        readable_event = \
            "{token_address}.{event_name}(from:{from_address}, to:{to_address}, amount:{amount})"\
            .format(token_address = str(token_address), 
                    event_name = event_name, 
                    from_address = str(from_address), 
                    to_address = str(to_address), 
                    amount = str(amount))
        processed_log = {
            "name" : event_name, 
            "token": token_address, 
            "from": from_address, 
            "to": to_address, 
            "amount": amount,
            "readable event": readable_event,
            "index": decoded_event['logIndex'],
        }

        if token_address not in TOKEN_NAME:
            self.record_token_name(token_address=token_address)

        return processed_log


    def other_event(self, decoded_event: Dict) -> Dict:
        event_name = decoded_event['event']
        event_recorder = Web3.to_checksum_address(decoded_event['address'])
        args = list(decoded_event['args'].keys())
        parameters = dict()
        parameters_string = ""
        for arg in args:
            parameters[arg] = decoded_event['args'][arg]
            parameters_string += "{_arg}:{_data},"\
                .format(
                    _arg = str(arg), 
                    _data = str(decoded_event['args'][arg]))
        readable_event = \
            "{event_recorder}.{event_name}({parameters_string})"\
                .format(
                    event_recorder = str(event_recorder), 
                    event_name = event_name, 
                    parameters_string = parameters_string[:-1])
        processed_log = {
            "name" : event_name, 
            "event recorder": event_recorder, 
            "decoded parameters": parameters,
            "readable event": readable_event,
            "index": decoded_event['logIndex'],
        }
        return processed_log

    def decode_transfer(self, log: Dict) -> Dict:
        if "index" in log:
            index = log["index"]
        else:
            index = None
        token_address = str(Web3.to_checksum_address(log["address"]))
        sender_address = str(Web3.to_checksum_address(log["topics"][1][-20:]))
        receiver_address = str(Web3.to_checksum_address(log["topics"][2][-20:]))
        amount = int(log["data"].hex(), 16)
        readable_event = "{token_address}.Transfer(from:{sender}, to:{receiver}, amount:{amount})".format(
            token_address = token_address,
            sender = sender_address,
            receiver = receiver_address,
            amount = amount
        )

        if token_address not in TOKEN_NAME:
            self.record_token_name(token_address=token_address)
        
        return {
            "name": "Transfer",
            "token": token_address,
            "from": sender_address,
            "to": receiver_address,
            "amount": amount,
            "readable event": readable_event,
            "index": index,
            }
    
    def record_token_name(self, token_address: str):
        abi = [{"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"}]
        try:
            contract = self.w3.eth.contract(address=token_address, abi=abi)
            token_symbol = contract.functions.symbol().call()
        except:
            token_symbol = "Unknown"
        TOKEN_NAME[token_address] = token_symbol