from enum import Enum
from typing import List, Dict, Optional

class AccountType(Enum):
    USER_ACCOUNT = "User Controlled Account" # including EOA, the contract EOA directly interacts with, the contract created by all known user accounts
    PROTOCOL_ACCOUNT = "DeFi Protocol Account"

class Token:
    """
    Args:
        address: the address of the token
        balance_change: the change of the balance
    """
    def __init__(self, address: str, balance_change: Optional[int]) -> None:
        self.address = address
        self.balance_change = balance_change

    def debug_store_data(self) -> Dict:
        return {
            "address": self.address,
            "balance_change": self.balance_change
        }

class Account:
    """
    BalanceUnit:
        |-- AccountType
        |-- Address
        '-- List(Token)
                    |-- Address
                    '-- BalanceChange

    Args:
        account_type: the type of the account (EOA, Contract)
        address: the address of the account
        list(Token): a list of tokens owned by the account
    """
    def __init__(self, account_type: AccountType, address: str, tokens: List[Token]) -> None:
        self.account_type = account_type
        self.address = address
        self.tokens = tokens
    
    #@debug
    def debug_log(self) -> None:
        print("*" * 150)
        print("Account Address: ", self.address)
        print("Account Type: ", self.account_type)
        print("Tokens: ")
        for token in self.tokens:
            print("Token Address: ", token.address)
            print("Balance Change: ", token.balance_change)

    def debug_store_data(self) -> Dict:
        return {
            "account_type": self.account_type.value,
            "address": self.address,
            "tokens": [token.debug_store_data() for token in self.tokens]
        }