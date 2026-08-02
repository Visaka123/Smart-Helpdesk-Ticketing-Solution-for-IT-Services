from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def verify_dashboard_sla_final_state_logic():
    print("\n=======================================================================")
    print("  VERIFYING DASHBOARD KPI & SLA FINAL STATE MUTUAL EXCLUSIVITY         ")
    print("=======================================================================\n")

    # 1. Fetch Stats & Tickets
    stats = client.get("/ticket/stats").json()
    all_tickets = client.get("/ticket/all").json()

    print(f"Total Tickets in DB          : {stats['total_tickets']}")
    print(f"Active / Open Tickets (KPI) : {stats['open_tickets']}")
    print(f"Resolved / Closed (KPI)     : {stats['closed_tickets']}")
    print(f"Active SLA Breached         : {stats['breached_tickets']}")
    print(f"Active SLA At Risk          : {stats['at_risk_tickets']}\n")

    active_statuses = ["new", "open", "assigned", "in_progress", "waiting_for_user", "on_hold"]
    final_statuses = ["resolved", "closed", "cancelled"]

    # 2. Audit each ticket for mutual exclusivity
    for t in all_tickets:
        status = t["status"].lower()
        badge = t["sla_badge"]

        print(f"Ticket #{t['id']} ('{t['title'][:35]}...') | Status: {status} | SLA Badge: {badge}")

        if status in final_statuses:
            # Final state ticket must NEVER be marked BREACHED or AT_RISK in dashboard listings
            assert badge in ["RESOLVED", "COMPLETED"], f"Ticket #{t['id']} is {status} but has SLA badge '{badge}'!"
            assert status not in active_statuses, f"Status overlap for Ticket #{t['id']}!"
        elif status in active_statuses:
            assert badge in ["ON_TRACK", "AT_RISK", "BREACHED"], f"Active Ticket #{t['id']} has invalid SLA badge '{badge}'!"

    print("\n=======================================================================")
    print("  DASHBOARD KPI & SLA FINAL STATE VERIFICATION PASSED 100% CLEANLY!    ")
    print("=======================================================================\n")

if __name__ == "__main__":
    verify_dashboard_sla_final_state_logic()
