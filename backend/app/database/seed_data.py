import json
from datetime import datetime, timedelta
from app.database.database import SessionLocal, engine, Base
from app.models import User, Team, Ticket, TicketComment, KnowledgeArticle
from app.auth.hashing import hash_password

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 1. Seed Users
    if db.query(User).count() == 0:
        default_users = [
            User(
                name="Admin User",
                email="admin@helpdesk.com",
                password=hash_password("admin123"),
                role="admin",
                department="IT Administration",
            ),
            User(
                name="John Manager",
                email="manager@helpdesk.com",
                password=hash_password("manager123"),
                role="manager",
                department="IT Management",
                assigned_team="IT Support",
            ),
            User(
                name="Sarah Agent",
                email="agent@helpdesk.com",
                password=hash_password("agent123"),
                role="agent",
                department="IT Operations",
                assigned_team="IT Support",
            ),
            User(
                name="Mike Network Agent",
                email="mike.agent@helpdesk.com",
                password=hash_password("agent123"),
                role="agent",
                department="Network Operations",
                assigned_team="Network Team",
            ),
            User(
                name="Alice Employee",
                email="alice@company.com",
                password=hash_password("user123"),
                role="employee",
                department="Finance",
            ),
            User(
                name="Bob Sales Employee",
                email="bob@company.com",
                password=hash_password("user123"),
                role="employee",
                department="Sales",
            ),
        ]
        db.add_all(default_users)
        db.commit()
        print("[SEED] Created default users.")

    manager = db.query(User).filter(User.role == "manager").first()
    manager_id = manager.id if manager else None

    # 2. Seed Teams & SLA Policies
    if db.query(Team).count() == 0:
        teams_data = [
            ("IT Support", manager_id, "John Manager", "manager@helpdesk.com", 2.0, 8.0, 4.0, 24.0, 8.0, 48.0, 24.0, 72.0),
            ("Network Team", manager_id, "John Manager", "manager@helpdesk.com", 1.0, 4.0, 2.0, 12.0, 4.0, 24.0, 12.0, 48.0),
            ("Database Team", manager_id, "John Manager", "manager@helpdesk.com", 1.5, 6.0, 3.0, 18.0, 6.0, 36.0, 18.0, 60.0),
            ("Security Team", manager_id, "John Manager", "manager@helpdesk.com", 0.5, 2.0, 1.0, 8.0, 2.0, 16.0, 8.0, 24.0),
            ("SAP Team", manager_id, "John Manager", "manager@helpdesk.com", 2.0, 12.0, 6.0, 36.0, 12.0, 72.0, 24.0, 96.0),
            ("HR Support", manager_id, "John Manager", "manager@helpdesk.com", 4.0, 24.0, 8.0, 48.0, 16.0, 96.0, 48.0, 120.0),
            ("Billing & Payments", manager_id, "John Manager", "manager@helpdesk.com", 2.0, 8.0, 4.0, 24.0, 8.0, 48.0, 24.0, 72.0),
            ("Unassigned/Triage", manager_id, "John Manager", "manager@helpdesk.com", 1.0, 4.0, 2.0, 8.0, 4.0, 16.0, 8.0, 24.0),
        ]
        for t_name, m_id, m_name, m_email, r_crit, res_crit, r_high, res_high, r_med, res_med, r_low, res_low in teams_data:
            db.add(Team(
                name=t_name,
                manager_id=m_id,
                manager_name=m_name,
                manager_email=m_email,
                sla_response_hours_critical=r_crit,
                sla_resolve_hours_critical=res_crit,
                sla_response_hours_high=r_high,
                sla_resolve_hours_high=res_high,
                sla_response_hours_medium=r_med,
                sla_resolve_hours_medium=res_med,
                sla_response_hours_low=r_low,
                sla_resolve_hours_low=res_low,
            ))
        db.commit()
        print("[SEED] Created default teams & SLA policies.")

    # 3. Seed Knowledge Base Articles
    if db.query(KnowledgeArticle).count() == 0:
        articles = [
            KnowledgeArticle(
                title="VPN Connection and Multi-Factor Authentication Troubleshooting",
                category="Network & VPN",
                content="""If your VPN fails to connect:
1. Ensure your Cisco AnyConnect or GlobalProtect client is updated to the latest version.
2. Open your authenticator app (Okta / Microsoft Authenticator) and verify your OTP token code.
3. Check if your home Wi-Fi DNS is blocking UDP port 4500 or IPsec traffic.
4. If you see 'Server Certificate Invalid', reconnect via server gateway vpn.company.com:443.
5. Restart the VPN service or clear your local DNS cache with 'ipconfig /flushdns' in Command Prompt.""",
                source_file="vpn_troubleshooting_guide.md",
                helpful_count=24,
            ),
            KnowledgeArticle(
                title="Password Reset Self-Service & Account Lockout Clearance",
                category="Account Security",
                content="""Account lockouts occur after 5 failed login attempts.
To unlock or reset your password:
1. Visit https://identity.company.com/reset.
2. Enter your corporate email address and complete the SMS/Authenticator verification code.
3. Choose a new password minimum 12 characters including 1 uppercase, 1 symbol, and 1 number.
4. Wait 2 minutes for Active Directory replication across domain controllers before logging in again.""",
                source_file="identity_management_sop.md",
                helpful_count=42,
            ),
            KnowledgeArticle(
                title="Outlook Web & Desktop Email Sync Issues",
                category="Email & Desktop",
                content="""When Microsoft Outlook fails to sync emails or shows 'Disconnected':
1. Check Microsoft 365 status page or local exchange server availability.
2. Toggle Offline Mode: In Outlook, go to Send/Receive tab -> click 'Work Offline' to toggle off/on.
3. Repair Outlook Profile: Go to File -> Account Settings -> Account Settings -> Select profile -> click Repair.
4. Clear OST Cache: Navigate to %localappdata%\\Microsoft\\Outlook and rename your .ost file to .ost.old while Outlook is closed.""",
                source_file="outlook_repair_kb.md",
                helpful_count=18,
            ),
            KnowledgeArticle(
                title="SAP ERP Session Timeout and Authorization Errors",
                category="SAP Support",
                content="""For SAP GUI error 'Authorization check failed for transaction SU53':
1. Take a screenshot of transaction code /nSU53 showing the missing authorization object.
2. Verify if your SAP GUI kernel release matches version 770 patch level 8+.
3. Contact SAP Team with your User ID and screenshot for security role assignment.
4. Clear SAP GUI cache in Options -> Local Data -> History -> Clear History.""",
                source_file="sap_troubleshooting_manual.md",
                helpful_count=15,
            ),
            KnowledgeArticle(
                title="Wi-Fi 6 Corporate Network Onboarding (802.1X)",
                category="Network & Wireless",
                content="""To connect your corporate laptop to 'Company-Corporate' SSID:
1. Select WPA3-Enterprise security with PEAP authentication.
2. Set EAP Method to MSCHAPv2.
3. Trust Root CA certificate 'Company-Internal-Root-CA'.
4. Enter your domain credentials in domain\\username format.""",
                source_file="wireless_onboarding.md",
                helpful_count=30,
            ),
        ]
        db.add_all(articles)
        db.commit()
        print("[SEED] Created Knowledge Base Articles.")

    # 4. Seed Initial Sample Tickets
    if db.query(Ticket).count() == 0:
        now = datetime.now()
        agent = db.query(User).filter(User.role == "agent").first()
        agent_id = agent.id if agent else None
        user = db.query(User).filter(User.role == "employee").first()
        user_id = user.id if user else None

        sample_tickets = [
            Ticket(
                title="VPN Connection Fails with Certificate Error",
                description="I cannot connect to the corporate VPN from home. Cisco AnyConnect says 'Server certificate verification failed'. I need access to internal servers urgently for monthly report generation.",
                category="Network",
                priority="High",
                priority_confidence=0.92,
                status="open",
                assigned_team="Network Team",
                assigned_agent_id=agent_id,
                assigned_agent_name="Sarah Agent",
                routing_confidence=0.94,
                top_alternative_teams=json.dumps([{"team": "Network Team", "confidence": 0.94}, {"team": "IT Support", "confidence": 0.04}]),
                created_by=user_id,
                requester_name="Alice Employee",
                requester_department="Finance",
                created_at=now - timedelta(hours=5),
                sla_due_at=now + timedelta(hours=19), # High SLA = 24h
            ),
            Ticket(
                title="SAP ERP Transaction SU53 Authorization Denied",
                description="Getting SU53 permission denied error when attempting to run transaction code ME21N to generate purchase orders. Please grant SAP procurement role.",
                category="SAP Support",
                priority="Medium",
                priority_confidence=0.88,
                status="open",
                assigned_team="SAP Team",
                routing_confidence=0.91,
                top_alternative_teams=json.dumps([{"team": "SAP Team", "confidence": 0.91}, {"team": "IT Support", "confidence": 0.06}]),
                created_by=user_id,
                requester_name="Bob Sales Employee",
                requester_department="Sales",
                created_at=now - timedelta(hours=45),
                sla_due_at=now - timedelta(hours=3), # SLA Breached! (Medium SLA = 48h)
                is_sla_breached=True,
                escalated_to_manager=True,
                escalated_at=now - timedelta(hours=1),
            ),
            Ticket(
                title="Database Connection Timeout on MySQL Production Cluster",
                description="CRITICAL: Production application server is getting Connection Timeout errors when querying MySQL DB cluster 2. Customers are experiencing 504 Gateway errors.",
                category="Database",
                priority="Critical",
                priority_confidence=0.98,
                status="in_progress",
                assigned_team="Database Team",
                assigned_agent_id=agent_id,
                assigned_agent_name="Sarah Agent",
                routing_confidence=0.96,
                top_alternative_teams=json.dumps([{"team": "Database Team", "confidence": 0.96}, {"team": "Network Team", "confidence": 0.03}]),
                created_by=user_id,
                requester_name="Alice Employee",
                requester_department="Engineering",
                created_at=now - timedelta(hours=7),
                sla_due_at=now - timedelta(hours=1), # SLA Breached! (Critical SLA = 6h for DB)
                is_sla_breached=True,
                escalated_to_manager=True,
                escalated_at=now - timedelta(minutes=30),
            ),
            Ticket(
                title="Outlook Desktop Client Keeps Prompting for Password",
                description="Outlook keeps asking for my Microsoft account password every 10 minutes even after typing the correct password.",
                category="Email",
                priority="Low",
                priority_confidence=0.85,
                status="resolved",
                assigned_team="IT Support",
                assigned_agent_id=agent_id,
                assigned_agent_name="Sarah Agent",
                routing_confidence=0.89,
                top_alternative_teams=json.dumps([{"team": "IT Support", "confidence": 0.89}]),
                resolution_notes="Cleared cached credentials in Windows Credential Manager under Generic Credentials. User re-authenticated and verified Outlook stays connected.",
                resolution_summary="Cleared outdated Windows credential cache and re-authenticated user account.",
                resolution_detail="1. Closed Microsoft Outlook process.\n2. Opened Windows Credential Manager -> Generic Credentials.\n3. Removed corrupted SSO token `MicrosoftAccount:user@company.com`.\n4. Relaunched Outlook and completed MFA challenge.",
                root_cause="User Error / Cached Credentials",
                created_by=user_id,
                requester_name="Bob Sales Employee",
                requester_department="Sales",
                created_at=now - timedelta(days=2),
                resolved_at=now - timedelta(hours=12),
                sla_due_at=now + timedelta(days=1),
            ),

        ]
        db.add_all(sample_tickets)
        db.commit()
        print("[SEED] Created Sample Initial Tickets.")

    db.close()

if __name__ == "__main__":
    init_db()
