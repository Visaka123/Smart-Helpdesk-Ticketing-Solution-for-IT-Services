#!/usr/bin/env python3
"""
backend/seed.py

Developer seeding tool for realistic support desk data.
Usage:
    python seed.py load   - Idempotently loads 5 realistic agents, schedules, and 14 network tickets.
    python seed.py reset  - Removes ONLY seeded records (is_demo=True), preserving real users and tickets.
"""

import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.ticket import Ticket
from app.models.team import Team
from app.models.availability import AgentShift, AgentLeave, OnCallRoster
from app.auth.hashing import hash_password

SEEDED_PASSWORD_PLAIN = "HelpDesk@2026"

SEEDED_AGENTS = [
    {
        "name": "Ravi",
        "email": "ravi@smartdesk.com",
        "role": "agent",
        "team": "Network Operations",
        "dept": "Network Operations",
        "tz": "Asia/Kolkata",
        "cap": 10,
        "scenario": "On leave (approved leave covering now)",
    },
    {
        "name": "Priya",
        "email": "priya@smartdesk.com",
        "role": "agent",
        "team": "Network Operations",
        "dept": "Network Operations",
        "tz": "Asia/Kolkata",
        "cap": 10,
        "scenario": "Off shift (shift ended 1 hour ago)",
    },
    {
        "name": "Arun",
        "email": "arun@smartdesk.com",
        "role": "agent",
        "team": "Network Operations",
        "dept": "Network Operations",
        "tz": "Asia/Kolkata",
        "cap": 10,
        "scenario": "At capacity (in shift, 10/10 tickets)",
    },
    {
        "name": "Meena",
        "email": "meena@smartdesk.com",
        "role": "agent",
        "team": "Network Operations",
        "dept": "Network Operations",
        "tz": "Asia/Kolkata",
        "cap": 10,
        "scenario": "Available (in shift, 3/10 tickets)",
    },
    {
        "name": "Kiran",
        "email": "kiran@smartdesk.com",
        "role": "agent",
        "team": "Network Operations",
        "dept": "Network Operations",
        "tz": "Asia/Kolkata",
        "cap": 10,
        "scenario": "Available / On-call (in shift, 1/10 tickets)",
    },
]

SEEDED_EMAILS = [a["email"] for a in SEEDED_AGENTS]

