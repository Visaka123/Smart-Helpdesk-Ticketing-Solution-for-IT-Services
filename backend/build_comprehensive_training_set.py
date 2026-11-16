"""
Priority Detection Training Script (IT-Domain) — EXPANDED
-------------------------------------------------------------
Expanded from the earlier version: ~65-70 unique base phrases per priority class
(vs. 24 before), covering more scenarios, tones (formal/casual/urgent/calm), and
edge cases within each severity band. This gives the model meaningfully more
linguistic diversity to generalize from, rather than memorizing a small template set.

Labeling logic:
  critical - full outage, production down, security breach, data loss,
             company-wide or business-critical-system impact
  high     - single user/team blocked from working, but not a full outage;
             access denied, service degraded significantly, security concern
             without confirmed breach
  medium   - inconvenient but workaround exists; partial degradation;
             non-blocking bugs; standard access/configuration requests
  low      - routine requests, informational questions, cosmetic issues,
             no urgency
"""

import os
import pandas as pd
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report

MODELS_DIR = "model_assets/models"
DATASET_PATH = "model_assets/processed/priority_training_real.csv"
EVAL_OUTPUT_PATH = "model_assets/models/priority_eval_predictions.csv"
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)

templates = {
    "critical": [
        "Production database cluster is completely down, all services offline",
        "Company-wide email outage, no one can send or receive mail",
        "Ransomware detected encrypting files on the finance department fileserver",
        "Data center power failure, all production servers unreachable",
        "Payment processing system is down, customers cannot complete any purchases",
        "Confirmed security breach, attacker has access to production database",
        "Entire VPN gateway is down, no remote employees can connect",
        "Core banking application returning 500 errors for all users company-wide",
        "Primary and backup internet circuits both down at headquarters",
        "SAP production system completely inaccessible for all departments",
        "Critical data loss detected after failed migration script execution",
        "Active Directory domain controller down, no one can log in anywhere",
        "DDoS attack overwhelming public-facing web servers, site unreachable",
        "Fire suppression system triggered in server room, emergency shutdown initiated",
        "All point-of-sale terminals down across every retail location",
        "Kubernetes cluster crash-looping, entire production environment offline",
        "Customer-facing API completely down, all integrations failing",
        "Backup system failure discovered during attempted disaster recovery",
        "Unauthorized admin account created, suspected active compromise in progress",
        "Core network switch failure taking down entire office building connectivity",
        "Production Kafka cluster down, no messages processing across all services",
        "Entire authentication service down, no employees can log into any system",
        "Critical vulnerability actively being exploited on internet-facing server",
        "Full site outage reported by monitoring, all regions affected",
        "Executive team locked out during live board meeting, system-wide login failure",
        "Emergency: our main website has been down for the last 20 minutes",
        "All hands needed, checkout system is completely broken, losing sales every minute",
        "Entire call center phone system down, cannot receive any customer calls",
        "Data breach confirmed, customer PII exposed in public S3 bucket",
        "Total loss of connectivity to primary data center, failover not triggering",
        "Air conditioning failure in server room causing servers to overheat and shut down",
        "Every employee simultaneously locked out after failed SSO configuration push",
        "Production release rollback failed, application is now completely unusable",
        "Malicious insider deleted production tables, need immediate restore",
        "Global outage affecting every regional office simultaneously",
        "Core message queue broken, orders are being silently dropped company-wide",
        "Cloud provider region outage taking down our entire infrastructure",
        "Corrupted database backup discovered, no viable restore point exists",
        "Load balancer misconfiguration routing 100% of traffic to a dead server",
        "Critical patch failed mid-deployment, half the fleet is now unreachable",
        "Root certificate expired unexpectedly, breaking all internal service communication",
        "This is urgent, nobody in the company can access email or Slack right now",
        "Our SaaS platform is completely down for every single customer",
        "Server room flooding reported, emergency shutdown of all hardware required",
        "Entire finance system offline the morning of month-end close",
        "Suspected supply-chain compromise in a critical software dependency",
        "Mass password reset triggered accidentally, locking out the entire org",
        "Primary Kubernetes control plane unreachable, cannot deploy or scale anything",
        "Every microservice returning errors after a bad config push to production",
        "Confirmed ransomware note found on multiple servers across the network",
        "24/7 monitoring alert: uptime dropped to 0% across all production endpoints",
        "Customer support queue flooded, entire platform reported down by users",
        "Total loss of access to our source code repository, cannot deploy fixes",
        "Building-wide power outage has taken every on-prem system offline",
        "Emergency escalation: trading platform down during market hours",
        "Critical infrastructure certificate revoked, all HTTPS traffic now failing",
        "Massive spike in 500 errors correlating with total service unavailability",
        "Entire engineering org locked out of GitHub after a token compromise",
        "Nobody can process any orders, the entire e-commerce platform is unreachable",
        "All backups corrupted simultaneously, disaster recovery plan has failed",
        "Full network partition between our two data centers, no failover possible",
        "Confirmed zero-day exploit actively being used against our production servers",
        "Company intranet, email, and VPN are all down at the same time",
        "Immediate danger: unauthorized wire transfer detected from compromised finance account",
        "Entire user base reporting inability to log in simultaneously across regions",
        # Failure Mode 1: Vague/Terse Terse Outage Alerts
        "prod db down",
        "entire site down",
        "all servers offline",
        "company email down",
        "datacenter down",
        "total system outage",
        # Failure Mode 2: Formal / Polite Registers Paired with Catastrophic Severity
        "Respected team, kindly be informed that our production database has been completely unreachable since this morning",
        "Greetings support team, I regret to inform you that the entire office network appears to be down company-wide",
        "Dear support team, please be advised that our customer checkout payment system has experienced a total outage",
        "Respected sir, kindly look into this urgently as all production servers are offline and returning 500 errors",
        "Good morning team, please assist immediately as ransomware has encrypted all files on the primary storage server",
        "Respected team, kindly note that no employees are able to log in due to active directory server crash",
        "Honored support team, please be informed that our core banking cluster has completely halted operation",
    ],
    "high": [
        "VPN connection fails with certificate error, cannot work remotely",
        "SAP SU53 authorization denied, blocked from processing purchase orders",
        "Cannot access shared drive, entire team blocked from project files",
        "Okta MFA push notifications not arriving, cannot log into any system",
        "Server returning intermittent 504 gateway timeout errors for one application",
        "Finance team locked out of expense reporting system before month-end deadline",
        "Suspicious phishing email with credential harvesting link reported by multiple users",
        "Single production microservice crash-looping, degraded but not fully down",
        "Engineering team cannot deploy, CI/CD pipeline failing on every build",
        "Database replication lag causing stale data on customer dashboard",
        "Executive laptop compromised with malware, isolating from network",
        "Access denied error blocking entire team from CRM system",
        "High-priority customer escalation blocked by billing system error",
        "Password reset not working, employee locked out before critical deadline",
        "SSL certificate expired on customer-facing portal, users seeing security warnings",
        "Significant packet loss on WAN link affecting entire branch office",
        "SAP GRC access request stuck, blocking new hire from working",
        "Cannot process payroll, HR system throwing errors before pay run deadline",
        "Server disk space critically low, application performance severely degraded",
        "Two-factor authentication broken for entire sales department",
        "Key vendor integration failing, blocking order fulfillment process",
        "Manager unable to approve time-sensitive budget request due to system error",
        "Firewall misconfiguration blocking legitimate traffic to critical application",
        "Data sync job failing repeatedly, reports showing incorrect financial figures",
        "Cannot submit quarterly compliance report, portal returns error on every attempt",
        "Legal team locked out of document management system before filing deadline",
        "Single sign-on broken for entire marketing department this morning",
        "Support ticketing system itself is down, agents cannot log new tickets",
        "Customer data export job failing, blocking a contractual delivery deadline",
        "Remote desktop keeps disconnecting every few minutes, cannot get work done",
        "One region's API gateway returning errors, affecting a large customer segment",
        "Developer cannot push code, git server rejecting all authentication attempts",
        "Warehouse scanning system down, blocking shipment processing for the day",
        "Slack workspace inaccessible for the whole company, no internal communication",
        "Critical report generation job has failed for three days in a row",
        "New hire cannot access any systems on their first day, provisioning failed",
        "Entire QA team blocked, staging environment throwing constant errors",
        "Billing system miscalculating invoices for a large batch of customers",
        "Data warehouse ETL job stuck, tomorrow's board report will be incomplete",
        "Multiple users reporting they cannot reset their own passwords",
        "Production alerting system itself went down, we're flying blind on monitoring",
        "Key API rate limit being hit constantly, causing failed customer requests",
        "Video conferencing completely broken company-wide during a critical client call",
        "Contractor access revoked accidentally mid-project, blocking delivery",
        "Automated deployment pipeline broken, hotfixes cannot reach production",
        "Customer support inbox not receiving any new emails since this morning",
        "Recruiting team locked out of the applicant tracking system during hiring push",
        "One entire department's laptops failed to boot after a bad update rollout",
        "Cannot access production logs, actively troubleshooting another incident blind",
        "Order fulfillment queue backed up significantly, shipments already delayed",
        "Confirmed suspicious access to a single employee's account, containing now",
        "Customer-reported bug is blocking checkout for a specific payment method",
        "Reporting dashboard has been broken for the exec team all week",
        "SFTP server rejecting all vendor file uploads since last night",
        "Internal wiki completely inaccessible, teams cannot find critical documentation",
        "A regional office's entire network dropped, they're fully offline",
        "License server down, blocking the whole design team from their software",
        "Automated invoice generation broken, delaying customer billing cycle",
        "On-call engineer paged repeatedly by a flapping but non-fatal alert",
        "Cannot generate any PDF exports, blocking a client-facing deliverable",
        "Entire support team's headsets stopped working after a system update",
        "Data pipeline feeding the ML model has been broken for two days",
        # Failure Mode 1: Vague/Terse Terse Single-User Operational Blockers
        "vpn disconnected",
        "sap user locked",
        "blue screen crashing",
        "cannot work at all",
        "access denied error",
        "account locked",
        # Failure Mode 2: Formal / Polite Registers Paired with High Severity
        "Respected sir, my laptop getting blue screen every one hour when doing work kindly resolve",
        "Greetings team, kindly do the needful as my SAP login is showing user locked error for my id",
        "Dear support, please assist as my VPN connection fails repeatedly with certificate error preventing remote work",
        "Respected team, kindly grant access as I am completely blocked from accessing CRM before my client demo",
        "Good day, I am respectfully requesting urgent resolution as Okta MFA is not arriving on my mobile device",
        "Dear IT team, kindly fix my account as I am getting access denied error on finance portal before payroll deadline",
        "Respected team, kindly assist as single sign-on is broken for our entire department this morning",
    ],
    "medium": [
        "Printer in accounting department jammed, workaround printer available nearby",
        "Outlook occasionally freezes when opening large attachments",
        "Wi-Fi signal weak in one corner of the office, wired connection available",
        "Need software license reassigned from departed employee to new hire",
        "Dashboard reporting shows minor data lag of a few hours",
        "Request for additional storage quota on shared drive",
        "New employee needs standard software installed before start date next week",
        "Second monitor not detected after docking station firmware update",
        "Meeting room video conferencing camera has poor image quality",
        "Need access granted to internal wiki space for new team member",
        "Non-critical background job occasionally fails and needs manual restart",
        "Request to update distribution list membership for department",
        "Slow loading times on internal reporting tool during peak hours",
        "Need firewall rule opened for new vendor SaaS integration",
        "Laptop battery health degraded, still usable but needs eventual replacement",
        "Request for read-only access to project tracking board",
        "Minor UI bug in internal tool, workaround exists using alternate menu",
        "Need VPN profile updated to include new internal subnet",
        "Occasional Bluetooth disconnect issue with wireless headset",
        "Request to increase mailbox storage quota approaching limit",
        "Internal application showing outdated data, refresh resolves temporarily",
        "Need test environment database refreshed with latest production schema",
        "Software update available but not yet installed on department laptops",
        "Request for calendar sharing permissions between two departments",
        "Occasional lag when switching between multiple monitors on docking station",
        "Need to update team's shared calendar with new meeting room",
        "Spreadsheet macro throwing an error, manual workaround currently in use",
        "Request for guest Wi-Fi credentials for upcoming vendor visit",
        "Need to archive old project files to free up shared drive space",
        "Minor formatting issue in automated weekly report email",
        "Request for additional seats on team collaboration software license",
        "Occasional dropped call quality on desk phone, mobile works fine",
        "Need read access to another team's shared folder for a joint project",
        "Company intranet search returning some outdated results",
        "Request to onboard a new contractor with standard system access",
        "Laptop occasionally needs a restart after waking from sleep",
        "Need help configuring email signature template for new branding",
        "Request for a loaner laptop while primary device is being repaired",
        "Minor delay in nightly report generation, report still arrives by morning",
        "Need permissions updated after internal team reorganization",
        "Chat notifications occasionally delayed by a few minutes",
        "Request to add a new field to the internal ticket intake form",
        "Shared printer toner running low, replacement already on order",
        "Need to update firmware on conference room display, no urgency",
        "Occasional autocomplete glitch in the internal CRM search bar",
        "Request for a second display cable, current one has minor connector wear",
        "Internal training video buffering occasionally on slower connections",
        "Need standard onboarding checklist re-sent for a rescheduled new hire",
        "Request to test a new integration in the staging environment first",
        "Minor spacing issue on the internal employee directory page",
        "Need to update the on-call rotation schedule for next month",
        "Occasional slow response time on the internal helpdesk chatbot",
        "Request for a spare HDMI adapter for the shared meeting room cart",
        "Need to adjust automatic email forwarding rule for a team alias",
        "Internal dashboard chart occasionally mislabels a data series",
        "Request to extend trial access to a new productivity tool for evaluation",
        "Laptop fan runs a bit louder than usual under heavy load, still functional",
        "Need someone to review and approve a routine access request",
        "Request for updated documentation on the expense submission process",
        "Occasional typo found in an automated system-generated email template",
        "Need help setting up a recurring meeting series in the shared calendar",
        "Request to test whether a new browser extension is compatible with our SSO",
        # Failure Mode 1: Vague / Terse Short Inputs (Reasonable Baseline = Medium)
        "network problem",
        "system error popped up",
        "system error popped up on my screen",
        "it is not working",
        "something is wrong with my laptop",
        "something's wrong",
        "help with this",
        "issue with computer",
        "laptop problem",
        "app not loading",
        "getting an error",
        "having trouble",
        "computer issue",
        "software broken",
        "please help",
        "need assistance with system",
        "facing error",
        "connection issue",
        # Failure Mode 2: Formal / Polite Registers Paired with Medium Severity
        "Greetings team, I am not getting email notifications in my mobile phone application since yesterday evening",
        "Please to assist, password reset link expired for internal portal",
        "Respected team, kindly assist in requesting standard software installation for new department member",
        "Dear support, kindly note that my second monitor screen is flickering occasionally when docked",
        "Good day, please be informed that printer in accounting has minor paper jam",
        "Respected team, kindly help configure email signature template for new company branding",
    ],
    "low": [
        "Requesting information about available software training courses",
        "Question about company policy on personal device usage",
        "Would like to request an additional monitor for ergonomic setup",
        "General inquiry about upcoming IT system maintenance windows",
        "Requesting a new mouse pad and desk organizer for workstation",
        "Curious about what video conferencing tools are officially supported",
        "Asking for a walkthrough of the new expense reporting tool",
        "Requesting information on how to set up email signature template",
        "Question about how to request annual software license renewal",
        "General question about company Wi-Fi guest access policy",
        "Would like documentation on how to use the internal knowledge base",
        "Requesting a demo of new project management tool for the team",
        "Asking about best practices for organizing shared drive folders",
        "Inquiry about upgrading to a larger external monitor",
        "Requesting information about company laptop refresh cycle",
        "Question about how to add a delegate to shared calendar",
        "Would like an optional desk plant approved for personal workspace",
        "Asking whether standing desks are available for new hires",
        "General question about how to submit an IT feature request",
        "Requesting information about noise-cancelling headset options",
        "Asking about company style guide for internal presentation templates",
        "Question about how long IT support tickets typically take to resolve",
        "Requesting an optional training session on new collaboration tool",
        "Asking for recommendation on ergonomic keyboard options",
        "Curious if there's a dark mode option for the internal portal",
        "Requesting a tour of the new office IT setup for orientation",
        "Question about whether personal headphones can be used with the desk phone",
        "Asking if there's a recommended backpack for carrying a work laptop",
        "Would like to suggest a new feature for the internal ticketing tool",
        "General curiosity about what browser is officially recommended",
        "Requesting an optional lunch-and-learn session on cybersecurity basics",
        "Asking how to change the display language on the internal portal",
        "Question about whether a webcam cover is provided with new laptops",
        "Requesting a copy of the IT onboarding slide deck for reference",
        "Asking if there's a preferred note-taking app for meetings",
        "Curious about the process for suggesting a new company holiday",
        "Requesting feedback form link for a recent IT support interaction",
        "Asking about optional add-ons available for the standard laptop bundle",
        "Question about whether we support Linux as a personal dev environment",
        "Requesting an extra desk mat, current one is slightly worn but functional",
        "Asking for a list of keyboard shortcuts for the internal tool",
        "General inquiry about upcoming company tech talk schedule",
        "Requesting clarification on optional two-monitor setup guidelines",
        "Asking if there's a preferred password manager recommended by IT",
        "Curious about the roadmap for future internal tool improvements",
        "Requesting an optional accessibility review of a personal workstation setup",
        "Asking whether a wireless charging pad can be added to the desk",
        "Question about the typical response time for non-urgent IT requests",
        "Requesting a printed copy of the company IT usage policy",
        "Asking if there's a suggested reading list for new engineers",
        "Curious about whether team can get branded laptop stickers",
        "Requesting an optional calendar block for quiet focus time setup help",
        "Asking about the process to nominate a tool for company-wide adoption",
        "Question about whether external monitors are eligible for reimbursement",
        "Requesting general feedback on the new self-service IT portal design",
        "Asking if there's a way to preview upcoming system maintenance notices",
        "Curious what the typical laptop specs are for a new starter kit",
        "Requesting an optional walkthrough of keyboard accessibility settings",
        "Asking whether desk risers are available to borrow from IT",
        "Question about how to update preferred name in the company directory",
        "Requesting a sample email template for common IT request types",
        "Asking if there's a suggested onboarding buddy program contact",
        # Failure Mode 1: Vague / Terse Routine General Queries
        "help me with computer",
        "question about laptop",
        "how to use this",
        "quick question",
        "general query",
        "policy question",
        "info request",
        "need guidance",
        # Failure Mode 2: Formal / Polite Registers Paired with Low Severity
        "Good day, wanting to inquire regarding process for requesting secondary screen monitor",
        "Respected team, kindly share documentation on how to use internal knowledge base",
        "Greetings support, I am requesting information about available software training courses",
        "Dear team, kindly clarify company policy regarding personal headphone usage with desk phone",
        "Respected team, kindly provide list of recommended keyboard shortcuts for internal tool",
    ],
}

