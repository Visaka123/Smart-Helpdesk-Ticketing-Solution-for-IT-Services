import pandas as pd, re
from collections import Counter

df = pd.read_csv('model_assets/processed/training_real.csv')
print('Shape:', df.shape)
print(df['assigned_team'].value_counts())
print()

STOPWORDS = {
    "the","a","an","is","it","in","on","at","to","for","of","and","or","but",
    "with","this","that","are","was","were","be","been","have","has","had",
    "do","does","did","will","would","could","should","may","might","i","we",
    "you","he","she","they","our","your","my","their","its","not","no","so",
    "as","by","from","am","us","me","him","her","them","which","who","what",
    "when","where","how","all","any","some","more","also","can","just","about",
    "up","out","if","into","than","then","there","these","those","such","after",
    "before","during","while","am","currently","experiencing","please","help",
    "issue","problem","need","using","use","used","would","like","want","get",
    "getting","having","having","one","two","three","new","old","first","last",
    "dear","customer","support","team","writing","report","reach","reaching",
    "hope","message","finds","well","regarding","related","contact","provide",
    "information","details","request","requesting","assistance","thank","thanks",
}

for cls in ['IT Support', 'Product Support', 'Customer Service']:
    print(f'--- {cls} (3 samples) ---')
    for s in df[df['assigned_team']==cls]['description'].head(3):
        print(f'  {repr(s[:200])}')
    print()

print('=== UNIQUE VOCABULARY PER CLASS (top 20 non-stop words) ===')
class_words = {}
for cls in df['assigned_team'].unique():
    texts = df[df['assigned_team']==cls]['description'].str.lower()
    words = []
    for t in texts:
        words.extend(re.findall(r'\b[a-z]{4,}\b', t))
    freq = Counter(w for w in words if w not in STOPWORDS)
    class_words[cls] = freq

# Show top words per class
for cls in df['assigned_team'].unique():
    top = [w for w,c in class_words[cls].most_common(25)]
    print(f'\n{cls}:')
    print(f'  {", ".join(top)}')

# Show words UNIQUE to each class (not in top words of other classes)
print('\n=== DISCRIMINATIVE WORDS (unique to each class) ===')
all_top = {}
for cls in df['assigned_team'].unique():
    all_top[cls] = set(w for w,c in class_words[cls].most_common(50))

for cls in df['assigned_team'].unique():
    others = set()
    for other_cls, words in all_top.items():
        if other_cls != cls:
            others |= words
    unique = all_top[cls] - others
    print(f'\n{cls}: {", ".join(list(unique)[:15]) if unique else "NONE — fully overlapping!"}')
