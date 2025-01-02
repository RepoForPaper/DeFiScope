from typing import Dict

class FlashLoan:
    def __init__(self, isFlashloan: bool) -> None:
        self.isFlashloan = isFlashloan
        self.flashLoanTokens = dict()
    
    #@debug
    def debug_store_data(self) -> Dict:
        return {
            "isFlashloan": self.isFlashloan,
            "flashLoanTokens": self.flashLoanTokens
        }