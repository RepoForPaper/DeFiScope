## Dataset
Under folder dataset/

D1.csv, D2.csv, D3.csv refer to _D1_, _D2_, _D3_ in §VII, respectively.

training_set.csv, eval_set.csv, test_set.csv are the datasets used in fine-tuning OpenAI's models and Phi-3-medium-128k-instruct, containing 800, 100, 100 samples respectively.

## How to use
### Fine-tuning
#### Environment

Python 3.12.9

#### Install dependencies

```cmd
$ pip install -r fine-tuning/requirements.txt
```

#### Start Fine-tuning

Run:

```
deepspeed --num_gpus=<number of gpus> fine-tuning/fine-tuning.py --base_model_name <base model name> --model_name_or_path <model name or path> --tokenizer_name_or_path <tokenizer name or path> --version <checkpoint version> --num_epochs <number of epochs> --lr <learning rate> --save_per_x_epochs <save checkpoint period>
```

Where
- `<number of gpus>` is the number of GPUs you want to used in fine-tuning.
- `<base model name>`, `<checkpoint version>` together form the path where the checkpoint is saved: checkpoints/{base_model_name}/{version}.
- `<model name or path>` can be either a local path or a huggingface model name, e.g. microsoft/Phi-3-medium-128k-instruct.
- `<number of epochs>` refers to the total number of epochs will run in the fine-tuning process.
- `<learning rate>` is to set the learning rate.
- `<save checkpoint period>` denotes the interval at which checkpoints are saved.

### Detection
#### Environment

Python 3.10.12

#### Install dependencies

```cmd
$ pip install -r requirements.txt
```
#### Using OpenAI's Models
##### Set OpenAI API key

Follow the instructions in [OpenAI](https://platform.openai.com/docs/quickstart/step-2-set-up-your-api-key) for instructions on setting OpenAI API key

##### Start detection

Run detector with the following command:

```cmd
$ python main.py -tx <transaction hash> -bp <chain ID>
```

- Where `<transaction hash>` is the transaction hash of the test transaction
- Where `<chain ID>` is the blockchain platform where test transaction is on. The blockchain platforms supported by the detector include Ethereum (`chain ID` = ethereum), BSC (`chain ID` = bsc).

#### Using Local Models
##### Start detection

Run detector with the following command:

```cmd
$ python main.py -tx <transaction hash> -bp <chain ID> --use_local_model --model_path <model path>
```

- Where `<model path>` can be either a local path or a huggingface model name, e.g. microsoft/Phi-3-medium-128k-instruct.

#### Detection result

Detection result is stored in `detection_result.jsonl`