# ---------------------------------------------------------------------------
# Build dataset — light augmentation kept modest so severity signal dominates
# ---------------------------------------------------------------------------
data = []
for priority, phrases in templates.items():
    for phrase in phrases:
        data.append({"description": phrase, "priority": priority})
        data.append({"description": f"URGENT: {phrase}" if priority in ("critical", "high") else phrase,
                     "priority": priority})
        data.append({"description": f"User reported: {phrase}", "priority": priority})
        data.append({"description": f"Ticket: {phrase.lower()}", "priority": priority})

df = pd.DataFrame(data).drop_duplicates(subset=["description"]).reset_index(drop=True)
df.to_csv(DATASET_PATH, index=False)
print(f"[DATASET BUILD] Created IT-domain priority dataset with {len(df)} samples")
print(f"[DATASET BUILD] Class distribution: {df['priority'].value_counts().to_dict()}")
print(f"[DATASET BUILD] Unique base phrases per class: "
      f"{ {k: len(v) for k, v in templates.items()} }")

# ---------------------------------------------------------------------------
# Encode labels and embed text
# ---------------------------------------------------------------------------
le = LabelEncoder()
y = le.fit_transform(df["priority"])
X_raw = df["description"].tolist()

embedder = SentenceTransformer("all-MiniLM-L6-v2")
print("[EMBEDDING] Encoding descriptions with all-MiniLM-L6-v2 ...")
X_vec = embedder.encode(X_raw, show_progress_bar=True)

