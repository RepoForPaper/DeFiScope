from enum import Enum

class TransferActionType(Enum):
    """
    Transfer:
        sender_address != 0x0 and receiver_address != 0x0
    Mint:
        sender_address == 0x0
    Burn:
        receiver_address == 0x0 / 0xdead
    """
    TRANSFER = "Transfer"
    MINT = "Mint"
    BURN = "Burn"
    UNDEFINED = "Undefined"
    

class DeFiActionType(Enum):
    """
    Combination of transfer actions
    
    AddLiquidity:
        Transfer_1 + Transfer_2 -> Mint
        Initiator: Transfer.sender_address
        Receiver: Mint.receiver_address
        Pool: Transfer.receiver_address
        Amount_in: [Transfer_1.amount, Transfer_2.amount]
        Amount_out: [Mint.amount]
        Token_in: [Transfer_1.token_address, Transfer_2.token_address]
        Token_out: [Mint.token_address,]

    RemoveLiquidity:
        Burn -> Transfer_1 + Transfer_2
        Initiator: Burn.sender_address
        Receiver: Transfer.receiver_address
        Pool: Transfer.sender_address
        Amount_in: [Burn.amount]
        Amount_out: [Transfer_1.amount, Transfer_2.amount]
        Token_in: [Burn.token_address]
        Token_out: [Transfer_1.token_address, Transfer_2.token_address]

    Swap:
        @todo-done record all pools in the swap
        Transfer_1 + Transfer_2 ... + Transfer_n
        Initiator: Transfer_1.sender_address
        Receiver: Transfer_n.receiver_address
        Pool: Transfer_n.sender_address
        Amount_in: [Transfer_1.amount]
        Amount_out: [Transfer_n.amount]
        Token_in: [Transfer_1.token_address]
        Token_out: [Transfer_2.token_address]

    Claim (flashloan / flash swap / get reward) (Condition: Transfer.receiver in UserAccount, UserAccount only receive token, does not send token):
        Transfer(Undefined) + Transfer
        Initiator: Transfer.receiver_address
        Receiver: Transfer.receiver_address
        Pool: Transfer.sender_address
        Amount_in: [0]
        Amount_out: [Transfer.amount]
        Token_in: [None]
        Token_out: [Transfer.token_address]
    
    Stake (return flashloan / return flash swap) (Condition: Transfer.sender in UserAccount, UserAccount only send token, does not receive token):
        Transfer + Transfer(Undefined)
        Initiator: Transfer.sender_address
        Receiver: Transfer.receiver_address
        Pool: Transfer.receiver_address
        Amount_in: [Transfer.amount]
        Amount_out: [0]
        Token_in: [Transfer.token_address]
        Token_out: [None]
    
    Deposit
        Transfer + Mint
        Initiator: Transfer.sender_address
        Receiver: Mint.receiver_address
        Pool: Transfer.receiver_address
        Amount_in: [Transfer.amount]
        Amount_out: [Mint.amount]
        Token_in: [Transfer.token_address]
        Token_out: [Mint.token_address]

    Withdraw
        Burn + Transfer
        Initiator: Burn.sender_address
        Receiver: Transfer.receiver_address
        Pool: Transfer.sender_address
        Amount_in: [Burn.amount]
        Amount_out: [Transfer.amount]
        Token_in: [Burn.token_address]
        Token_out: [Transfer.token_address]
    
    Borrow
        Transfer + Mint
        Initiator: Mint.receiver_address
        Receiver: Transfer.receiver_address
        Pool: Transfer.sender_address
        Amount_in: [0]
        Amount_out: [Transfer.amount]
        Token_in: [None]
        Token_out: [Transfer.token_address]

    User account to User account Transfer (Condition: Transfer.sender in UserAccount and Transfer.receiver in UserAccount):
        Transfer + Transfer(Undefined) / Transfer(Undefined) + Transfer
        Initiator: Transfer.sender_address
        Receiver: Transfer.receiver_address
        Pool: Undefined
        Amount_in: [Transfer.amount / 0]
        Amount_out: [Transfer.amount / 0]
        Token_in: [Transfer.token_address / None]
        Token_out: [Transfer.token_address / None]
    """
    ADDLIQUIDITY = "Add Liquidity"
    REMOVELIQUIDITY = "Remove Liquidity"
    SWAP = "Swap"
    GETTOKEN = "Get Token"
    SPENDTOKEN = "Spend Token"
    DEPOSIT = "Deposit"
    WITHDRAW = "Withdraw"
    BORROW = "Borrow"
    U2UTRANSFER = "User account to User account Transfer"
    UNDEFINED = "Undefined"