REALISTIC_TICKETS = [
    # 10 tickets for Arun (10/10 at cap)
    {
        "agent": "Arun",
        "title": "VPN disconnects every 10 minutes",
        "desc": "Remote employees on macOS and Windows report intermittent SSL-VPN dropouts every 10 minutes during peak hours.",
        "category": "Access",
        "priority": "High",
        "requester": "Devon Vance",
        "dept": "Finance",
    },
    {
        "agent": "Arun",
        "title": "Wi-Fi drops in conference room 3",
        "desc": "AP-304 in Executive Boardroom 3 drops 5GHz signal under high client density during all-hands presentations.",
        "category": "Network",
        "priority": "Medium",
        "requester": "Priya Sharma",
        "dept": "Marketing",
    },
    {
        "agent": "Arun",
        "title": "Switch port down on floor 2",
        "desc": "Port Gi1/0/24 on Access Switch SW-FL2 went into err-disabled state after continuous broadcast storms.",
        "category": "Hardware",
        "priority": "High",
        "requester": "Rajesh Gupta",
        "dept": "Operations",
    },
    {
        "agent": "Arun",
        "title": "Cannot reach file server from branch office",
        "desc": "Site-to-site IPsec tunnel Phase 2 SA expired between Hyderabad branch and main datacenter.",
        "category": "Network",
        "priority": "High",
        "requester": "Carlos Rivera",
        "dept": "Legal",
    },
    {
        "agent": "Arun",
        "title": "Firewall rule request for the new CRM",
        "desc": "Allow outbound HTTPS (TCP 443) from internal subnet 10.20.4.0/24 to external vendor API endpoints.",
        "category": "Security",
        "priority": "Medium",
        "requester": "Sunita Nair",
        "dept": "Sales",
    },
    {
        "agent": "Arun",
        "title": "Slow internet in the Finance area",
        "desc": "Finance workstation cluster experiencing packet loss and high DNS latency on default gateway 10.10.12.1.",
        "category": "Network",
        "priority": "Medium",
        "requester": "Marcus Brody",
        "dept": "Accounting",
    },
    {
        "agent": "Arun",
        "title": "IP address conflict on VLAN 10",
        "desc": "DHCP snooping detected rogue static IP 10.10.10.45 conflicting with critical payroll print server.",
        "category": "Network",
        "priority": "High",
        "requester": "Emily Chen",
        "dept": "Engineering",
    },
    {
        "agent": "Arun",
        "title": "Core switch redundant power supply fault",
        "desc": "Datacenter Core Switch chassis reports PSU-2 voltage alert and amber fault LED.",
        "category": "Hardware",
        "priority": "Critical",
        "requester": "Farhan Akhtar",
        "dept": "Facilities",
    },
    {
        "agent": "Arun",
        "title": "DNS resolution failing for internal portal",
        "desc": "Secondary internal DNS forwarder timing out on lookups for dev.portal.smartdesk.local.",
        "category": "Network",
        "priority": "High",
        "requester": "Ananya Deshmukh",
        "dept": "Customer Support",
    },
    {
        "agent": "Arun",
        "title": "Guest Wi-Fi portal SSL certificate expired",
        "desc": "Captive portal redirect triggers untrusted certificate warnings on visitor mobile devices.",
        "category": "Security",
        "priority": "Medium",
        "requester": "Vikram Malhotra",
        "dept": "Executive",
    },
    # 3 tickets for Meena (3/10 available)
    {
        "agent": "Meena",
        "title": "Latency spike on primary MPLS circuit",
        "desc": "WAN link ping times jumped from 18ms to 240ms between Bangalore and Mumbai offices.",
        "category": "Network",
        "priority": "High",
        "requester": "Sneha Iyer",
        "dept": "Quality Assurance",
    },
    {
        "agent": "Meena",
        "title": "Bandwidth saturation on 4th floor access point",
        "desc": "802.11ax AP on 4th floor showing 98% channel utilization on 2.4GHz spectrum.",
        "category": "Network",
        "priority": "Medium",
        "requester": "David Miller",
        "dept": "Product",
    },
    {
        "agent": "Meena",
        "title": "BGP route flap with upstream transit provider",
        "desc": "Autonomous system border router logged 6 peering session resets in the last 45 minutes.",
        "category": "Network",
        "priority": "Critical",
        "requester": "Pooja Reddy",
        "dept": "IT",
    },
    # 1 ticket for Kiran (1/10 available + on-call)
    {
        "agent": "Kiran",
        "title": "Out-of-band management console unreachable",
        "desc": "Dedicated terminal server interface on 192.168.100.12 not responding to SSH requests.",
        "category": "Access",
        "priority": "Medium",
        "requester": "Deepak Joshi",
        "dept": "Human Resources",
    },
]

