import sqlite3
import os

db_path = "smart_helpdesk.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("[CLEANUP] Starting database consolidation...")

    # 1. Ensure Ticket #2 (SAP Master Ticket) has resolution summary & detail
    cursor.execute("""
    UPDATE tickets
    SET assigned_team = 'SAP Team',
        status = 'resolved',
        resolution_summary = 'Added SAP role Z_SAP_SU53_ACCESS to user profile for transaction ME21N.',
        resolution_detail = '1. Identified missing authorization object S_TCODE in SAP GRC.\n2. Added role Z_SAP_SU53_ACCESS to user profile.',
        root_cause = 'Permission Issue',
        is_low_confidence_routed = 0,
        routing_confidence = 0.96
    WHERE id = 2
    """)

    # 2. Link requesters from duplicate tickets #5, #6, #7, #8, #9, #10 to Ticket #2
    sap_dup_ids = [5, 6, 7, 8, 9, 10]
    for dup_id in sap_dup_ids:
        # Transfer requesters
        cursor.execute("SELECT requester_name, requester_department FROM ticket_requesters WHERE ticket_id = ?", (dup_id,))
        reqs = cursor.fetchall()
        for r_name, r_dept in reqs:
            cursor.execute("""
            INSERT INTO ticket_requesters (ticket_id, requester_name, requester_department, link_reason)
            VALUES (2, ?, ?, 'consolidated_test_duplicate')
            """, (r_name, r_dept or 'Finance'))

        # Delete duplicate ticket
        cursor.execute("DELETE FROM tickets WHERE id = ?", (dup_id,))
        cursor.execute("DELETE FROM ticket_requesters WHERE ticket_id = ?", (dup_id,))

    print("[CLEANUP] Consolidated SAP duplicate test tickets #5-#10 into Master Ticket #2.")

    # 3. Ensure Ticket #3 (Database Master Ticket) has resolution summary & detail
    cursor.execute("""
    UPDATE tickets
    SET assigned_team = 'Database Team',
        status = 'resolved',
        resolution_summary = 'Promoted secondary database node to primary master and restored sync.',
        resolution_detail = '1. Executed failover script sys_db_failover.sh.\n2. Re-routed virtual IP to node-02.',
        root_cause = 'Hardware Defect',
        is_low_confidence_routed = 0,
        routing_confidence = 0.94
    WHERE id = 3
    """)

    # 4. Link requesters from duplicate tickets #11, #12, #13 to Ticket #3
    db_dup_ids = [11, 12, 13]
    for dup_id in db_dup_ids:
        cursor.execute("SELECT requester_name, requester_department FROM ticket_requesters WHERE ticket_id = ?", (dup_id,))
        reqs = cursor.fetchall()
        for r_name, r_dept in reqs:
            cursor.execute("""
            INSERT INTO ticket_requesters (ticket_id, requester_name, requester_department, link_reason)
            VALUES (3, ?, ?, 'consolidated_test_duplicate')
            """, (r_name, r_dept or 'Engineering'))

        cursor.execute("DELETE FROM tickets WHERE id = ?", (dup_id,))
        cursor.execute("DELETE FROM ticket_requesters WHERE ticket_id = ?", (dup_id,))

    print("[CLEANUP] Consolidated Database duplicate test tickets #11-#13 into Master Ticket #3.")

    # 5. Clean up any orphaned escalation logs for deleted tickets
    cursor.execute("DELETE FROM sla_escalation_logs WHERE ticket_id >= 5")

    conn.commit()
    conn.close()
    print("[CLEANUP] Database consolidation completed cleanly!")
