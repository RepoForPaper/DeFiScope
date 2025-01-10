## How to use
### Environment

Python 3.10.12

### Install dependencies

```cmd
$ pip install -r requirements.txt
```

### Set OpenAI API key

Follow the instructions in [OpenAI](https://platform.openai.com/docs/quickstart/step-2-set-up-your-api-key) for instructions on setting OpenAI API key

### Start detection

Run detector with the following incantation:

```cmd
$ python main.py -tx <transaction hash> -bp <chain ID>
```

- Where `<transaction hash>` is the transaction hash of the test transaction
- Where `<chain ID>` is the blockchain platform where test transaction is on. The blockchain platforms supported by the detector include Ethereum (`chain ID` = ethereum), BSC (`chain ID` = bsc).

### Detection result

Detection result is stored in `detection_result.jsonl`
