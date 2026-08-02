import pandas as pd
df2 = pd.read_csv('model_assets/raw/tickets2.csv/helpdesk_tickets.csv')
print('tickets2 Assigned_Team distribution:')
print(df2['Assigned_Team'].value_counts())
print()
print('tickets2 Description samples per team:')
for team in df2['Assigned_Team'].unique():
    print(f'\n--- {team} ---')
    for s in df2[df2['Assigned_Team']==team]['Description'].head(5):
        print(f'  {repr(str(s)[:200])}')

print()
print('=== TEMPLATE DETECTION ===')
df2['prefix'] = df2['Description'].str[:40]
print('Most common prefixes:')
print(df2['prefix'].value_counts().head(10))
print()
print('Unique descriptions:', df2['Description'].nunique())
print('Total rows:', len(df2))
