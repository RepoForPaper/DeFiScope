from typing import List, Tuple, Dict, Set, Optional

from utils.userCall import UserCall
from utils.priceChangeInference import Tendency
from utils.actionType import DeFiActionType
from utils.defiAction import DeFiAction
from utils.transfer import Transfer
from utils.flashLoan import FlashLoan

class DetectResult:
    def __init__(self, 
                 matched_pattern: Optional[str],
                 isAttack: bool, 
                 profit_token: Optional[str], 
                 profit: Optional[int], 
                 attack_sequence: Optional[List[Optional[DeFiAction] | DeFiActionType | List[DeFiActionType]]], 
                 manipulated_pool: Optional[str], 
                 price_change_tendency: Optional[List[Dict[str, Tendency]]], 
                 manipulation_transfer_sequence: Optional[List[List[Transfer]]]) -> None:
        self.matched_pattern = matched_pattern
        self.isAttack = isAttack
        self.profit_token = profit_token
        self.profit = profit
        self.attack_sequence = attack_sequence
        self.manipulated_pool = manipulated_pool
        self.price_change_tendency = price_change_tendency
        self.manipulation_transfer_sequence = manipulation_transfer_sequence

class Detector:
    def __init__(self, userCalls: List[UserCall], userAccount: Set[str]) -> None:
        # @todo-done How to match the pattern from a list of user calls
        # e.g. if there are 10 user calls, only 3 of them are price manipulation related (userCall_3, userCall_5, userCall_7)
        # How to match the pattern from the 3 user calls
        # @todo-done combine all user calls which have defi purpose or price change inference to find the pattern
        # @note we check the combination of 3 user calls
        self.userCalls = userCalls
        self.userAccount = userAccount
        self.results = self.detect()
    
    def detect(self) -> List[DetectResult]:
        """
        Return:
            list[DeFiAction]: attack sequence
            str: manipulated pool address
            dict[str]: token price change tendency
            list[list[Transfer]]: transfer sequence in manipulation steps
            bool: whether the combination is a price manipulation attack
        """
        # @note currently we only detect on one rule: Buy in low price –> Inflate the price –> Sell in high price
        # @todo-done bind action with the token it manipulates
        # @todo-done rewrite function detect: price_change_inference structure is changed
        # @todo-urgent should consider the cumulative price change inference between userCall 0 and userCall 2
        userCall_0 = self.userCalls[0]
        userCall_1 = self.userCalls[1]
        userCall_2 = self.userCalls[2]
        detect_result = []
        #@debug-start speed up testing
        if not userCall_1.priceChangeInference and not userCall_0.priceChangeInference:
            return [DetectResult(
                matched_pattern=None,
                isAttack=False,
                profit_token=None,
                profit=None,
                attack_sequence=None,
                manipulated_pool=None,
                price_change_tendency=None,
                manipulation_transfer_sequence=None
            )]
        #@debug-end

        #@todo-done support all defined DeFi actions
        # Obtain -> Manipulate -> Sell
        action_index_1 = [index 
                          for index, defiAction in enumerate(userCall_0.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.SWAP, DeFiActionType.GETTOKEN}]
        action_index_2 = [index 
                          for index, defiAction in enumerate(userCall_2.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.SWAP, DeFiActionType.SPENDTOKEN}]
        if action_index_1 and action_index_2:
            for index_1 in action_index_1:
                defiAction_1 = userCall_0.defiActions[index_1]
                for index_2 in action_index_2:
                    defiAction_2 = userCall_2.defiActions[index_2]
                    if ((defiAction_1.defiPurpose == DeFiActionType.GETTOKEN and defiAction_2.defiPurpose == DeFiActionType.SPENDTOKEN) \
                        or (defiAction_1.defiPurpose == DeFiActionType.GETTOKEN and defiAction_2.defiPurpose == DeFiActionType.SWAP) \
                        or (defiAction_1.defiPurpose == DeFiActionType.SWAP and defiAction_2.defiPurpose == DeFiActionType.SPENDTOKEN) \
                        or (defiAction_1.defiPurpose == DeFiActionType.SWAP and defiAction_2.defiPurpose == DeFiActionType.SWAP)) \
                        and defiAction_1.receiver in self.userAccount \
                        and defiAction_2.initiator in self.userAccount \
                        and defiAction_1.token_out[0] == defiAction_2.token_in[0]:
                        for priceChangeInferenceKey in userCall_1.priceChangeInference.keys():
                            manipulated_pool = priceChangeInferenceKey.manipulated_pool
                            if manipulated_pool == defiAction_2.pool:
                                if userCall_2.relatedDeFiAction:
                                    target_tokens = userCall_2.relatedDeFiAction.token_out
                                else:
                                    target_tokens = defiAction_2.token_out

                                profit_maker = self.userAccount.copy()
                                profit_maker.add(defiAction_2.receiver)

                                transfer_in_manipulation = [userCall_1.transfer_sequence]
                                relatedDeFiAction_Type = None
                                if userCall_1.relatedDeFiAction:
                                    transfer_in_manipulation.append(userCall_1.relatedDeFiAction.transfer_sequence)
                                    relatedDeFiAction_Type = userCall_1.relatedDeFiAction.defiPurpose     
                                                          
                                check_token_price_increase = defiAction_2.token_in
                                for token in check_token_price_increase:
                                    if token in userCall_1.priceChangeInference[priceChangeInferenceKey] and userCall_1.priceChangeInference[priceChangeInferenceKey][token] == Tendency.INCREASE:
                                        self.record_result(
                                            matched_pattern="Buy / Get in normal price -> Manipulate -> Sell / Spend in manipulated price",
                                            defiActions=[defiAction_1, userCall_0.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[defiAction_1, userCall_0.relatedDeFiAction, 
                                                             priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_1.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )
                                
                                check_token_price_decrease = defiAction_2.token_out
                                for token in check_token_price_decrease:
                                    if token in userCall_1.priceChangeInference[priceChangeInferenceKey] and userCall_1.priceChangeInference[priceChangeInferenceKey][token] == Tendency.DECREASE:
                                        self.record_result(
                                            matched_pattern="Buy / Get in normal price -> Manipulate -> Sell / Spend in manipulated price",
                                            defiActions=[defiAction_1, userCall_0.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[defiAction_1, userCall_0.relatedDeFiAction, 
                                                             priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_1.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )
        
        # Manipulate -> Obtain -> Sell
        action_index_1 = [index 
                          for index, defiAction in enumerate(userCall_1.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.SWAP, DeFiActionType.GETTOKEN}]
        action_index_2 = [index 
                          for index, defiAction in enumerate(userCall_2.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.SWAP, DeFiActionType.SPENDTOKEN}]
        if action_index_1 and action_index_2:
            for index_1 in action_index_1:
                defiAction_1 = userCall_1.defiActions[index_1]
                for index_2 in action_index_2:
                    defiAction_2 = userCall_2.defiActions[index_2]
                    if ((defiAction_1.defiPurpose == DeFiActionType.GETTOKEN and defiAction_2.defiPurpose == DeFiActionType.SPENDTOKEN) \
                        or (defiAction_1.defiPurpose == DeFiActionType.GETTOKEN and defiAction_2.defiPurpose == DeFiActionType.SWAP) \
                        or (defiAction_1.defiPurpose == DeFiActionType.SWAP and defiAction_2.defiPurpose == DeFiActionType.SPENDTOKEN) \
                        or (defiAction_1.defiPurpose == DeFiActionType.SWAP and defiAction_2.defiPurpose == DeFiActionType.SWAP)) \
                        and defiAction_1.receiver in self.userAccount \
                        and defiAction_2.initiator in self.userAccount \
                        and defiAction_1.token_out[0] == defiAction_2.token_in[0] \
                        and defiAction_1.pool != defiAction_2.pool:
                        for priceChangeInferenceKey in userCall_0.priceChangeInference.keys():
                            manipulated_pool = priceChangeInferenceKey.manipulated_pool
                            if manipulated_pool == defiAction_1.pool:
                                if userCall_2.relatedDeFiAction:
                                    target_tokens = userCall_2.relatedDeFiAction.token_out
                                else:
                                    target_tokens = defiAction_2.token_out

                                profit_maker = self.userAccount.copy()
                                profit_maker.add(defiAction_2.receiver)

                                transfer_in_manipulation = [userCall_0.transfer_sequence]
                                relatedDeFiAction_Type = None
                                if userCall_0.relatedDeFiAction:
                                    transfer_in_manipulation.append(userCall_0.relatedDeFiAction.transfer_sequence)
                                    relatedDeFiAction_Type = userCall_0.relatedDeFiAction.defiPurpose
                                
                                check_token_price_increase = defiAction_1.token_in
                                for token in check_token_price_increase:
                                    if token in userCall_0.priceChangeInference[priceChangeInferenceKey] and userCall_0.priceChangeInference[priceChangeInferenceKey][token] == Tendency.INCREASE:
                                        self.record_result(
                                            matched_pattern="Manipulate -> Buy / Get in manipulated price -> Sell / Spend in normal price",
                                            defiActions=[defiAction_1, userCall_1.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_1, userCall_1.relatedDeFiAction, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_0.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )
                                
                                check_token_price_decrease = defiAction_1.token_out
                                for token in check_token_price_decrease:
                                    if token in userCall_0.priceChangeInference[priceChangeInferenceKey] and userCall_0.priceChangeInference[priceChangeInferenceKey][token] == Tendency.DECREASE:
                                        self.record_result(
                                            matched_pattern="Manipulate -> Buy / Get in manipulated price -> Sell / Spend in normal price",
                                            defiActions=[defiAction_1, userCall_1.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_1, userCall_1.relatedDeFiAction, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_0.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

        # Deposit -> Manipulate -> Borrow
        action_index_1 = [index 
                          for index, defiAction in enumerate(userCall_0.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.DEPOSIT, DeFiActionType.SPENDTOKEN}]
        action_index_2 = [index 
                          for index, defiAction in enumerate(userCall_2.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.GETTOKEN, DeFiActionType.BORROW}]
        if action_index_1 and action_index_2:
            for index_1 in action_index_1:
                defiAction_1 = userCall_0.defiActions[index_1]
                for index_2 in action_index_2:
                    defiAction_2 = userCall_2.defiActions[index_2]
                    if ((defiAction_1.defiPurpose == DeFiActionType.DEPOSIT and defiAction_2.defiPurpose == DeFiActionType.GETTOKEN and (defiAction_1.receiver in self.userAccount and defiAction_2.initiator in self.userAccount) and defiAction_1.token_in[0] != defiAction_2.token_out[0]) \
                        or (defiAction_1.defiPurpose == DeFiActionType.SPENDTOKEN and defiAction_2.defiPurpose == DeFiActionType.GETTOKEN and (defiAction_1.initiator in self.userAccount and defiAction_2.initiator in self.userAccount) and defiAction_1.token_in[0] != defiAction_2.token_out[0]) \
                        or (defiAction_1.defiPurpose == DeFiActionType.DEPOSIT and defiAction_2.defiPurpose == DeFiActionType.BORROW and (defiAction_1.receiver in self.userAccount and defiAction_2.initiator in self.userAccount))
                        or (defiAction_1.defiPurpose == DeFiActionType.SPENDTOKEN and defiAction_2.defiPurpose == DeFiActionType.BORROW and (defiAction_1.initiator in self.userAccount and defiAction_2.initiator in self.userAccount))):
                        # and defiAction_1.pool == defiAction_2.pool:
                        # and defiAction_1.token_in[0] != defiAction_2.token_out[0]:
                        for priceChangeInferenceKey in userCall_1.priceChangeInference.keys():
                            manipulated_pool = priceChangeInferenceKey.manipulated_pool
                            if manipulated_pool == defiAction_1.pool or manipulated_pool == defiAction_2.pool:

                                if userCall_2.relatedDeFiAction:
                                    target_tokens = userCall_2.relatedDeFiAction.token_out
                                else:
                                    target_tokens = defiAction_2.token_out

                                profit_maker = self.userAccount.copy()
                                profit_maker.add(defiAction_2.receiver)

                                transfer_in_manipulation = [userCall_1.transfer_sequence]
                                relatedDeFiAction_Type = None
                                if userCall_1.relatedDeFiAction:
                                    transfer_in_manipulation.append(userCall_1.relatedDeFiAction.transfer_sequence)
                                    relatedDeFiAction_Type = userCall_1.relatedDeFiAction.defiPurpose

                                check_token_price_increase = defiAction_1.token_in + defiAction_1.token_out
                                for token in check_token_price_increase:
                                    if token in userCall_1.priceChangeInference[priceChangeInferenceKey] and userCall_1.priceChangeInference[priceChangeInferenceKey][token] == Tendency.INCREASE:
                                        self.record_result(
                                            matched_pattern="Collateralise -> Manipulate -> Borrow",
                                            defiActions=[defiAction_1, userCall_0.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[defiAction_1, userCall_0.relatedDeFiAction, 
                                                             priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_1.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

                                check_token_price_decrease = defiAction_2.token_out
                                for token in check_token_price_decrease:
                                    if token in userCall_1.priceChangeInference[priceChangeInferenceKey] and userCall_1.priceChangeInference[priceChangeInferenceKey][token] == Tendency.DECREASE:
                                        self.record_result(
                                            matched_pattern="Collateralise -> Manipulate -> Borrow",
                                            defiActions=[defiAction_1, userCall_0.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[defiAction_1, userCall_0.relatedDeFiAction, 
                                                             priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_1.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

        # Manipulate -> Deposit -> Borrow
        action_index_1 = [index 
                          for index, defiAction in enumerate(userCall_1.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.DEPOSIT, DeFiActionType.SPENDTOKEN}]
        action_index_2 = [index 
                          for index, defiAction in enumerate(userCall_2.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.GETTOKEN, DeFiActionType.BORROW}]
        
        if action_index_1 and action_index_2:
            for index_1 in action_index_1:
                defiAction_1 = userCall_1.defiActions[index_1]
                for index_2 in action_index_2:
                    defiAction_2 = userCall_2.defiActions[index_2]
                    if ((defiAction_1.defiPurpose == DeFiActionType.DEPOSIT and defiAction_2.defiPurpose == DeFiActionType.GETTOKEN and (defiAction_1.receiver in self.userAccount and defiAction_2.initiator in self.userAccount) and defiAction_1.token_in[0] != defiAction_2.token_out[0]) \
                        or (defiAction_1.defiPurpose == DeFiActionType.SPENDTOKEN and defiAction_2.defiPurpose == DeFiActionType.GETTOKEN and (defiAction_1.initiator in self.userAccount and defiAction_2.initiator in self.userAccount) and defiAction_1.token_in[0] != defiAction_2.token_out[0]) \
                        or (defiAction_1.defiPurpose == DeFiActionType.DEPOSIT and defiAction_2.defiPurpose == DeFiActionType.BORROW and (defiAction_1.receiver in self.userAccount and defiAction_2.initiator in self.userAccount))
                        or (defiAction_1.defiPurpose == DeFiActionType.SPENDTOKEN and defiAction_2.defiPurpose == DeFiActionType.BORROW and (defiAction_1.initiator in self.userAccount and defiAction_2.initiator in self.userAccount))):
                        # and defiAction_1.pool == defiAction_2.pool:
                        # and defiAction_1.token_in[0] != defiAction_2.token_out[0]:
                        for priceChangeInferenceKey in userCall_0.priceChangeInference.keys():
                            manipulated_pool = priceChangeInferenceKey.manipulated_pool
                            if manipulated_pool == defiAction_1.pool or manipulated_pool == defiAction_2.pool:

                                if userCall_2.relatedDeFiAction:
                                    target_tokens = userCall_2.relatedDeFiAction.token_out
                                else:
                                    target_tokens = defiAction_2.token_out

                                profit_maker = self.userAccount.copy()
                                profit_maker.add(defiAction_2.receiver)

                                transfer_in_manipulation = [userCall_0.transfer_sequence]
                                relatedDeFiAction_Type = None
                                if userCall_0.relatedDeFiAction:
                                    transfer_in_manipulation.append(userCall_0.relatedDeFiAction.transfer_sequence)
                                    relatedDeFiAction_Type = userCall_0.relatedDeFiAction.defiPurpose

                                check_token_price_increase = defiAction_1.token_in + defiAction_1.token_out
                                for token in check_token_price_increase:
                                    if token in userCall_0.priceChangeInference[priceChangeInferenceKey] and userCall_0.priceChangeInference[priceChangeInferenceKey][token] == Tendency.INCREASE:
                                        self.record_result(
                                            matched_pattern="Manipulate -> Collateralise -> Borrow",
                                            defiActions=[defiAction_1, userCall_1.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                                defiAction_1, userCall_1.relatedDeFiAction, 
                                                                defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_0.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

                                check_token_price_decrease = defiAction_2.token_out
                                for token in check_token_price_decrease:
                                    if token in userCall_0.priceChangeInference[priceChangeInferenceKey] and userCall_0.priceChangeInference[priceChangeInferenceKey][token] == Tendency.DECREASE:
                                        self.record_result(
                                            matched_pattern="Manipulate -> Collateralise -> Borrow",
                                            defiActions=[defiAction_1, userCall_1.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                                defiAction_1, userCall_1.relatedDeFiAction, 
                                                                defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_0.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )
        
        # Deposit -> Manipulate -> Withdraw
        action_index_1 = [index 
                          for index, defiAction in enumerate(userCall_0.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.DEPOSIT}]
        action_index_2 = [index 
                          for index, defiAction in enumerate(userCall_2.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.SWAP, DeFiActionType.WITHDRAW}]
        if action_index_1 and action_index_2:
            for index_1 in action_index_1:
                defiAction_1 = userCall_0.defiActions[index_1]
                for index_2 in action_index_2:
                    defiAction_2 = userCall_2.defiActions[index_2]
                    if defiAction_1.receiver in self.userAccount and defiAction_2.initiator in self.userAccount\
                        and defiAction_1.token_out[0] == defiAction_2.token_in[0]:
                        for priceChangeInferenceKey in userCall_1.priceChangeInference.keys():
                            manipulated_pool = priceChangeInferenceKey.manipulated_pool
                            if manipulated_pool == defiAction_1.pool or manipulated_pool == defiAction_2.pool:
                                
                                if userCall_2.relatedDeFiAction:
                                    target_tokens = userCall_2.relatedDeFiAction.token_out
                                else:
                                    target_tokens = defiAction_2.token_out

                                profit_maker = self.userAccount.copy()
                                profit_maker.add(defiAction_2.receiver)

                                transfer_in_manipulation = [userCall_1.transfer_sequence]
                                relatedDeFiAction_Type = None
                                if userCall_1.relatedDeFiAction:
                                    transfer_in_manipulation.append(userCall_1.relatedDeFiAction.transfer_sequence)
                                    relatedDeFiAction_Type = userCall_1.relatedDeFiAction.defiPurpose
                                
                                check_token_price_increase = defiAction_1.token_in + defiAction_1.token_out
                                for token in check_token_price_increase:
                                    if token in userCall_1.priceChangeInference[priceChangeInferenceKey] and userCall_1.priceChangeInference[priceChangeInferenceKey][token] == Tendency.INCREASE:
                                        self.record_result(
                                            matched_pattern="Deposit -> Manipulate -> Withdraw",
                                            defiActions=[defiAction_1, userCall_0.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[defiAction_1, userCall_0.relatedDeFiAction, 
                                                             priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_1.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )
                                
                                check_token_price_decrease = defiAction_2.token_out
                                for token in check_token_price_decrease:
                                    if token in userCall_1.priceChangeInference[priceChangeInferenceKey] and userCall_1.priceChangeInference[priceChangeInferenceKey][token] == Tendency.DECREASE:
                                        self.record_result(
                                            matched_pattern="Deposit -> Manipulate -> Withdraw",
                                            defiActions=[defiAction_1, userCall_0.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[defiAction_1, userCall_0.relatedDeFiAction, 
                                                             priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_1.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )
        # Manipulate -> Deposit -> Withdraw
        action_index_1 = [index 
                          for index, defiAction in enumerate(userCall_1.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.DEPOSIT}]
        action_index_2 = [index 
                          for index, defiAction in enumerate(userCall_2.defiActions) 
                          if defiAction.defiPurpose in {DeFiActionType.SWAP, DeFiActionType.WITHDRAW}]
        if action_index_1 and action_index_2:
            for index_1 in action_index_1:
                defiAction_1 = userCall_1.defiActions[index_1]
                for index_2 in action_index_2:
                    defiAction_2 = userCall_2.defiActions[index_2]
                    if defiAction_1.receiver in self.userAccount and defiAction_2.initiator in self.userAccount\
                        and defiAction_1.token_out[0] == defiAction_2.token_in[0]:
                        for priceChangeInferenceKey in userCall_0.priceChangeInference.keys():
                            manipulated_pool = priceChangeInferenceKey.manipulated_pool
                            if manipulated_pool == defiAction_1.pool or manipulated_pool == defiAction_2.pool:

                                if userCall_2.relatedDeFiAction:
                                    target_tokens = userCall_2.relatedDeFiAction.token_out
                                else:
                                    target_tokens = defiAction_2.token_out

                                profit_maker = self.userAccount.copy()
                                profit_maker.add(defiAction_2.receiver)

                                transfer_in_manipulation = [userCall_0.transfer_sequence]
                                relatedDeFiAction_Type = None
                                if userCall_0.relatedDeFiAction:
                                    transfer_in_manipulation.append(userCall_0.relatedDeFiAction.transfer_sequence)
                                    relatedDeFiAction_Type = userCall_0.relatedDeFiAction.defiPurpose
                                
                                check_token_price_increase = defiAction_1.token_in + defiAction_1.token_out
                                for token in check_token_price_increase:
                                    if token in userCall_0.priceChangeInference[priceChangeInferenceKey] and userCall_0.priceChangeInference[priceChangeInferenceKey][token] == Tendency.INCREASE:
                                        self.record_result(
                                            matched_pattern="Manipulate -> Deposit -> Borrow",
                                            defiActions=[defiAction_1, userCall_1.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                                defiAction_1, userCall_1.relatedDeFiAction, 
                                                                defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_0.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

                                check_token_price_decrease = defiAction_2.token_out
                                for token in check_token_price_decrease:
                                    if token in userCall_0.priceChangeInference[priceChangeInferenceKey] and userCall_0.priceChangeInference[priceChangeInferenceKey][token] == Tendency.DECREASE:
                                        self.record_result(
                                            matched_pattern="Manipulate -> Deposit -> Borrow",
                                            defiActions=[defiAction_1, userCall_1.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                                defiAction_1, userCall_1.relatedDeFiAction, 
                                                                defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_0.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

        # Stake -> Manipulate -> Claim
        action_index_1 = [index 
                          for index, defiAction in enumerate(userCall_0.defiActions) 
                          if defiAction.defiPurpose == DeFiActionType.SPENDTOKEN]
        action_index_2 = [index 
                          for index, defiAction in enumerate(userCall_2.defiActions) 
                          if defiAction.defiPurpose == DeFiActionType.GETTOKEN]
        if action_index_1 and action_index_2:
            for index_1 in action_index_1:
                defiAction_1 = userCall_0.defiActions[index_1]
                for index_2 in action_index_2:
                    defiAction_2 = userCall_2.defiActions[index_2]
                    if defiAction_1.defiPurpose == DeFiActionType.SPENDTOKEN and defiAction_2.defiPurpose == DeFiActionType.GETTOKEN \
                        and defiAction_1.initiator in self.userAccount and defiAction_2.initiator in self.userAccount \
                        and defiAction_1.token_in[0] == defiAction_2.token_out[0] \
                        and defiAction_1.pool == defiAction_2.pool:
                        for priceChangeInferenceKey in userCall_1.priceChangeInference.keys():
                            manipulated_pool = priceChangeInferenceKey.manipulated_pool
                            if manipulated_pool == defiAction_1.pool:

                                if userCall_2.relatedDeFiAction:
                                    target_tokens = userCall_2.relatedDeFiAction.token_out
                                else:
                                    target_tokens = defiAction_2.token_out

                                profit_maker = self.userAccount.copy()
                                profit_maker.add(defiAction_2.receiver)

                                transfer_in_manipulation = [userCall_1.transfer_sequence]
                                relatedDeFiAction_Type = None
                                if userCall_1.relatedDeFiAction:
                                    transfer_in_manipulation.append(userCall_1.relatedDeFiAction.transfer_sequence)
                                    relatedDeFiAction_Type = userCall_1.relatedDeFiAction.defiPurpose

                                check_token_price_increase = defiAction_1.token_in
                                for token in check_token_price_increase:
                                    if token in userCall_1.priceChangeInference[priceChangeInferenceKey] and userCall_1.priceChangeInference[priceChangeInferenceKey][token] == Tendency.INCREASE:
                                        self.record_result(
                                            matched_pattern="Deposit -> Manipulate -> Withdraw / Get reward",
                                            defiActions=[defiAction_1, userCall_0.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[defiAction_1, userCall_0.relatedDeFiAction, 
                                                             priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_1.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

                                check_token_price_decrease = defiAction_2.token_out
                                for token in check_token_price_decrease:
                                    if token in userCall_1.priceChangeInference[priceChangeInferenceKey] and userCall_1.priceChangeInference[priceChangeInferenceKey][token] == Tendency.DECREASE:
                                        self.record_result(
                                            matched_pattern="Deposit -> Manipulate -> Withdraw / Get reward",
                                            defiActions=[defiAction_1, userCall_0.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[defiAction_1, userCall_0.relatedDeFiAction, 
                                                             priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_1.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )
        
        # Manipulate -> Stake -> Claim
        action_index_1 = [index 
                          for index, defiAction in enumerate(userCall_1.defiActions) 
                          if defiAction.defiPurpose == DeFiActionType.SPENDTOKEN]
        action_index_2 = [index 
                          for index, defiAction in enumerate(userCall_2.defiActions) 
                          if defiAction.defiPurpose == DeFiActionType.GETTOKEN]
        
        if action_index_1 and action_index_2:
            for index_1 in action_index_1:
                defiAction_1 = userCall_1.defiActions[index_1]
                for index_2 in action_index_2:
                    defiAction_2 = userCall_2.defiActions[index_2]
                    if defiAction_1.defiPurpose == DeFiActionType.SPENDTOKEN and defiAction_2.defiPurpose == DeFiActionType.GETTOKEN \
                        and defiAction_1.initiator in self.userAccount and defiAction_2.initiator in self.userAccount \
                        and defiAction_1.token_in[0] == defiAction_2.token_out[0] \
                        and defiAction_1.pool == defiAction_2.pool:
                        for priceChangeInferenceKey in userCall_0.priceChangeInference.keys():
                            manipulated_pool = priceChangeInferenceKey.manipulated_pool
                            if manipulated_pool == defiAction_1.pool:

                                if userCall_2.relatedDeFiAction:
                                    target_tokens = userCall_2.relatedDeFiAction.token_out
                                else:
                                    target_tokens = defiAction_2.token_out

                                profit_maker = self.userAccount.copy()
                                profit_maker.add(defiAction_2.receiver)

                                transfer_in_manipulation = [userCall_0.transfer_sequence]
                                relatedDeFiAction_Type = None
                                if userCall_0.relatedDeFiAction:
                                    transfer_in_manipulation.append(userCall_0.relatedDeFiAction.transfer_sequence)
                                    relatedDeFiAction_Type = userCall_0.relatedDeFiAction.defiPurpose

                                check_token_price_increase = defiAction_1.token_in
                                for token in check_token_price_increase:
                                    if token in userCall_0.priceChangeInference[priceChangeInferenceKey] and userCall_0.priceChangeInference[priceChangeInferenceKey][token] == Tendency.INCREASE:
                                        self.record_result(
                                            matched_pattern="Manipulate -> Deposit -> Withdraw",
                                            defiActions=[defiAction_1, userCall_1.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_1, userCall_1.relatedDeFiAction, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_0.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

                                check_token_price_decrease = defiAction_2.token_out
                                for token in check_token_price_decrease:
                                    if token in userCall_0.priceChangeInference[priceChangeInferenceKey] and userCall_0.priceChangeInference[priceChangeInferenceKey][token] == Tendency.DECREASE:
                                        self.record_result(
                                            matched_pattern="Manipulate -> Deposit -> Withdraw",
                                            defiActions=[defiAction_1, userCall_1.relatedDeFiAction, defiAction_2, userCall_2.relatedDeFiAction],
                                            attack_sequence=[priceChangeInferenceKey.defiActionType, relatedDeFiAction_Type, 
                                                             defiAction_1, userCall_1.relatedDeFiAction, 
                                                             defiAction_2, userCall_2.relatedDeFiAction],
                                            manipulated_pool=manipulated_pool,
                                            price_change_tendency=[userCall_0.priceChangeInference[priceChangeInferenceKey],{}],
                                            transfer_in_manipulation=transfer_in_manipulation,
                                            target_tokens=target_tokens,
                                            profit_maker=profit_maker,
                                            flashLoans=[userCall.flashLoan for userCall in self.userCalls],
                                            detect_result=detect_result
                                        )

        detect_result.append(DetectResult(
            matched_pattern=None,
            isAttack=False,
            profit_token=None,
            profit=None,
            attack_sequence=None,
            manipulated_pool=None,
            price_change_tendency=None,
            manipulation_transfer_sequence=None
        ))
        return detect_result

    def record_result(self,
                      matched_pattern: str,
                      defiActions: List[DeFiAction],
                      attack_sequence: List[Optional[DeFiAction] | DeFiActionType | List[DeFiActionType]],
                      manipulated_pool: str,
                      price_change_tendency: List[Dict[str, Tendency]],
                      transfer_in_manipulation: List[List[Transfer]],
                      target_tokens: List[str],
                      profit_maker: str,
                      flashLoans: List[FlashLoan],
                      detect_result: List[DetectResult]) -> None:
        detect_result.append(DetectResult(
                    matched_pattern=matched_pattern,
                    isAttack=True,
                    profit_token=None,
                    profit=None,
                    attack_sequence=attack_sequence,
                    manipulated_pool=manipulated_pool,
                    price_change_tendency=price_change_tendency,
                    manipulation_transfer_sequence=transfer_in_manipulation
                ))