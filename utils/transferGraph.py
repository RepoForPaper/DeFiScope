from typing import List, Dict, Set
from itertools import combinations

from utils.transfer import Transfer, TransferActionType
from utils.defiAction import DeFiAction, DeFiActionType

class Edge:
    def __init__(self, time_index: int, transfer: Transfer) -> None:
        self.time_index = time_index
        self.transfer = transfer

class TransferGraph:
    def __init__(self, transfer_sequence: List[Transfer], userAccount: Set[str]) -> None:
        self.graph = self.construct_transferGraph(transfer_sequence)
        self.userInGraph = set(self.graph.keys()).intersection(userAccount)

    def construct_transferGraph(self, transfer_sequence: List[Transfer]) -> Dict[str, Dict[str, List[Edge]]]:
        adjacencyList = {}
        for index, transfer in enumerate(transfer_sequence):
            if transfer.sender_address not in adjacencyList:
                adjacencyList[transfer.sender_address] = {"in": [], "out": []}
            if transfer.receiver_address not in adjacencyList:
                adjacencyList[transfer.receiver_address] = {"in": [], "out": []}
            adjacencyList[transfer.sender_address]["out"].append(Edge(time_index=index, transfer=transfer))
            adjacencyList[transfer.receiver_address]["in"].append(Edge(time_index=index, transfer=transfer))
        return adjacencyList
    
    def search_swap_transferSequence(self) -> List[List[Transfer]]:
        graph = self.graph
        userAccount = self.userInGraph
        swap_transferSequence: List[List[Transfer]] = []
        visited: Set[str] = set()
        stack: List[str] = list()
        transfer_sequence: List[Transfer] = []
        def dfs(node: str, time_index: int) -> None:
            visited.add(node)
            stack.append(node)

            for edge in graph.get(node, {}).get("out", []):
                if edge.time_index > time_index and edge.transfer.transfer_type == TransferActionType.TRANSFER:
                    if edge.transfer.receiver_address in userAccount:
                        stack_bak = stack
                        address_cycle = [edge.transfer.receiver_address]
                        transfer_cycle = [edge.transfer]
                        for address in reversed(stack_bak):
                            address_cycle.append(address)
                            if address == edge.transfer.receiver_address or address in userAccount:
                                break
                        for i in range(len(address_cycle) - 2):
                            transfer_cycle.append(transfer_sequence[-(i+1)])
                        swap_transferSequence.append(list(reversed(transfer_cycle)))
                    elif edge.transfer.receiver_address not in visited:
                        transfer_sequence.append(edge.transfer)
                        dfs(edge.transfer.receiver_address, edge.time_index)
                else:
                    continue
            stack.pop()
            if transfer_sequence:
                transfer_sequence.pop()
                    
        for node_address in graph:
            if node_address not in visited and node_address in userAccount:
                dfs(node_address, -1)
        
        return swap_transferSequence
    
    def match_swap_action(self, swap_transferSequence: List[List[Transfer]]) -> List[DeFiAction]:
        #@todo-done handle the swap with more than one pool
        #@note Currently we only consider the swap with one pool, two different tokens, two user account
        userAccount = self.userInGraph
        swapActions = []
        for transfer_sequence in swap_transferSequence:
            if transfer_sequence[0].token_address != transfer_sequence[-1].token_address:
                init_sender = transfer_sequence[0].sender_address
                for i in range(len(transfer_sequence) - 1):
                    if i == len(transfer_sequence) - 2:
                        transfer_in = Transfer(sender_address=init_sender, receiver_address=transfer_sequence[i].receiver_address, token_address=transfer_sequence[i].token_address, amount=transfer_sequence[i].amount)
                        transfer_out = Transfer(sender_address=transfer_sequence[i+1].sender_address, receiver_address=transfer_sequence[i+1].receiver_address, token_address=transfer_sequence[i+1].token_address, amount=transfer_sequence[i+1].amount)
                    else:
                        transfer_in = Transfer(sender_address=init_sender, receiver_address=transfer_sequence[i].receiver_address, token_address=transfer_sequence[i].token_address, amount=transfer_sequence[i].amount)
                        transfer_out = Transfer(sender_address=transfer_sequence[i+1].sender_address, receiver_address=init_sender, token_address=transfer_sequence[i+1].token_address, amount=transfer_sequence[i+1].amount)
                    swapAction = DeFiAction(transfer_sequence=[transfer_in, transfer_out], userAccount=userAccount, purpose=DeFiActionType.SWAP)
                    if swapAction.defiPurpose != DeFiActionType.UNDEFINED:
                        swapActions.append(swapAction)
        return swapActions
    
    def search_addLiquidity_transferSequence(self) -> List[List[Transfer]]:
        graph = self.graph
        userAccount = self.userInGraph
        addLiquidity_transferSequence = []
        for node_address in graph:
            if node_address in userAccount:
                for mint_edge in graph.get(node_address, {}).get("in", []):
                    if mint_edge.transfer.transfer_type == TransferActionType.MINT:
                        for path_1, path_2 in combinations(self.isReachable(src=userAccount, dst=mint_edge.transfer.token_address), 2):
                            if path_1[0].transfer.sender_address == path_2[0].transfer.sender_address \
                                and path_1[-1].transfer.token_address != path_2[-1].transfer.token_address \
                                and path_1[-1].transfer.token_address != mint_edge.transfer.token_address \
                                and path_2[-1].transfer.token_address != mint_edge.transfer.token_address \
                                and max(path_1[-1].time_index, path_2[-1].time_index) < mint_edge.time_index:
                                addLiquidity_transferSequence.append([path_1[0].transfer, path_2[0].transfer, mint_edge.transfer]) # Transfer(out) + Transfer(out) + Mint(in)
        return addLiquidity_transferSequence
    
    def match_addLiquidity_action(self, addLiquidity_transferSequence: List[List[Transfer]]) -> List[DeFiAction]:
        userAccount = self.userInGraph
        addLiquidityActions = []
        for transfer_sequence in addLiquidity_transferSequence:
            addLiquidityAction = DeFiAction(transfer_sequence=transfer_sequence, userAccount=userAccount, purpose=DeFiActionType.ADDLIQUIDITY)
            if addLiquidityAction.defiPurpose != DeFiActionType.UNDEFINED:
                addLiquidityActions.append(addLiquidityAction)
        return addLiquidityActions

    def search_removeLiquidity_transferSequence(self) -> List[List[Transfer]]:
        graph = self.graph
        userAccount = self.userInGraph
        removeLiquidity_transferSequence = []
        for node_address in graph:
            if node_address in userAccount:
                for burn_edge in graph.get(node_address, {}).get("out", []):
                    if burn_edge.transfer.transfer_type == TransferActionType.BURN:
                        for path_1, path_2 in combinations(self.isReachable(src=burn_edge.transfer.token_address, dst=userAccount), 2):
                            if path_1[-1].transfer.receiver_address == path_2[-1].transfer.receiver_address \
                                and path_1[0].transfer.token_address != path_2[0].transfer.token_address \
                                and path_1[0].transfer.token_address != burn_edge.transfer.token_address \
                                and path_2[0].transfer.token_address != burn_edge.transfer.token_address \
                                and min(path_1[-1].time_index, path_2[-1].time_index) > burn_edge.time_index:
                                removeLiquidity_transferSequence.append([burn_edge.transfer, path_1[-1].transfer, path_2[-1].transfer]) # Burn(out) + Transfer(in) + Transfer(in)
        return removeLiquidity_transferSequence
    
    def match_removeLiquidity_action(self, removeLiquidity_transferSequence: List[List[Transfer]]) -> List[DeFiAction]:
        userAccount = self.userInGraph
        removeLiquidityActions = []
        for transfer_sequence in removeLiquidity_transferSequence:
            removeLiquidityAction = DeFiAction(transfer_sequence=transfer_sequence, userAccount=userAccount, purpose=DeFiActionType.REMOVELIQUIDITY)
            if removeLiquidityAction.defiPurpose != DeFiActionType.UNDEFINED:
                removeLiquidityActions.append(removeLiquidityAction)
        return removeLiquidityActions
                    
    def search_getToken_transferSequence(self) -> List[Transfer]:
        # exist in degree but no out degree
        graph = self.graph
        userAccount = self.userInGraph
        getToken_transferSequence: List[Transfer] = []
        in_degree = [bool(graph.get(node_address, {}).get("in", [])) == True for node_address in graph if node_address in userAccount]
        out_degree = [bool(graph.get(node_address, {}).get("out", [])) == False for node_address in graph if node_address in userAccount]
        if all(out_degree) and any(in_degree):
            for node_address in graph:
                if node_address in userAccount:
                    for edge in graph.get(node_address, {}).get("in", []):
                        if edge.transfer.transfer_type == TransferActionType.TRANSFER:
                            getToken_transferSequence.append(edge.transfer)
        return self.prune_transferSequence(transfer_sequence=getToken_transferSequence)

    def match_getToken_action(self, getToken_transferSequence: List[Transfer]) -> List[DeFiAction]:
        userAccount = self.userInGraph
        getTokenActions = []
        for transfer in getToken_transferSequence:
            getTokenAction = DeFiAction(
                transfer_sequence=[
                    Transfer(sender_address=transfer.sender_address,receiver_address=None,token_address=None,amount=0), 
                    transfer], 
                userAccount=userAccount,
                purpose=DeFiActionType.GETTOKEN)
            if getTokenAction.defiPurpose != DeFiActionType.UNDEFINED:
                getTokenActions.append(getTokenAction)
        return getTokenActions
    
    def search_spendToken_transferSequence(self) -> List[Transfer]:
        # exist out degree but no in degree
        graph = self.graph
        userAccount = self.userInGraph
        spendToken_transferSequence = []
        in_degree = [bool(graph.get(node_address, {}).get("in", [])) == False for node_address in graph if node_address in userAccount]
        out_degree = [bool(graph.get(node_address, {}).get("out", [])) == True for node_address in graph if node_address in userAccount]
        if all(in_degree) and any(out_degree):
            for node_address in graph:
                if node_address in userAccount:
                    for edge in graph.get(node_address, {}).get("out", []):
                        if edge.transfer.transfer_type == TransferActionType.TRANSFER:
                            spendToken_transferSequence.append(edge.transfer)
        return self.prune_transferSequence(transfer_sequence=spendToken_transferSequence)
                        
    def match_spendToken_action(self, spendToken_transferSequence: List[Transfer]) -> List[DeFiAction]:
        userAccount = self.userInGraph
        spendTokenActions = []
        for transfer in spendToken_transferSequence:
            spendTokenAction = DeFiAction(
                transfer_sequence=[
                    transfer, 
                    Transfer(sender_address=None,receiver_address=transfer.receiver_address,token_address=None,amount=0)], 
                userAccount=userAccount,
                purpose=DeFiActionType.SPENDTOKEN)
            if spendTokenAction.defiPurpose != DeFiActionType.UNDEFINED:
                spendTokenActions.append(spendTokenAction)
        return spendTokenActions

    def search_deposit_transferSequence(self) -> List[List[Transfer]]:
        graph = self.graph
        userAccount = self.userInGraph
        deposit_transferSequence = []
        for node_address in graph:
            if node_address in userAccount:
                for mint_edge in graph.get(node_address, {}).get("in", []):
                    if mint_edge.transfer.transfer_type == TransferActionType.MINT:
                        for deposit_to in graph:
                            if deposit_to not in userAccount \
                                and deposit_to != "0x0000000000000000000000000000000000000000" \
                                and deposit_to != "0x000000000000000000000000000000000000dEaD":
                                to_path = self.isReachable(src=userAccount, dst=deposit_to)
                                from_path = self.isReachable(src=deposit_to, dst=userAccount)
                                if len(from_path) == 0 and len(to_path) > 0:
                                    for deposit_path in to_path:
                                        if deposit_path[0].transfer.token_address != mint_edge.transfer.token_address:
                                            deposit_transferSequence.append([deposit_path[-1].transfer,mint_edge.transfer])
        return deposit_transferSequence

    def match_deposit_action(self, deposit_transferSequence: List[List[Transfer]]) -> List[DeFiAction]:
        userAccount = self.userInGraph
        depositActions = []
        for transfer_sequence in deposit_transferSequence:
            depositAction = DeFiAction(transfer_sequence=transfer_sequence, userAccount=userAccount, purpose=DeFiActionType.DEPOSIT)
            if depositAction.defiPurpose != DeFiActionType.UNDEFINED:
                depositActions.append(depositAction)
        return depositActions
    
    def search_withdraw_transferSequence(self) -> List[List[Transfer]]:
        graph = self.graph
        userAccount = self.userInGraph
        withdraw_transferSequence = []
        for node_address in graph:
            if node_address in userAccount:
                for burn_edge in graph.get(node_address, {}).get("out", []):
                    if burn_edge.transfer.transfer_type == TransferActionType.BURN:
                        for withdraw_from in graph:
                            if withdraw_from not in userAccount \
                                and withdraw_from != "0x0000000000000000000000000000000000000000" \
                                and withdraw_from != "0x000000000000000000000000000000000000dEaD":
                                to_path = self.isReachable(src=userAccount, dst=withdraw_from)
                                from_path = self.isReachable(src=withdraw_from, dst=userAccount)
                                if len(to_path) == 0 and len(from_path) > 0:
                                    for withdraw_path in from_path:
                                        if withdraw_path[-1].transfer.token_address != burn_edge.transfer.token_address:
                                            withdraw_transferSequence.append([burn_edge.transfer,withdraw_path[0].transfer])
        return withdraw_transferSequence
    
    def match_withdraw_action(self, withdraw_transferSequence: List[List[Transfer]]) -> List[DeFiAction]:
        userAccount = self.userInGraph
        withdrawActions = []
        for transfer_sequence in withdraw_transferSequence:
            withdrawAction = DeFiAction(transfer_sequence=transfer_sequence, userAccount=userAccount, purpose=DeFiActionType.WITHDRAW)
            if withdrawAction.defiPurpose != DeFiActionType.UNDEFINED:
                withdrawActions.append(withdrawAction)
        return withdrawActions
    
    def search_borrow_transferSequence(self) -> List[List[Transfer]]:
        graph = self.graph
        userAccount = self.userInGraph
        borrow_transferSequence = []
        for node_address in graph:
            if node_address in userAccount:
                for mint_edge in graph.get(node_address, {}).get("in", []):
                    if mint_edge.transfer.transfer_type == TransferActionType.MINT:
                        for borrow_from in graph:
                            if borrow_from not in userAccount \
                                and borrow_from != "0x0000000000000000000000000000000000000000" \
                                and borrow_from != "0x000000000000000000000000000000000000dEaD":
                                to_path = self.isReachable(src=userAccount, dst=borrow_from)
                                from_path = self.isReachable(src=borrow_from, dst=userAccount)
                                if len(to_path) == 0 and len(from_path) > 0:
                                    for borrow_path in from_path:
                                        if borrow_path[-1].transfer.token_address != mint_edge.transfer.token_address:
                                            borrow_transferSequence.append([mint_edge.transfer,borrow_path[0].transfer])
        return borrow_transferSequence
    
    def match_borrow_action(self, borrow_transferSequence: List[List[Transfer]]) -> List[DeFiAction]:
        userAccount = self.userInGraph
        borrowActions = []
        for transfer_sequence in borrow_transferSequence:
            borrowAction = DeFiAction(transfer_sequence=transfer_sequence, userAccount=userAccount, purpose=DeFiActionType.BORROW)
            if borrowAction.defiPurpose != DeFiActionType.UNDEFINED:
                borrowActions.append(borrowAction)
        return borrowActions

    def isReachable(self, src: str | Set[str], dst: str | Set[str]) -> List[List[Edge]]:
        visited = set()
        paths = []

        def dfs(curr: str, dst: str, path: List[Edge], visited: Set[str], paths: List[List[Edge]], time_index: int):
            visited.add(curr)
            if curr == dst:
                paths.append(path.copy())
            else:
                for edge in self.graph.get(curr, {}).get("out", []):
                    if edge.transfer.receiver_address not in visited \
                        and edge.transfer.transfer_type == TransferActionType.TRANSFER \
                        and edge.time_index > time_index:
                        path.append(edge)
                        dfs(curr=edge.transfer.receiver_address, 
                            dst=dst, 
                            path=path, 
                            visited=visited, 
                            paths=paths, 
                            time_index=edge.time_index)
                        path.pop()
            visited.remove(curr)
        if isinstance(src, set):
            # Add liquidity
            for userAccount in src:
                dfs(curr=userAccount, dst=dst, path=[], visited=visited, paths=paths, time_index= -1)
        if isinstance(dst, set):
            # Remove liquidity
            for userAccount in dst:
                dfs(curr=src, dst=userAccount, path=[], visited=visited, paths=paths, time_index= -1)
        if isinstance(src, str) and isinstance(dst, str):
            dfs(curr=src, dst=dst, path=[], visited=visited, paths=paths, time_index= -1)
        return paths

    def prune_transferSequence(self, transfer_sequence: List[Transfer]) -> List[Transfer]:
        # prune the transfer sequence
        tmp = {}
        pruned_transferSequence: List[Transfer] = []
        for transfer in transfer_sequence:
            if transfer.sender_address not in tmp:
                tmp[transfer.sender_address] = {
                    transfer.receiver_address: {
                        transfer.token_address: transfer.amount
                    }
                }
            else:
                if transfer.receiver_address not in tmp[transfer.sender_address]:
                    tmp[transfer.sender_address][transfer.receiver_address] = {
                        transfer.token_address: transfer.amount
                    }
                else:
                    if transfer.token_address not in tmp[transfer.sender_address][transfer.receiver_address]:
                        tmp[transfer.sender_address][transfer.receiver_address][transfer.token_address] = transfer.amount
                    else:
                        tmp[transfer.sender_address][transfer.receiver_address][transfer.token_address] += transfer.amount
        for sender_address, receiver_dict in tmp.items():
            for receiver_address, token_dict in receiver_dict.items():
                for token_address, amount in token_dict.items():
                    pruned_transferSequence.append(Transfer(sender_address=sender_address, receiver_address=receiver_address, token_address=token_address, amount=amount))
        return pruned_transferSequence