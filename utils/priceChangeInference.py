import re
import os
from enum import Enum
from typing import List, Tuple, Dict, Optional
from openai import OpenAI
from openai.types.chat import ChatCompletion

from utils.actionType import DeFiActionType

class Tendency(Enum):
    INCREASE = "Increase"
    DECREASE = "Decrease"
    UNCERTAIN = "Uncertain"

class PriceChangeInferenceKey:
    """
    Attributes:
        defiActionType: the type of the DeFi action
        manipulated_pool: the address of the manipulated pool
    """
    def __init__(self, defiActionType: DeFiActionType | List[DeFiActionType], manipulated_pool: str) -> None:
        self.defiActionType = defiActionType
        self.manipulated_pool = manipulated_pool
    
    #@debug
    def debug_log(self) -> None:
        print("*" * 150)
        if isinstance(self.defiActionType, list):
            print("DeFi action type: ", [actionType.value for actionType in self.defiActionType])
        else:
            print("DeFi action type: ", self.defiActionType.value)
        print("Manipulated pool: ", self.manipulated_pool)
    
    def debug_store_data(self) -> Dict:
        if isinstance(self.defiActionType, list):
            defiActionType = [actionType.value for actionType in self.defiActionType]
        else:
            defiActionType = self.defiActionType.value
        return {
            "defiActionType": defiActionType,
            "manipulated_pool": self.manipulated_pool
        }

