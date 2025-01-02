from typing import List, Optional

from utils.userCall import UserCall, POOLS
from utils.actionType import DeFiActionType
from utils.priceChangeInference import PriceChangeInferenceKey

# def matchRelatedActions(userCalls: List[UserCall]) -> None:
#     """
#     Match the related getToken and spendToken actions in the user calls: for profit calculation (Cross userCall Swap)
#     """
#     for spendTokenIndex in range(len(userCalls)):
#         if DeFiActionType.SPENDTOKEN in userCalls[spendTokenIndex].userCallPurpose and len(userCalls[spendTokenIndex].userCallPurpose) == 1:
#             spendTokenAction = userCalls[spendTokenIndex].getDeFiAction(defiActionType=DeFiActionType.SPENDTOKEN)
#             if not spendTokenAction:
#                 continue
#             for getTokenIndex in range(spendTokenIndex + 1, len(userCalls)):
#                 if DeFiActionType.GETTOKEN in userCalls[getTokenIndex].userCallPurpose \
#                     and len(userCalls[getTokenIndex].userCallPurpose) == 1 \
#                     and userCalls[getTokenIndex].relatedDeFiAction == None:
#                     getTokenAction = userCalls[getTokenIndex].getDeFiAction(defiActionType=DeFiActionType.GETTOKEN)
#                     if not getTokenAction:
#                         continue
#                     if spendTokenAction.initiator == getTokenAction.initiator and spendTokenAction.pool == getTokenAction.pool:
#                         userCalls[spendTokenIndex].relatedDeFiAction = getTokenAction
#                         userCalls[getTokenIndex].relatedDeFiAction = spendTokenAction
#                         break

def matchRelatedActions(userCalls: List[UserCall]) -> None:
    """
    Match the related getToken and spendToken actions in the user calls: for profit calculation (Cross userCall Swap)
    """
    for index in range(len(userCalls)):
        if DeFiActionType.SPENDTOKEN in userCalls[index].userCallPurpose \
            and len(userCalls[index].userCallPurpose) == 1 \
            and userCalls[index].relatedDeFiAction == None \
            and not userCalls[index].flashLoan.isFlashloan:
            spendTokenIndex = index
            spendTokenAction = userCalls[spendTokenIndex].getDeFiAction(defiActionType=DeFiActionType.SPENDTOKEN)
            if not spendTokenAction:
                continue
            for getTokenIndex in range(spendTokenIndex + 1, len(userCalls)):
                if DeFiActionType.GETTOKEN in userCalls[getTokenIndex].userCallPurpose \
                    and len(userCalls[getTokenIndex].userCallPurpose) == 1 \
                    and userCalls[getTokenIndex].relatedDeFiAction == None \
                    and not userCalls[getTokenIndex].flashLoan.isFlashloan:
                    getTokenAction = userCalls[getTokenIndex].getDeFiAction(defiActionType=DeFiActionType.GETTOKEN)
                    if not getTokenAction:
                        continue
                    if spendTokenAction.initiator == getTokenAction.initiator \
                        and spendTokenAction.pool == getTokenAction.pool \
                        and spendTokenAction.token_in != getTokenAction.token_out:
                        userCalls[spendTokenIndex].relatedDeFiAction = getTokenAction
                        userCalls[getTokenIndex].relatedDeFiAction = spendTokenAction

                        if spendTokenAction.pool not in POOLS:
                            POOLS[spendTokenAction.pool] = set()
                        POOLS[spendTokenAction.pool].add(spendTokenAction.token_in[0])
                        POOLS[spendTokenAction.pool].add(getTokenAction.token_out[0])
                        # infer_price_change_after_matched(userCalls=userCalls, spendTokenIndex=spendTokenIndex, getTokenIndex=getTokenIndex)

                        break
        elif DeFiActionType.GETTOKEN in userCalls[index].userCallPurpose \
            and len(userCalls[index].userCallPurpose) == 1 \
            and userCalls[index].relatedDeFiAction == None \
            and not userCalls[index].flashLoan.isFlashloan:
            # Example: LUSD 0x1eeef7b9a12b13f82ba04a7951c163eb566aa048050d6e9318b725d7bcec6bfa L48-L57
            getTokenIndex = index
            getTokenAction = userCalls[getTokenIndex].getDeFiAction(defiActionType=DeFiActionType.GETTOKEN)
            if not getTokenAction:
                continue
            for spendTokenIndex in range(getTokenIndex + 1, len(userCalls)):
                if DeFiActionType.SPENDTOKEN in userCalls[spendTokenIndex].userCallPurpose \
                    and len(userCalls[spendTokenIndex].userCallPurpose) == 1 \
                    and userCalls[spendTokenIndex].relatedDeFiAction == None \
                    and not userCalls[spendTokenIndex].flashLoan.isFlashloan:
                    spendTokenAction = userCalls[spendTokenIndex].getDeFiAction(defiActionType=DeFiActionType.SPENDTOKEN)
                    if not spendTokenAction:
                        continue
                    if spendTokenAction.initiator == getTokenAction.initiator \
                        and spendTokenAction.pool == getTokenAction.pool \
                        and spendTokenAction.token_in != getTokenAction.token_out:
                        userCalls[spendTokenIndex].relatedDeFiAction = getTokenAction
                        userCalls[getTokenIndex].relatedDeFiAction = spendTokenAction

                        if getTokenAction.pool not in POOLS:
                            POOLS[getTokenAction.pool] = set()
                        POOLS[getTokenAction.pool].add(spendTokenAction.token_in[0])
                        POOLS[getTokenAction.pool].add(getTokenAction.token_out[0])
                        # infer_price_change_after_matched(userCalls=userCalls, spendTokenIndex=spendTokenIndex, getTokenIndex=getTokenIndex)

                        break

