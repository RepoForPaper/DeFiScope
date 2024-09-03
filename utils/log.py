from utils.detector import DetectResult
from utils.actionType import DeFiActionType
from utils.defiAction import DeFiAction

def attack_log(detect_result: DetectResult) -> None:
    print("[*]Attack detected:")
    attack_pattern = []
    action_details = []
    if detect_result.manipulation_transfer_sequence:
        manipulation_transfer_sequence = iter(detect_result.manipulation_transfer_sequence)
    else:
        print("[!]Error in generating attack log")
        return
    if detect_result.price_change_tendency:
        price_change_tendency = iter(detect_result.price_change_tendency)
    else:
        print("[!]Error in generating attack log")
        return
    for attack_action in detect_result.attack_sequence:
        if isinstance(attack_action, DeFiAction):
            attack_pattern.append(attack_action.defiPurpose.value)
            action_details.append(attack_action.log())
        elif isinstance(attack_action, DeFiActionType) or isinstance(attack_action, list):
            if isinstance(attack_action, list):
                attack_action_value = " or ".join(list(set([action.value + "(Manipulation)" for action in attack_action])))
            else:
                attack_action_value = attack_action.value + "(Manipulation)"
            attack_pattern.append(attack_action_value)
            action_details.append("\t[-]Manipulation:\n")
            action_details.append("\t[-]Manipulate price through: {action_purpose}\n".format(action_purpose=attack_action_value))
            action_details.append("\t[-]Manipulated pool: {pool_address}\n".format(pool_address=detect_result.manipulated_pool))
            action_details.append("\t[-]Transfer sequence:\n")
            action_details.append("".join([transfer.log() for transfer in next(manipulation_transfer_sequence)]))
            action_details.append("\t[-]Token price change inference:\n")
            for token_address, tendency in next(price_change_tendency).items():
                action_details.append("\t[-]Token: {token_address}\n".format(token_address=token_address))
                action_details.append("\t[-]Tendency: {tendency}\n".format(tendency=tendency.value))
    print("\t[-]Matched attack pattern: ", detect_result.matched_pattern)
    print("\t[-]Attack flow: ", " -> ".join(attack_pattern))
    # print("\t[-]Target token: ", detect_result.profit_token)
    # print("\t[-]Profit: ", detect_result.profit)
    print("\t[-]Attack details:\n", "".join(action_details))