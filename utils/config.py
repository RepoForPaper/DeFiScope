SUPPORTED_NETWORK = {
    # platform name: {prefix in the crytic_compile, quick node api, explorer api prefix, command in flatting (check in cryticparser), explorer api key, address of wrapped stable coin}
    "ethereum": {
        "name":"mainet", 
        "quick_node":"https://docs-demo.quiknode.pro/", 
        "api_prefix":".etherscan.io", 
        "key_command": "--etherscan-apikey", 
        "api_key": "QDS5WNKKGD6UM84H6W836VM8IFF13NYNRA",
        "stable_coin": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", # WETH
        "symbol": "WETH",
        },
    "bsc": {
        "name":"bsc", 
        "quick_node":"https://docs-demo.bsc.quiknode.pro/", 
        "api_prefix":".bscscan.com", 
        "key_command": "--bscan-apikey", 
        "api_key": "MINR7693QG357W7VWKCTURW5KX1KQ7G9HN",
        "stable_coin": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", # WBNB
        "symbol": "WBNB",
        },
}