# def infer_price_change_after_matched(userCalls: List[UserCall], spendTokenIndex: int, getTokenIndex: int) -> None:
#     if not userCalls[spendTokenIndex].priceChangeInference:
#         price_change_inference = {}
#         tokenBalanceChangeInPool = userCalls[spendTokenIndex].calTotalTokenBalanceChange(transfer_sequence=userCalls[spendTokenIndex].transfer_sequence)
#         if tokenBalanceChangeInPool:
#             for pool, tokenBalanceChange in tokenBalanceChangeInPool.items():
#                 tokenPriceChangeTendency = userCalls[spendTokenIndex].generate_price_change_inference_in_known_pool(pool=pool, tokenBalanceChange=tokenBalanceChange)
#                 price_change_inference[
#                     PriceChangeInferenceKey(
#                         defiActionType=[defiAction.defiPurpose for defiAction in userCalls[spendTokenIndex].defiActions],
#                         manipulated_pool=pool)] = tokenPriceChangeTendency
#         userCalls[spendTokenIndex].priceChangeInference = userCalls[spendTokenIndex].prune_price_change_inference(price_change_inference=price_change_inference)
    
#     if not userCalls[getTokenIndex].priceChangeInference:
#         price_change_inference = {}
#         tokenBalanceChangeInPool = userCalls[getTokenIndex].calTotalTokenBalanceChange(transfer_sequence=userCalls[getTokenIndex].transfer_sequence)
#         if tokenBalanceChangeInPool:
#             for pool, tokenBalanceChange in tokenBalanceChangeInPool.items():
#                 tokenPriceChangeTendency = userCalls[getTokenIndex].generate_price_change_inference_in_known_pool(pool=pool, tokenBalanceChange=tokenBalanceChange)
#                 price_change_inference[
#                     PriceChangeInferenceKey(
#                         defiActionType=[defiAction.defiPurpose for defiAction in userCalls[getTokenIndex].defiActions],
#                         manipulated_pool=pool)] = tokenPriceChangeTendency
#         userCalls[getTokenIndex].priceChangeInference = userCalls[getTokenIndex].prune_price_change_inference(price_change_inference=price_change_inference)