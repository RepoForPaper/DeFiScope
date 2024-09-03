from typing import List, Tuple, Set, Optional, Dict
from utils.transfer import Transfer
from utils.actionType import DeFiActionType

class DeFiAction:
    """
    Args:
        list[Transfer]: a sequence contains Transfer objects
    
    Attributes:
        Initiator: the address who initiates the action
        Receiver: the address who receives the output token
        Amount_in: the amount of token_in
        Amount_out: the amount of token_out
        Token_in: the token address of input token
        Token_out: the token address of output token
        Pool: the address of the pool where the action happens
        defiAction: the supposed purpose of the action

    initiator sends amount_in token_in (to pool)
    receiver gets amount_out token_out (from pool)
    """
    def __init__(self, transfer_sequence: List[Transfer], userAccount: Set[str], purpose: DeFiActionType) -> None:
        #@todo-done support multiple input and output tokens
        self.transfer_sequence = transfer_sequence
        (
            self.initiator, 
            self.receiver, 
            self.amount_in, 
            self.amount_out, 
            self.token_in, 
            self.token_out, 
            self.pool, 
            self.defiPurpose
            ) = self.match_DeFiPurpose(transfer_sequence=transfer_sequence, userAccount=userAccount, purpose=purpose)

    def match_DeFiPurpose(
            self, 
            transfer_sequence: List[Optional[Transfer]], 
            userAccount: Set[str], purpose: DeFiActionType) -> Tuple[str, str, List[int], List[int], List[str], List[str], str, DeFiActionType]:
        if purpose == DeFiActionType.UNDEFINED:
            return (None, None, [0], [0], [None], [None], "Undefined", DeFiActionType.UNDEFINED)
        
        elif purpose == DeFiActionType.ADDLIQUIDITY:
            transfer_1 = transfer_sequence[0]
            transfer_2 = transfer_sequence[1]
            mint = transfer_sequence[2]
            return (transfer_1.sender_address,
                    mint.receiver_address,
                    [transfer_1.amount, transfer_2.amount],
                    [mint.amount],
                    [transfer_1.token_address, transfer_2.token_address],
                    [mint.token_address],
                    mint.token_address,
                    purpose)
                
        elif purpose == DeFiActionType.REMOVELIQUIDITY:
            burn = transfer_sequence[0]
            transfer_1 = transfer_sequence[1]
            transfer_2 = transfer_sequence[2]
            return (burn.sender_address,
                    transfer_1.receiver_address,
                    [burn.amount],
                    [transfer_1.amount, transfer_2.amount],
                    [burn.token_address],
                    [transfer_1.token_address, transfer_2.token_address],
                    burn.token_address,
                    purpose)
        
        elif purpose == DeFiActionType.SWAP:
            transfer_1 = transfer_sequence[0]
            transfer_n = transfer_sequence[-1]
            return (transfer_1.sender_address, 
                    transfer_n.receiver_address,
                    [transfer_1.amount],
                    [transfer_n.amount],
                    [transfer_1.token_address],
                    [transfer_n.token_address],
                    transfer_n.sender_address,
                    purpose)
                    
        elif purpose == DeFiActionType.GETTOKEN:
            transfer_1 = transfer_sequence[0]
            transfer_2 = transfer_sequence[1]
            if transfer_1.sender_address in userAccount and transfer_2.receiver_address in userAccount:
                return (transfer_1.sender_address,
                        transfer_2.receiver_address,
                        [0],
                        [transfer_2.amount],
                        [None],
                        [transfer_2.token_address],
                        "Undefined",
                        DeFiActionType.U2UTRANSFER)
            return (transfer_2.receiver_address,
                    transfer_2.receiver_address,
                    [0],
                    [transfer_2.amount],
                    [None],
                    [transfer_2.token_address],
                    transfer_2.sender_address,
                    purpose)
        
        elif purpose == DeFiActionType.SPENDTOKEN:
            transfer_1 = transfer_sequence[0]
            transfer_2 = transfer_sequence[1]
            if transfer_1.sender_address in userAccount and transfer_2.receiver_address in userAccount:
                return (transfer_1.sender_address,
                        transfer_2.receiver_address,
                        [transfer_1.amount],
                        [0],
                        [transfer_1.token_address],
                        [None],
                        "Undefined",
                        DeFiActionType.U2UTRANSFER)
            return (transfer_1.sender_address,
                    transfer_2.receiver_address,
                    [transfer_1.amount],
                    [0],
                    [transfer_1.token_address],
                    [None],
                    transfer_2.receiver_address,
                    purpose)
        
        elif purpose == DeFiActionType.DEPOSIT:
            transfer = transfer_sequence[0] # transfer deposited asset
            mint = transfer_sequence[1] # mint credentials
            return (mint.receiver_address,
                    mint.receiver_address,
                    [transfer.amount],
                    [mint.amount],
                    [transfer.token_address],
                    [mint.token_address],
                    transfer.receiver_address,
                    purpose)
        
        elif purpose == DeFiActionType.WITHDRAW:
            burn = transfer_sequence[0] # burn credentials
            transfer = transfer_sequence[1] # get withdrawn asset
            return (burn.sender_address,
                    burn.sender_address,
                    [burn.amount],
                    [transfer.amount],
                    [burn.token_address],
                    [transfer.token_address],
                    transfer.sender_address,
                    purpose)
        
        elif purpose == DeFiActionType.BORROW:
            mint = transfer_sequence[0] # mint debt
            transfer = transfer_sequence[1] # get borrowed asset
            return (mint.receiver_address,
                    mint.receiver_address,
                    [0],
                    [transfer.amount],
                    [None],
                    [transfer.token_address],
                    transfer.sender_address,
                    purpose)
        
    def log(self) -> str:
        return "\t[-]DeFi Purpose: " + self.defiPurpose.value + "\n" + \
            "\t[-]Initiator: " + (self.initiator if isinstance(self.initiator, str) else str(self.initiator)) + "\n" + \
            "\t[-]Receiver: " + (self.receiver if isinstance(self.receiver, str) else str(self.receiver)) + "\n" + \
            "\t[-]Token in: " + str(self.token_in) + "\n" + \
            "\t[-]Amount in: " + str(self.amount_in) + "\n" + \
            "\t[-]Token out: " + str(self.token_out) + "\n" + \
            "\t[-]Amount out: " + str(self.amount_out) + "\n" + \
            "\t[-]Action pool: " + (self.pool if isinstance(self.pool, str) else str(self.pool)) + "\n"
    
    # @debug
    def debug_log(self) -> None:
        print("*" * 150)
        print("Defi Purpose: ", self.defiPurpose.value)
        print("Initiator: ", self.initiator if isinstance(self.initiator, str) else str(self.initiator))
        print("Receiver: ", self.receiver if isinstance(self.receiver, str) else str(self.receiver))
        print("Token in: ", str(self.token_in))
        print("Amount in: ", str(self.amount_in))
        print("Token out: ", str(self.token_out))
        print("Amount out: ", str(self.amount_out))
        print("Action pool: ", self.pool if isinstance(self.pool, str) else str(self.pool))

    def debug_store_data(self) -> Dict:
        return {
            "transfer_sequence": [transfer.debug_store_data() for transfer in self.transfer_sequence],
            "initiator": self.initiator,
            "receiver": self.receiver,
            "amount_in": self.amount_in,
            "amount_out": self.amount_out,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "pool": self.pool,
            "defiPurpose": self.defiPurpose.value
        }