import pandas as pd
import os

DATASETS = [
    "datasets/raw/tickets1.csv/IT Support Ticket Data.csv",
    
    # Folder 2
    "datasets/raw/tickets2.csv/helpdesk_tickets.csv",
    
    # Folder 3 (All 5 files)
    "datasets/raw/tickets3.csv/aa_dataset-tickets-multi-lang-5-2-50-version.csv", # Check if it ends in "-version.csv" or "-versio.csv"
    "datasets/raw/tickets3.csv/dataset-tickets-german_normalized.csv",
    "datasets/raw/tickets3.csv/dataset-tickets-german_normalized_50_5_2.csv",
    "datasets/raw/tickets3.csv/dataset-tickets-multi-lang3-4k.csv",
    "datasets/raw/tickets3.csv/dataset-tickets-multi-lang-4-20k.csv",
    
    # Folder 4
    "datasets/raw/tickets4.csv/incident_event_log.csv"

]

frames = []

for file in DATASETS:

    if os.path.exists(file):

        df = pd.read_csv(file)

        frames.append(df)

master = pd.concat(
    frames,
    ignore_index=True
)

master.columns = (
    master.columns
    .str.lower()
    .str.strip()
)

print(master.head())

master.to_csv(
    "datasets/processed/master.csv",
    index=False
)

print("Dataset Combined")