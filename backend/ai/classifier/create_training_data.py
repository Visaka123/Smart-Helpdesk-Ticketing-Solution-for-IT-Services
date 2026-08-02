import pandas as pd

from team_mapper import map_team

df = pd.read_csv(
    "datasets/processed/master.csv"
)

df["description"] = (
    df["description"]
    .fillna("")
)

df["assigned_team"] = (
    df["description"]
    .apply(map_team)
)

df.to_csv(
    "datasets/processed/training.csv",
    index=False
)

print(
    df["assigned_team"]
    .value_counts()
)