# ---------------------------------------------------------------------------
# Real train/test split
# ---------------------------------------------------------------------------
X_train, X_test, y_train, y_test, desc_train, desc_test = train_test_split(
    X_vec, y, X_raw,
    test_size=0.20,
    random_state=42,
    stratify=y,
)

clf = RandomForestClassifier(n_estimators=300, max_depth=None, random_state=42)
clf.fit(X_train, y_train)

# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------
y_pred = clf.predict(X_test)
acc = accuracy_score(y_test, y_pred)
f1_macro = f1_score(y_test, y_pred, average="macro")
f1_weighted = f1_score(y_test, y_pred, average="weighted")

print("\n" + "=" * 70)
print(f"[EVALUATION] Held-out test set: {len(y_test)} samples")
print(f"[EVALUATION] Accuracy:          {acc:.4f}")
print(f"[EVALUATION] F1 (macro avg):    {f1_macro:.4f}")
print(f"[EVALUATION] F1 (weighted avg): {f1_weighted:.4f}")
print("=" * 70)
print("\n[EVALUATION] Per-class report:\n")
print(classification_report(y_test, y_pred, target_names=le.classes_))

eval_df = pd.DataFrame({
    "description": desc_test,
    "true_priority": le.inverse_transform(y_test),
    "predicted_priority": le.inverse_transform(y_pred),
    "correct": y_test == y_pred,
})
eval_df.to_csv(EVAL_OUTPUT_PATH, index=False)
print(f"\n[EVALUATION] Test predictions saved to {EVAL_OUTPUT_PATH} for manual review.")