REALISTIC_RESOLVED_TICKETS = [
    {
        "title": "VPN error 809 remote connection could not be established",
        "desc": "Remote employee unable to connect to corporate L2TP/IPsec VPN from home router. Receiving Windows error 809 stating network gateway did not respond.",
        "category": "Network",
        "priority": "High",
        "team": "Network Operations",
        "requester": "Rachel Green",
        "dept": "Marketing",
        "root_cause": "Network",
        "summary": "Configured Windows registry key AssumeUDPEncapsulationContextOnSendRule under HKLM\\SYSTEM\\CurrentControlSet\\Services\\PolicyAgent to value 2 to support NAT-T traversal behind consumer routers. Verified UDP ports 500 and 4500 firewall traversal on corporate edge gateway. Remote client successfully established stable VPN tunnel.",
    },
    {
        "title": "Outlook mailbox full error 0x8004060C cannot send or receive email",
        "desc": "Employee reports Microsoft Outlook warning that Exchange mailbox quota exceeded 50GB, preventing inbound and outbound messages.",
        "category": "Email",
        "priority": "Medium",
        "team": "IT Support",
        "requester": "Ross Geller",
        "dept": "Research",
        "root_cause": "Software",
        "summary": "Executed Exchange Online retention policy to automatically move emails older than 12 months to Online In-Place Archive. Emptied Deleted Items and Recoverable Items folders, freeing 14 GB of primary storage. Upgraded user mailbox license from Exchange Online Plan 1 to Plan 2 to double maximum quota.",
    },
    {
        "title": "Excel crashes opening large 150MB financial report file",
        "desc": "Microsoft Excel application stops responding and force closes when opening large XLSX financial forecasting workbook containing external data queries.",
        "category": "Software",
        "priority": "High",
        "team": "IT Support",
        "requester": "Monica Geller",
        "dept": "Finance",
        "root_cause": "Software",
        "summary": "Disabled problematic third-party COM add-ins and cleared cached pivot table schemas in Excel Trust Center. Updated 32-bit Office installation to 64-bit Microsoft 365 Enterprise build to eliminate 2GB virtual memory address space exhaustion. Workbook now opens smoothly and calculates data model within 10 seconds.",
    },
    {
        "title": "Domain account locked out after multiple failed logon attempts",
        "desc": "User locked out of Windows Active Directory workstation and corporate single sign-on portal after password change.",
        "category": "Access",
        "priority": "Medium",
        "team": "IT Support",
        "requester": "Chandler Bing",
        "dept": "Procurement",
        "root_cause": "User Error",
        "summary": "Unlocked user account in Active Directory Domain Controller and flushed stale Kerberos ticket cache on client machine using klist purge. Identified cached expired credentials in Windows Credential Manager from mapped network drives causing automatic lockout loops. Cleared credential entries and confirmed user logged in successfully with MFA.",
    },
    {
        "title": "Floor 3 HP LaserJet printer recurring paper jam error in Tray 2",
        "desc": "HP Enterprise LaserJet printer in 3rd floor copy room repeatedly halts with error 13.00.00 paper jam inside pickup roller area.",
        "category": "Hardware",
        "priority": "Low",
        "team": "IT Support",
        "requester": "Joey Tribbiani",
        "dept": "Sales",
        "root_cause": "Hardware",
        "summary": "Inspected internal paper feed path and extracted a torn sheet fragment caught in the duplexing registration assembly. Cleaned optical paper feed sensors and replaced worn pickup and feed separation rollers on Tray 2 with OEM maintenance kit. Ran 50-page duplex test print job without paper feed failures.",
    },
    {
        "title": "File server shares unreachable from Chicago branch office",
        "desc": "Chicago branch office staff cannot reach corporate file server shares on 10.20.4.15 over the IPsec VPN tunnel; SMB timeout error 0x80070035.",
        "category": "Network",
        "priority": "High",
        "team": "Network Operations",
        "requester": "Phoebe Buffay",
        "dept": "Operations",
        "root_cause": "Network",
        "summary": "Diagnosed asymmetric routing caused by dropped BGP route advertisement on the Chicago branch Cisco router. Re-established IPsec phase 2 security association and restored static failover route for the 10.20.0.0/16 subnet. Verified bidirectional ping latency and confirmed SMB file shares mounted successfully for branch users.",
    },
    {
        "title": "Corporate 802.1X Wi-Fi network connection refused invalid certificate",
        "desc": "Laptops fail to connect to Secure-Corp Wi-Fi SSID with authentication error indicating the RADIUS server certificate has expired.",
        "category": "Network",
        "priority": "High",
        "team": "Network Operations",
        "requester": "Gunther Central",
        "dept": "Facilities",
        "root_cause": "Network",
        "summary": "Renewed the enterprise Wi-Fi root CA certificate on the FreeRADIUS cluster and bound the new TLS cert to EAP-PEAP profiles. Pushed the updated trusted root certificate authority profile to all managed workstations via Microsoft Intune MDM. Verified endpoint Wi-Fi handshake and authenticated 120 client devices.",
    },
    {
        "title": "Docker socket permission denied error connect to docker daemon",
        "desc": "Software engineer encounters 'Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock' on Linux workstation.",
        "category": "Application/Backend",
        "priority": "Medium",
        "team": "DevOps",
        "requester": "Mike Hannigan",
        "dept": "Engineering",
        "root_cause": "Permission",
        "summary": "Added the developer user account to the system docker group via usermod -aG docker and applied socket ACL permissions. Restarted docker.socket systemd service unit and instructed user to execute newgrp docker or log out to reload group memberships. Verified non-root execution of docker ps and container builds.",
    },
    {
        "title": "Zoom meeting audio device missing cannot detect microphone or speaker",
        "desc": "Zoom client displays error 'No audio device detected' during video conferences; internal Realtek microphone and headset output are unresponsive.",
        "category": "Software",
        "priority": "Medium",
        "team": "IT Support",
        "requester": "Janice Hosenstein",
        "dept": "Human Resources",
        "root_cause": "Software",
        "summary": "Re-enabled microphone hardware access permissions under Windows Privacy & Security settings for desktop applications. Reinstalled the latest OEM Realtek High Definition Audio driver and restarted the Windows Audio service. Tested Zoom audio loopback test call, confirming crisp microphone capture and audio playback.",
    },
    {
        "title": "IntelliJ IDEA Ultimate license ticket expired cannot activate",
        "desc": "Backend developer unable to launch IntelliJ IDEA Ultimate; IDE prompts for license activation key stating subscription expired.",
        "category": "Software",
        "priority": "Medium",
        "team": "IT Support",
        "requester": "David Scientist",
        "dept": "Engineering",
        "root_cause": "License",
        "summary": "Configured IntelliJ License Activation settings to point to corporate JetBrains Floating License Server at license.corp.internal:8080. Allocated an active JetBrains All Products Pack enterprise seat to user email in JetBrains Organization Admin Portal. IDE activated successfully with permanent corporate floating ticket.",
    },
    {
        "title": "SAP GUI connection timeout error 10060 connecting to ERP production",
        "desc": "Finance users experiencing WSAETIMEDOUT error 10060 when opening SAP GUI logon pad connecting to PRD SAP instance.",
        "category": "Application/Backend",
        "priority": "Critical",
        "team": "SAP / ERP Team",
        "requester": "Richard Burke",
        "dept": "Finance",
        "root_cause": "Application",
        "summary": "Cleared corrupted saplogon.ini cache and updated SAP GUI dispatcher port 3200 gateway rule in the corporate firewall. Re-synchronized user application server router strings in SAP Logon Pad to secondary application server instance PRD-APP-02. Verified standard SU53 transaction execution and financial report extraction without timeouts.",
    },
    {
        "title": "SSL certificate warning NET::ERR_CERT_DATE_INVALID on internal portal",
        "desc": "Web browsers displaying SSL certificate expired security warning when navigating to internal employee self-service portal.",
        "category": "Security",
        "priority": "High",
        "team": "Security",
        "requester": "Emma Geller",
        "dept": "Legal",
        "root_cause": "Security",
        "summary": "Issued a renewed 2-year wildcard TLS certificate from corporate DigiCert CA and deployed it to the IIS reverse proxy server on port 443. Replaced expired certificate bindings in IIS Manager and verified complete TLS certificate chain using OpenSSL s_client. Confirmed internal portal loads with green padlock and zero security warnings.",
    },
]


