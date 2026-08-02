from app.database.database import SessionLocal
from app.models.team import Team

db=SessionLocal()

teams=[

"Network Team",
"SAP Team",
"Database Team",
"Windows Team",
"Linux Team",
"Security Team",
"HR Systems Team",
"Application Support Team"

]

for t in teams:

    db.add(
        Team(name=t)
    )

db.commit()

print("Teams Inserted")