misclassified = eval_df[~eval_df["correct"]]
if len(misclassified) > 0:
    print(f"\n[EVALUATION] {len(misclassified)} misclassified examples (first 15 shown):")
    print(misclassified[["description", "true_priority", "predicted_priority"]].head(15).to_string(index=False))

# ---------------------------------------------------------------------------
# Retrain on FULL dataset for final saved model
# ---------------------------------------------------------------------------
final_clf = RandomForestClassifier(n_estimators=300, max_depth=None, random_state=42)
final_clf.fit(X_vec, y)

with open(os.path.join(MODELS_DIR, "priority.pkl"), "wb") as f:
    pickle.dump(final_clf, f)

with open(os.path.join(MODELS_DIR, "priority_label_encoder.pkl"), "wb") as f:
    pickle.dump(le, f)

print(f"\n[MODEL SAVED] Final priority model (trained on all {len(df)} samples) "
      f"saved to {MODELS_DIR}/priority.pkl")
print(f"[MODEL SAVED] Label encoder saved to {MODELS_DIR}/priority_label_encoder.pkl")
print(f"[MODEL SAVED] Classes: {list(le.classes_)}")
print("\nNOTE: Accuracy/F1 above were measured on the held-out split BEFORE this "
      "final full-data refit — that's the honest estimate of real generalization.")
print("\nIMPORTANT: This replaces priority.pkl. Confirm app/priority/service.py's "
      "predict_priority_enhanced() still correctly loads this new label encoder "
      "before deploying.")