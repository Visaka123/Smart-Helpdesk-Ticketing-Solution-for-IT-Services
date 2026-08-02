from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
import pandas as pd
import pickle

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

df = pd.read_csv(
    "datasets/tickets.csv"
)

X = model.encode(
    df["description"].tolist()
)

y = df["assigned_team"]

clf = LogisticRegression(
    max_iter=2000
)

clf.fit(X,y)

pickle.dump(
    clf,
    open("router.pkl","wb")
)

print("Model Trained")