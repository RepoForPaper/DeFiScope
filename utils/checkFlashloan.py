from typing import List, Set
from utils.userCall import UserCall
from utils.actionType import DeFiActionType

#@todo-done do an investigation on the common flashloan interest rate
#@note currently we set the interest rate cap as 0.1, basically this is higher than any common flashloan interest rate
FLASHLOAN_INTEREST_CAP = 0.1

def flagFlashloan(userCalls: List[UserCall], userAccount: Set[str]) -> None:
    """
    Flag the get token and spend token which belongs to a flashloan in the user calls: find the compliant get token and spend token pair
    """
    for getTokenIndex in range(len(userCalls)):
        if DeFiActionType.GETTOKEN in userCalls[getTokenIndex].userCallPurpose \
            and not userCalls[getTokenIndex].flashLoan.isFlashloan \
            and userCalls[getTokenIndex].relatedDeFiAction == None:
            getTokenActions = [defiAction for defiAction in userCalls[getTokenIndex].defiActions if defiAction.defiPurpose == DeFiActionType.GETTOKEN]
            for getTokenAction in getTokenActions:
                for spendTokenIndex in range(getTokenIndex + 1, len(userCalls)):
                    if DeFiActionType.SPENDTOKEN in userCalls[spendTokenIndex].userCallPurpose \
                        and not userCalls[spendTokenIndex].flashLoan.isFlashloan \
                        and userCalls[spendTokenIndex].relatedDeFiAction == None:
                        spendTokenActions = [defiAction for defiAction in userCalls[spendTokenIndex].defiActions if defiAction.defiPurpose == DeFiActionType.SPENDTOKEN]
                        for spendTokenAction in spendTokenActions:
                            if getTokenAction.initiator == spendTokenAction.initiator \
                                and getTokenAction.initiator in userAccount \
                                and getTokenAction.pool == spendTokenAction.pool \
                                and getTokenAction.token_out[0] == spendTokenAction.token_in[0] \
                                and getTokenAction.amount_out[0] * (1 + FLASHLOAN_INTEREST_CAP) >= spendTokenAction.amount_in[0] \
                                and spendTokenAction.amount_in[0] >= getTokenAction.amount_out[0]:
                                # Condition:
                                # 1. Two actions happen in the same pool 
                                # 2. Both are called by the same user account
                                # 3. The spent token is the same as the received token 
                                # 4. The amount of the spent token is larger than that of the received token, but less than that of the received token plus the interest cap
                                getTokenFlashLoan = userCalls[getTokenIndex].flashLoan
                                getTokenFlashLoan.isFlashloan = True
                                if spendTokenAction.token_in[0] in getTokenFlashLoan.flashLoanTokens:
                                    getTokenFlashLoan.flashLoanTokens[spendTokenAction.token_in[0]] -= spendTokenAction.amount_in[0]
                                else:
                                    getTokenFlashLoan.flashLoanTokens[spendTokenAction.token_in[0]] = -spendTokenAction.amount_in[0]

                                spendTokenFlashLoan = userCalls[spendTokenIndex].flashLoan
                                spendTokenFlashLoan.isFlashloan = True
                                if getTokenAction.token_out[0] in spendTokenFlashLoan.flashLoanTokens:
                                    spendTokenFlashLoan.flashLoanTokens[getTokenAction.token_out[0]] += getTokenAction.amount_out[0]
                                else:
                                    spendTokenFlashLoan.flashLoanTokens[getTokenAction.token_out[0]] = getTokenAction.amount_out[0]
                                
                                break