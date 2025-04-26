from datasets import load_dataset

def load_csv_dataset(tag, file_path):
    data_files = {tag: file_path}
    dataset = load_dataset("csv", data_files=data_files)
    # print(dataset)
    # print(dataset[tag][0])
    # print(dataset[tag].features)
    return dataset[tag]