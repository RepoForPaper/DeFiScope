from typing import Optional, Dict

from utils.actionType import TransferActionType



class Transfer:
    def __init__(self, sender_address: Optional[str], receiver_address: Optional[str], token_address: Optional[str], amount: int, index: Optional[int] = None) -> None:
        self.sender_address = sender_address
        self.receiver_address = receiver_address
        self.token_address = token_address
        self.amount = amount
        self.index = index
        self.transfer_type = self.match_TransferAction()
    
    def match_TransferAction(self) -> TransferActionType:
        if self.amount > 0:
            if self.sender_address == "0x0000000000000000000000000000000000000000" and self.amount > 0:
                return TransferActionType.MINT
            elif self.receiver_address == "0x0000000000000000000000000000000000000000" \
                or self.receiver_address == "0x000000000000000000000000000000000000dEaD" \
                and self.amount > 0:
                return TransferActionType.BURN
            else:
                return TransferActionType.TRANSFER
        else:
            return TransferActionType.UNDEFINED
    
    def log(self) -> str:
        return "\t[-]Transfer type: " + self.transfer_type.value + "\n" + \
                "\t[-]Sender address: " + (self.sender_address if isinstance(self.sender_address, str) else str(self.sender_address)) + "\n" + \
                "\t[-]Receiver address: " + (self.receiver_address if isinstance(self.receiver_address, str) else str(self.receiver_address)) + "\n" + \
                "\t[-]Token address: " + (self.token_address if isinstance(self.token_address, str) else str(self.token_address)) + "\n" + \
                "\t[-]Amount: " + str(self.amount) + "\n"
    
    # @debug
    def debug_log(self) -> None:
        print("*" * 150)
        print("Transfer type: ", self.transfer_type.value)
        print("Sender address: ", self.sender_address if isinstance(self.sender_address, str) else str(self.sender_address))
        print("Receiver address: ", self.receiver_address if isinstance(self.receiver_address, str) else str(self.receiver_address))
        print("Token address: ", self.token_address if isinstance(self.token_address, str) else str(self.token_address))
        print("Amount: ", self.amount)
        print("Index: ", self.index if isinstance(self.index, int) else str(self.index))

    def debug_store_data(self) -> Dict:
        return {
            "sender_address": self.sender_address,
            "receiver_address": self.receiver_address,
            "token_address": self.token_address,
            "amount": self.amount,
            "transfer_type": self.transfer_type.value
        }