class PriceChangeInferenceUnit:
    """
    Args:
        pool_address: the address of the pool
        token_address_list: a list of token addresses
        code_snippet: the code snippet that contains the price calculation model
        variables_change: a dictionary of variables change in the price calculation model {contract address: {variable name: value change}}
    
    Attributes:
        price_change_inference: a dictionary of price change tendency of tokens {token address: price change tendency}
    """
    def __init__(self, 
                 pool_address: str, 
                 token_address_list: List[str], 
                 code_snippet: Optional[str], 
                 variables_change: Dict[str, Dict[str, int]],
                 contract_name_mapping: Dict[str, str],
                 token_name_mapping: Dict[str,str]) -> None:
        self.contract_name_mapping = contract_name_mapping
        self.token_name_mapping = token_name_mapping
        self.pool_address = pool_address
        self.token_address_list = token_address_list
        self.code_snippet = code_snippet
        self.variables_change = variables_change
        self.price_change_inference = self.generate_price_change_inference()
    
    def generate_prompt(self) -> Tuple[str, List[str]]:
        """
        Returns:
            str: prompt for the price change inference
            list(str): statements for the price change inference
        """
        statements = self.generate_statements()
        variables_change_prompt = self.generate_variable_change()
        answer_format = self.generate_answer_format(statements)

        answer_template = """
You must follow the following format(delimited with XML tags) to answer the question and replace {score} with your evaluation scores.
<answer>
{answer_format}
</answer>
        """.format(BASE_TOKEN="{BASE_TOKEN}" ,score="{score}", answer_format=("\n").join(answer_format))

        if self.code_snippet:
            instruction_1 = """
Instruction 1:
The following is related price calculation functions. You are required to extract the price calculation model.
        """
            intruction_2 = """
Instruction 2:
You will be provided with some changes of variables in the price calculation model(delimited with XML tags). Only based on the price model you extracted previously and the following change, evaluate the degree of credibility of following statements and give me evaluation scores from 1 to 10: {statements}. There is no need for quantitative calculation. Do not need to consider the effect of the market, supply and demand model
        """.format(statements=(" ").join(statements))
            
            prompt = instruction_1 + self.code_snippet + intruction_2 + variables_change_prompt + answer_template
        
        else:
            #@note given total balance change, action purpose, pool address, construct new prompt for the price change inference 
            instruction = """
{pool_address} is the address of a liquidity pool. The price model of the pool aligns with the Constant Product Market Maker (CPMM). You will be provided with some changes of tokens' balance inside the pool. Only based on the given information, you are required to evaluate the degree of credibility of following statements and give me evaluation scores from 1 to 10: {statements}. There is no need for quantitative calculation. Do not need to consider the effect of the market, supply and demand model
""".format(pool_address=self.pool_address, statements=(" ").join(statements))
            
            prompt = instruction + variables_change_prompt + answer_template
        
        return (prompt, statements)

    def generate_price_change_inference(self) -> Dict[str, Tendency]:
        """
        Returns:
            dict(token address, price change tendency): the price change tendency of the each token
            @todo-done bind the price change tendency with specific contract/pool address
        """
        print("[+]Start price change inference")
        client = OpenAI()

        retry = 0
        retry_limit = 2

        while retry <= retry_limit: #try retry_limit + 1 times
            (scores, statements, completion) = self.get_evaluation_score(client)
        
            if len(scores) != len(statements):
                print("[!]Error: Cannot extract the scores from the completion.\n\tCompletion:\n\t{completion}".format(completion=completion))
                if retry < retry_limit:
                    print("[+]Retry for {retry} time".format(retry=retry + 1))
                else:
                    print("[!]Set the scores to 0")
                    scores = [0] * len(statements)
                retry += 1
            else:
                break
        
        price_change_tendency = self.generate_finally_prediction(scores)

        return price_change_tendency

    def generate_statements(self) -> List[str]:
        #@todo-done bind the token address with the pool address (the price of {token_address} {change} in {pool_address} after change) (the pool address could be obtained from the deFiaction.pool)
        statments = []
        token_list_len = len(self.token_address_list)
        # Use readable contract name if possible
        pool_name = self.pool_address
        if self.pool_address in self.contract_name_mapping:
            if self.contract_name_mapping[self.pool_address] != "Unknown":
                pool_name = self.contract_name_mapping[self.pool_address]
        for index, token_address in enumerate(self.token_address_list, start=0):
            # Use readable token name if possible
            token_name = token_address
            if token_address in self.token_name_mapping:
                if self.token_name_mapping[token_address] != "Unknown":
                    token_name = self.token_name_mapping[token_address]
            # Try to find the relative token
            relative_token = ""
            if token_list_len == 2:
                relative_token_address = self.token_address_list[1 - index]
                relative_token_name = relative_token_address
                if relative_token_address in self.token_name_mapping:
                    if self.token_name_mapping[relative_token_address] != "Unknown":
                        relative_token_name = self.token_name_mapping[relative_token_address]
                relative_token = f" relative to {relative_token_name}"
            statments.append("{index})The price of {token_name}{relative_token} in {pool_name} increases after change".format(
                index=index*2+1, 
                token_name=token_name,
                relative_token=relative_token,
                pool_name=pool_name))
            statments.append("{index})The price of {token_name}{relative_token} in {pool_name} decreases after change".format(
                index=index*2+2, 
                token_name=token_name,
                relative_token=relative_token,
                pool_name = pool_name))
        return statments
    
    def generate_variable_change(self) -> str:
        variable_change = []
        for contract_address, variables in self.variables_change.items():
            if contract_address == "0x0000000000000000000000000000000000000000" or contract_address == "0x000000000000000000000000000000000000dEaD":
                #Burn / Mint
                for variable_name, value_change in variables.items():
                    if variable_name in self.token_name_mapping:
                        if self.token_name_mapping[variable_name] != "Unknown":
                            variable_name = self.token_name_mapping[variable_name]
                    if value_change != 0:
                        if value_change > 0: #Burn: Zero address get token
                            variable_change.append("The total supply of {variable_name} decreases by {value_change}".format(
                                variable_name=variable_name, 
                                value_change=value_change))
                        else: #Mint: Zero address "lose" token
                            variable_change.append("The total supply of {variable_name} increases by {value_change}".format(
                                variable_name=variable_name, 
                                value_change=-value_change))
            else:
                #For not Zero address: Use readable contract name if possible
                contract_name = contract_address
                if contract_address in self.contract_name_mapping:
                    if self.contract_name_mapping[contract_address] != "Unknown":
                        contract_name = self.contract_name_mapping[contract_address]
                for variable_name, value_change in variables.items():
                    # Use readable token name if variable is a token address
                    if variable_name in self.token_name_mapping:
                        if self.token_name_mapping[variable_name] != "Unknown":
                            variable_name = self.token_name_mapping[variable_name]
                    if value_change != 0:
                        if value_change > 0:
                            variable_change.append("The balance of {variable_name} in contract {contract_name} increases by {value_change}".format(
                                variable_name=variable_name, 
                                contract_name = contract_name,
                                value_change=value_change))
                        else:
                            variable_change.append("The balance of {variable_name} in contract {contract_name} decreases by {value_change}".format(
                                variable_name=variable_name, 
                                contract_name = contract_name,
                                value_change=-value_change))
                    else:
                        # variable_change.append("The balance of {variable_name} in contract {contract_name} remains unchanged".format(
                        #     variable_name=variable_name, 
                        #     contract_name = contract_name))
                        pass
        variable_change = ["<change>"] + variable_change + ["</change>"]
        return ("\n").join(variable_change)
    
    def get_evaluation_score(self, client: OpenAI) -> Tuple[List[int], List[str], ChatCompletion]:
        temperature = 0
        top_p = 1
        model = "ft:gpt-3.5-turbo-1106:metatrust-labs::8zFctmxs" # Fine-tuned model
        # model = "gpt-3.5-turbo" #@test Original model

        (prompt, statements) = self.generate_prompt()
        # #@debug-start
        # print(prompt)
        # exit()
        # #@debug-end
        try:
            completion = client.chat.completions.create(
                model = model,
                messages=[
                {"role": "system", "content": "You are a price oracle of DeFi protocols, your job is to evaluate the price change of assets based on the given information."},
                {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                top_p=top_p,
            )
            
            scores = []
            #@debug-start
            # chat_id = completion.id[-6:]
            # txhash = os.environ.get('TXHASH')
            # file_name = txhash[:6]
            # store_prompt_path = os.path.join(f"/Volumes/Elements/Paper/Baseline_LLM_log/{file_name}", f'prompt_{chat_id}.txt')
            # store_res_path = os.path.join(f"/Volumes/Elements/Paper/Baseline_LLM_log/{file_name}", f'res_{chat_id}.txt')
            # with open(store_prompt_path, "w") as f:
            #     f.write(prompt)
            #@debug-end
            for choice in completion.choices:
                answer = choice.message.content
                #@debug-start
                # with open(store_res_path, "a") as f:
                #     f.write(answer)
                # print("[*]Answer: \n", answer)
                #@debug-end
                scores = self.extract_scores(answer)
            
            return (scores, statements, completion)
        
        except Exception as e:
            print("[!]Error: {error}".format(error=e))
            return ([0] * len(statements), statements, None)
        
    def extract_scores(self, completion: str) -> List[int]:
        """
        Args:
            completion: the completion string
        Returns:
            list(int): a list of scores of the statements
        """
        pattern = r"\d+\).*:(\s*\d+)" # match i) xxxxx : {score}
        scores = re.findall(pattern, completion)
        scores = [int(s) for s in scores]
        return scores

    def generate_answer_format(self, statements: List[str]) -> List[str]:
        """
        Args:
            statements: the statements for the price change inference
        Returns:
            list(str): the answer format
        """
        answer_format = []
        for statement in statements:
            tmp = "{index}) Evaluation score of {statement}: {score}".format(
                index=statement.split(")")[0],
                statement=statement.split(")")[1], 
                score="{score}"
                )
            answer_format.append(tmp)
        return answer_format

    def generate_finally_prediction(self, scores: List[int]) -> Dict[str, Tendency]:
        """
        Args:
            scores: the scores of the statements
        Returns:
            dict(str, str): the price change tendency of the each token
        """
        price_change_tendency = dict()
        for index, i in enumerate(range(0, len(scores) - 1, 2)):
            increase_score = scores[i]
            decrease_score = scores[i+1]
            if increase_score > decrease_score:
                price_change_tendency[self.token_address_list[index]] = Tendency.INCREASE
            elif increase_score < decrease_score:
                price_change_tendency[self.token_address_list[index]] = Tendency.DECREASE
            else:
                price_change_tendency[self.token_address_list[index]] = Tendency.UNCERTAIN
        return price_change_tendency
