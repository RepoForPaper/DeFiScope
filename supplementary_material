# Supplementary Material

## A. Full Version of Fine-tuning Prompt Template

Following figure shows the full version of prompt template used in fine-tuning, mentioned in §IV, in the main part of the paper.

Above the dashed line is the first instruction, which requires the LLM to extract the price calculation model from the provided code. `{code}` is the placeholder for the code snippet of price calculation functions. Below the dashed line, we guide the LLM to evaluate the credibility of four statements based on the price model extracted from step 1 and the tokens’ balance change. 

![fine-tuning_prompt_template](https://github.com/user-attachments/assets/0cef326d-67f9-4b01-894b-954d3d9f04d3)

## B. Example Prompt and Response of the Motivating Example

The figure below demonstrates a simplified version of the Type-I prompt used and the response produced by our fine-tuned LLM for inferring price changes of the motivating example in §II-C, in the main part of the paper.

From the motivating example’s response shown in the right-hand section, the LLM initially extracts the code of price calculation-related functions, followed by an high-level summary. In this example, it accurately identifies the underlying price model (see eq. (1) in the main part of the paper) — the price of *sUSDe* is determined by the median of multiple prices.

![UwULend_prompt_response](https://github.com/user-attachments/assets/985057f8-0a8d-4582-96b3-8953a56e4964)

## C. Detailed Type-II Prompt Template

The following figure illustrates the Type-II prompt template mentioned in §IV, in the main part of the paper.

It is used in *Customized Inference Process*, for inferring the trend of price changes in closed source two-token liquidity pools. The primary distinction between the Type-I prompt and the Type-II prompt lies in replacing the first instruction with a description of the liquidity pool, informing the LLM that the pool’s price model aligns with CPMM.

![Type-II_prompt](https://github.com/user-attachments/assets/5d8bb668-a1c4-4aa9-b8c9-8a75baf89da1)

## D. A Case Study of Type-II Prompt

The figure below shows a use case of the Type-II prompt. 

The contract (0x2120...3379) is a closed source DEX contract that allows users to trade SVT and USDT. While recovering the DeFi operations, this contract was identified as a two-token liquidity pool. So, we applied the Type-II prompt to inferring the token price trend in its transactions. 

As shown by the LLM response in figure, the primary difference from the response to a Type-I prompt lies in the absence of the analysis on the price model; instead, the scoring is directly yielded. The is because the prompt itself assumes that the CPMM is employed in this contract. Regarding the CPMM, the relationship between token price and token balance is quite standardized, i.e., the direction of balance change is opposite to that of price change.

![prompt_response_of_t2_prompt_case_study](https://github.com/user-attachments/assets/a0f11d5e-f5ad-4567-beb8-2d442aa0df3c)

## E. Full List of Top-10 High-value DeFi Application Across 3 Categories

The design of DeFi operations and the category of transfer actions in §V, in the main part of the paper, is based on an in-depth study of the high-value DeFi applications listed in the table below as of August 2024.

|   DEX App   |   TVL    |  Lending App  |   TVL    | Yield farming App  |   TVL    |
| :---------: | :------: | :-----------: | :------: | :----------------: | :------: |
|   Uniswap   |  \$4.8B  |   Compound    |  \$2.0B  |       Pendle       |  \$2.8B  |
|    Curve    |  \$1.9B  |     AAVE      | \$12.3B  |   Convex Finance   |  \$1.1B  |
|  Balancer   | \$777.2M |    Morpho     |  \$1.5B  |        Aura        | \$361.9M |
|    Sushi    | \$250.2M |   Fraxlend    | \$134.4M |       Magpie       | \$192.5M |
| PancakeSwap |  \$1.7B  |     Venus     |  \$1.5B  |      StakeDAO      | \$78.8M  |
|    1inch    | \$4.58M  |    Strike     |  \$9.7M  | Equilibria Finance | \$80.0M  |
|  ParaSwap   | \$6.34M  |    Planet     |  \$1.2M  |    Kine Finance    |  \$8.0M  |
|  ShibaSwap  | \$18.19M | Kinza Finance | \$42.8M  |  Dot Dot Finance   |  \$2.1M  |
|   BiSwap    | \$27.1M  |    Radiant    |  \$7.8M  |      Solo Top      |  \$1.8M  |
|    MDEX     | \$16.0M  |     Ambit     |   \$6M   |  Jetfuel Finance   |  \$1.5M  |

## F. Detailed Discussion of Attack Types and Patterns

In this section, we will illustrate the attack types and patterns mentioned in §VI, in the main part of the paper.

**Buy** **\&** **Sell.** In this type of attack strategy, the attacker primarily profits by first buying $Token_y$ with $Token_x$ through a swap in $Pool_{buy}$ and then selling $Token_y$ for $Token_z$ through a swap in $Pool_{sell}$. $Token_x$ and $Token_z$ can be the same or different tokens. In the attack against ElephantMoney, the attacker first conducted a swap in $Pool_{buy}$ to exchange WBNB for ELEPHANT and then invoked the `mint` function, which triggered a swap in $Pool_{sell}$ to exchange ELEPHANT for WBNB, resulting in a price increase of ELEPHANT in $Pool_{sell}$. Ultimately, the attacker utilized a reverse swap in $Pool_{sell}$ to obtain WBNB by selling ELEPHANT at the manipulated price. We design Pattern I based on this attack and subsequently generalize it to Pattern II. The major difference between these two patterns is that the token price is manipulated before the first swap in Pattern II, allowing the price of tokens in either $Pool_{buy}$ or $Pool_{sell}$ to be manipulated.

**Deposit** **\&** **Borrow.** In this type, the attacker inflates the price of the deposited tokens or deflates the price of the borrowed assets as calculated by $Contract_{borrow}$, bypassing the protective mechanism of over-collateralization, thereby borrowing more assets than the actual value of the collateral. In the Cream Finance incident, the attacker first deposited yUSD as collateral and obtained an equivalent amount of crYUSD as proof of deposit, then inflated the price of yUSD calculated by $Contract_{borrow}$ by transferring a large quantity of yCrv to a specific contract account. Finally, using yUSD as collateral, the attacker borrowed a large amount of assets, which far exceeded the actual value of the deposited yUSD, from $Contract_{borrow}$. We design Pattern III based on this attack and then generalize it to Pattern IV. Pattern IV differs from Pattern III in that the attacker can preemptively increase the price of tokens designated for deposit or decrease the price of assets intended for borrowing as calculated by $Contract_{borrow}$ before the deposit operation. In particular, the motivating example in §II, in the main part of the paper, conforms to Pattern IV.

**Stake** **\&** **Claim.** This attack type primarily targets yield-farming protocols that offer staking services. Typically, an attacker first stakes $Token_x$ into the application in one transaction. The share ratio of the user is calculated based on the value and quantity of the staked asset in real-time and is stored in the state variables. Then, the attacker decreases the calculated price of $Token_y$ in $Contract_{claim}$ and subsequently claims $Token_y$ from the contract. $Token_x$ and $Token_y$ can be the same or different tokens. We derive Pattern V based on the analysis of the attack against ATK. Specifically, in the first transaction, the attacker initially staked ATK into $Contract_{stake}$. Since the staking service required that the ATK be held for 24 hours by the contract account before claiming, the attacker waited for a period and executed the second transaction, exploiting a flash loan to deflate the price of ATK in $Contract_{claim}$, subsequently claiming back an amount of ATK significantly higher than the appropriate quantity. Considering that the attacker can inflate the price of tokens intended for staking beforehand to get an incorrectly calculated share ratio, we further derive Pattern VI from Pattern V.

**Deposit** **\&** **Withdraw.** In this attack type, the attacker exploits vulnerabilities in the token pricing mechanism within the deposit or withdrawal contract to conduct price manipulation attacks. We design and generalize Pattern VII based on the Harvest attack. In this hack, the attacker first deposited USDC ($Token_x$) in $Contract_{deposit}$ and received fUSDC ($Token_y$) as proof. Then, by exchanging USDC for USDT, the price of USDC calculated by $Contract_{withdrawal}$ decreased, and the attacker withdrew an excessive amount of USDC ($Token_z$) from $Contract_{withdrawal}$ by burning fUSDC. In this case, $Token_x$ and $Token_z$ are the same; however, some protocols, such as [LUSD](https://bscscan.com/address/0xdec12a1dcbc1f741ccd02dfd862ab226f6383003), allow different tokens for deposit and withdrawal. Besides deflating the price of tokens to be withdrawn, the attacker can also inflate the price of tokens used for calculating the withdrawal amount, i.e., $Token_y$. If the attacker manipulates the token price before depositing, the price of tokens involved in the deposit can also be affected. Based on this reason, we generalize Pattern VII to create Pattern VIII.

## G. Details of False Positives

The following table presents the details of six false positives discovered in our experiments described in §VII-C, in the main part of the paper. The reason for these false positives is that their transactions involve two contract accounts that were created three months ago by the transaction initiator. Any fund transfers among these accounts and the initiator should be considered benign operations rather than price manipulation operations. Yet, these accounts were incorrectly marked as closed-source DEXes in the detection, leading to false inferences. Such false positives could be mitigated by conducting a historical analysis of account ownership relationships and clustering user accounts that are controlled by the same owners.

| Transaction hash | Chain |  Block   |   Type    | Root Cause  |
| :--------------: | :---: | :------: | :-------: | :---------: |
|    0x130c6370    |  BSC  | 38218540 |  Benign   |      -      |
|    0x4b59af93    |  BSC  | 38218538 |  Benign   |      -      |
|    0xe158a2b9    |  BSC  | 38218537 |  Benign   |      -      |
|    0x59942848    |  BSC  | 38218536 |  Benign   |      -      |
|    0x2e9ceb16    |  BSC  | 38218539 |  Benign   |      -      |
|    0x640ce34c    |  BSC  | 11403670 | Malicious | Logic issue |

