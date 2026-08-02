import pickle

from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

clf = pickle.load(
    open("router.pkl","rb")
)

def predict_team(text):

    vec = embedder.encode([text])

    team = clf.predict(vec)[0]

    return team