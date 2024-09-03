from utils.userCall import UserCall
from utils.function import Function

def log_userCall_details(userCall: UserCall) -> None:
    print("=" * 150)
    print("UserCall Purpose: ", [(purpose.value, pool) for (purpose, pool) in zip([defiAction.defiPurpose for defiAction in userCall.defiActions], [defiAction.pool for defiAction in userCall.defiActions])])
    print("Price calculation functions: ", [function.entry_point for _, function in userCall.price_calculation_functions])
    print("Price change inference: ")
    for priceChangeInferenceKey, tendency_dict in userCall.priceChangeInference.items():
        priceChangeInferenceKey.debug_log()
        for token_address, tendency in tendency_dict.items():
            print("Token: ", token_address)
            print("Tendency: ", tendency.value)

def log_defiPurpose_sequence(userCall: UserCall) -> None:
    print("=" * 150)
    print("UserCall Purpose Sequence:")
    print([(purpose.value, pool) for (purpose, pool) in zip([defiAction.defiPurpose for defiAction in userCall.defiActions], [defiAction.pool for defiAction in userCall.defiActions])])

def log_transfer_details(userCall: UserCall) -> None:
    print("=" * 150)
    for transfer in userCall.transfer_sequence:
        transfer.debug_log()

def log_functions(userCall: UserCall) -> None:
    print("=" * 150)
    print("Functions: ")
    print([(contract_address, function_name) for contract_address, function_name, _ in userCall.functions])

def log_price_calculation_functions(userCall: UserCall) -> None:
    print("=" * 150)
    print("Price calculation functions: ")
    output = []
    for _, function in userCall.price_calculation_functions:
        if isinstance(function, Function):
            output.append(function.entry_point)
        else:
            output.append(function)
    print(output)

def log_defiAction(userCall: UserCall) -> None:
    print("=" * 150)
    for defiAction in userCall.defiActions:
        defiAction.debug_log()

def log_flashloan(userCall: UserCall) -> None:
    print("=" * 150)
    if userCall.flashLoan.isFlashloan:
        print("Flashloan details: ")
        print(userCall.flashLoan.flashLoanTokens)
    else:
        print("Not flashloan")

def log_relatedAction(userCall: UserCall) -> None:
    print("=" * 150)
    if userCall.relatedDeFiAction:
        print("Related DeFi Action: ")
        userCall.relatedDeFiAction.debug_log()
    else:
        print("No related DeFi Action")

def log_priceChangeTendency(userCall: UserCall) -> None:
    print("=" * 150)
    print("Price change inference: ")
    for priceChangeInferenceKey, tendency_dict in userCall.priceChangeInference.items():
        priceChangeInferenceKey.debug_log()
        for token_address, tendency in tendency_dict.items():
            print("Token: ", token_address)
            print("Tendency: ", tendency.value)