def seed_reset():
    """Removes only records flagged with is_demo=True."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        demo_user_ids = [u[0] for u in db.query(User.id).filter(User.is_demo == True).all()]
        deleted_shifts = db.query(AgentShift).filter(AgentShift.is_demo == True).delete(synchronize_session=False)
        deleted_leaves = db.query(AgentLeave).filter(AgentLeave.is_demo == True).delete(synchronize_session=False)
        deleted_oncall = db.query(OnCallRoster).filter(OnCallRoster.is_demo == True).delete(synchronize_session=False)
        deleted_tickets = db.query(Ticket).filter(Ticket.is_demo == True).delete(synchronize_session=False)
        deleted_users = db.query(User).filter(User.is_demo == True).delete(synchronize_session=False)
        db.commit()

        print("[RESET COMPLETE]")
        print(f"  Removed: {deleted_users} agents, {deleted_shifts} shifts, {deleted_leaves} leaves, {deleted_oncall} on-call entries, {deleted_tickets} tickets.")
        print("  Real data (Sarah Agent, Mike Network Agent, real tickets) was preserved.")
    finally:
        db.close()


def seed_load():
    """Idempotently loads 5 realistic agents, schedules, and tickets."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Clean previous seeded data
        demo_user_ids = [u[0] for u in db.query(User.id).filter(User.is_demo == True).all()]
        if demo_user_ids:
            db.query(AgentShift).filter(AgentShift.agent_id.in_(demo_user_ids)).delete(synchronize_session=False)
            db.query(AgentLeave).filter(AgentLeave.agent_id.in_(demo_user_ids)).delete(synchronize_session=False)
            db.query(OnCallRoster).filter(OnCallRoster.agent_id.in_(demo_user_ids)).delete(synchronize_session=False)
        db.query(Ticket).filter(Ticket.is_demo == True).delete(synchronize_session=False)
        db.commit()

        # 2. Ensure "Network Operations" team exists in teams table
        net_team = db.query(Team).filter(Team.name == "Network Operations").first()
        if not net_team:
            mgr = db.query(User).filter(User.role == "manager").first()
            net_team = Team(
                name="Network Operations",
                manager_id=mgr.id if mgr else None,
                manager_name=mgr.name if mgr else "John Manager",
                manager_email=mgr.email if mgr else "manager@helpdesk.com",
            )
            db.add(net_team)
            db.commit()

        # 3. Fix Mike Network Agent and Sarah Agent in DB
        mike = db.query(User).filter(User.name.like("%Mike%")).first()
        if mike:
            mike.timezone = "Asia/Kolkata"
            mike.assigned_team = "Network Operations"
            mike.department = "Network Operations, Network, Security"
            # Activate Mike's shift
            mike_shift = db.query(AgentShift).filter(AgentShift.agent_id == mike.id).first()
            if mike_shift:
                mike_shift.is_active = True
                mike_shift.weekday = 0
                mike_shift.start_time = "09:00"
                mike_shift.end_time = "17:00"
            else:
                db.add(AgentShift(
                    agent_id=mike.id,
                    agent_name=mike.name,
                    weekday=0,
                    start_time="09:00",
                    end_time="17:00",
                    is_active=True,
                    is_demo=False,
                ))

        sarah = db.query(User).filter(User.name.like("%Sarah%")).first()
        if sarah:
            sarah.timezone = "Asia/Kolkata"
            sarah.assigned_team = "IT Support"
            sarah.department = "IT Operations, Software, Hardware, Access, Email, Application/Backend, Printer"
        db.commit()

        # 4. Upsert 5 realistic agents
        pw_hash = hash_password(SEEDED_PASSWORD_PLAIN)
        user_map = {}
        for spec in SEEDED_AGENTS:
            u = db.query(User).filter(User.email == spec["email"]).first()
            if not u:
                u = User(
                    name=spec["name"],
                    email=spec["email"],
                    password=pw_hash,
                    role="agent",
                    assigned_team=spec["team"],
                    department=spec["dept"],
                    timezone=spec["tz"],
                    max_open_tickets=spec["cap"],
                    is_demo=True,
                )
                db.add(u)
                db.commit()
                db.refresh(u)
            else:
                u.name = spec["name"]
                u.password = pw_hash
                u.role = "agent"
                u.assigned_team = spec["team"]
                u.department = spec["dept"]
                u.timezone = spec["tz"]
                u.max_open_tickets = spec["cap"]
                u.is_demo = True
                db.commit()
            user_map[spec["name"]] = u

        # 5. Times relative to NOW in Asia/Kolkata
        try:
            kolkata_tz = ZoneInfo("Asia/Kolkata")
        except Exception:
            kolkata_tz = ZoneInfo("UTC")

        now_ist = datetime.now(kolkata_tz)
        now_utc = datetime.utcnow()

        def upsert_shift(agent_id, agent_name, weekday, start_time, end_time):
            shift = db.query(AgentShift).filter(
                AgentShift.agent_id == agent_id,
                AgentShift.weekday == weekday,
                AgentShift.start_time == start_time,
                AgentShift.end_time == end_time,
            ).first()
            if shift:
                shift.is_active = True
                shift.is_demo = True
                shift.agent_name = agent_name
            else:
                shift = AgentShift(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    weekday=weekday,
                    start_time=start_time,
                    end_time=end_time,
                    is_active=True,
                    is_demo=True,
                )
                db.add(shift)
            return shift

        active_start_dt = now_ist - timedelta(hours=2)
        active_end_dt   = now_ist + timedelta(hours=6)
        active_start_str = active_start_dt.strftime("%H:%M")
        active_end_str   = active_end_dt.strftime("%H:%M")
        active_weekday   = active_start_dt.weekday()

        # Ravi: Active shift + Approved leave covering NOW
        upsert_shift(user_map["Ravi"].id, "Ravi", active_weekday, active_start_str, active_end_str)
        for d in range(7):
            if d != active_weekday:
                upsert_shift(user_map["Ravi"].id, "Ravi", d, "09:00", "17:00")

        db.add(AgentLeave(
            agent_id=user_map["Ravi"].id,
            agent_name="Ravi",
            start_datetime=now_utc - timedelta(hours=4),
            end_datetime=now_utc + timedelta(hours=20),
            leave_type="annual",
            status="approved",
            is_processed=True,
            notes="Annual Leave covering current shift window",
            is_demo=True,
        ))

        # Priya: Shift ended exactly 1 hour ago
        priya_end_dt = now_ist - timedelta(hours=1)
        priya_start_dt = priya_end_dt - timedelta(hours=8)
        priya_start_str = priya_start_dt.strftime("%H:%M")
        priya_end_str = priya_end_dt.strftime("%H:%M")
        priya_weekday = priya_start_dt.weekday()
        upsert_shift(user_map["Priya"].id, "Priya", priya_weekday, priya_start_str, priya_end_str)

        # Arun, Meena, Kiran: In-shift window covering NOW, plus 09:00-17:00 on other 6 days
        for name in ["Arun", "Meena", "Kiran"]:
            upsert_shift(user_map[name].id, name, active_weekday, active_start_str, active_end_str)
            for d in range(7):
                if d != active_weekday:
                    upsert_shift(user_map[name].id, name, d, "09:00", "17:00")

        # Kiran: On-call entry covering now
        db.add(OnCallRoster(
            agent_id=user_map["Kiran"].id,
            agent_name="Kiran",
            team_name="Network Operations",
            start_dt=now_utc - timedelta(hours=2),
            end_dt=now_utc + timedelta(hours=22),
            is_demo=True,
        ))

        # 6. Add 14 realistic tickets
        for t_spec in REALISTIC_TICKETS:
            agent_name = t_spec["agent"]
            agent_user = user_map[agent_name]
            db.add(Ticket(
                title=t_spec["title"],
                description=t_spec["desc"],
                category=t_spec["category"],
                priority=t_spec["priority"],
                status="open",
                assigned_team="Network Operations",
                assigned_agent_id=agent_user.id,
                assigned_agent_name=agent_name,
                routing_confidence=0.98,
                requester_name=t_spec["requester"],
                requester_department=t_spec["dept"],
                created_at=now_utc - timedelta(hours=2),
                sla_due_at=now_utc + timedelta(hours=24),
                is_demo=True,
            ))

        db.commit()

        # 7. Add 12 realistic resolved tickets with concrete resolution notes
        resolved_titles = [r["title"] for r in REALISTIC_RESOLVED_TICKETS]
        db.query(Ticket).filter(Ticket.title.in_(resolved_titles)).delete(synchronize_session=False)
        db.commit()

        sarah_user = db.query(User).filter(User.name.like("%Sarah%")).first()
        meena_user = db.query(User).filter(User.name.like("%Meena%")).first()

        for idx, r_spec in enumerate(REALISTIC_RESOLVED_TICKETS):
            is_net = "Network" in r_spec["team"]
            agent_id = meena_user.id if (is_net and meena_user) else (sarah_user.id if sarah_user else None)
            agent_name = "Meena" if (is_net and meena_user) else (sarah_user.name if sarah_user else "Sarah Agent")

            res_ticket = Ticket(
                title=r_spec["title"],
                description=r_spec["desc"],
                category=r_spec["category"],
                priority=r_spec["priority"],
                status="resolved",
                assigned_team=r_spec["team"],
                assigned_agent_id=agent_id,
                assigned_agent_name=agent_name,
                routing_confidence=0.99,
                root_cause=r_spec["root_cause"],
                resolution_summary=r_spec["summary"],
                resolution_notes=r_spec["summary"],
                resolution_detail=r_spec["summary"],
                requester_name=r_spec["requester"],
                requester_department=r_spec["dept"],
                created_at=now_utc - timedelta(days=4, hours=idx),
                resolved_at=now_utc - timedelta(days=2, hours=idx),
                sla_due_at=now_utc - timedelta(days=3),
                is_demo=False,
            )
            db.add(res_ticket)
        db.commit()

        # Terminal output
        shifts_count = db.query(AgentShift).filter(AgentShift.is_demo == True, AgentShift.is_active == True).count()
        tickets_count = db.query(Ticket).filter(Ticket.is_demo == True).count()

        print("=================================================================")
        print("                 SMART HELPDESK SEED COMPLETE                    ")
        print("=================================================================")
        print(f"Agents Created : {len(SEEDED_AGENTS)}")
        print(f"Shifts Active  : {shifts_count}")
        print(f"Tickets Seeded : {tickets_count}")
        print("-----------------------------------------------------------------")
        print(f"{'AGENT':<10} {'EMAIL':<25} {'PASSWORD':<16} {'EXPECTED STATE'}")
        print("-----------------------------------------------------------------")
        for a in SEEDED_AGENTS:
            print(f"{a['name']:<10} {a['email']:<25} {SEEDED_PASSWORD_PLAIN:<16} {a['scenario']}")
        print("-----------------------------------------------------------------")
        print("Times computed relative to current Asia/Kolkata wall clock.")
        print("Credentials printed above for local testing. Never shown in UI.")
        print("=================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("load", "reset"):
        print("Usage:")
        print("  python seed.py load   - Seed 5 realistic agents, shifts, and 14 tickets")
        print("  python seed.py reset  - Reset and delete only seeded rows")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "load":
        seed_load()
    elif cmd == "reset":
        seed_reset()
