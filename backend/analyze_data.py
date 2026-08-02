import pandas as pd

df = pd.read_csv('model_assets/processed/training_real.csv')

print('=== CLASS DISTRIBUTION ===')
print(df['assigned_team'].value_counts())
print()

print('=== DESCRIPTION LENGTH STATS ===')
df['len'] = df['description'].str.len()
print(df.groupby('assigned_team')['len'].describe()[['mean','min','max']])
print()

print('=== SAMPLE DESCRIPTIONS ===')
for team in ['Technical Support', 'It Support', 'Customer Service', 'General Inquiry', 'Product Support']:
    print(f'\n--- {team} ---')
    for s in df[df['assigned_team']==team]['description'].head(3):
        print(f'  {repr(s[:180])}')

print()
print('=== NEAR-DUPLICATE CHECK (first 60 chars) ===')
df['short'] = df['description'].str.lower().str[:60]
dups = df[df.duplicated(subset=['short'], keep=False)]
print(f'Near-duplicate rows (same first 60 chars): {len(dups)}')
print()

print('=== TICKETS2 DESCRIPTION SAMPLES ===')
df2 = pd.read_csv('model_assets/raw/tickets2.csv/helpdesk_tickets.csv', nrows=5)
for s in df2['Description']:
    print(f'  {repr(str(s)[:200])}')
