import os
import pandas as pd
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score

MODELS_DIR = "model_assets/models"
DATASET_PATH = "model_assets/processed/training_real.csv"
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)

# Domain-specific template variations for enterprise teams
templates = {
    "SAP Team": [
        "SAP Transaction SU53 Permission Error when creating purchase orders",
        "Getting ME21N permission denied screenshot on SAP SU53 screen",
        "SAP ERP Transaction SU53 Authorization Denied for user profile",
        "SAP GUI crash on startup with T-code VA01 execution failure",
        "SAP GRC role Z_SAP_SU53_ACCESS missing authorization object S_TCODE",
        "User locked out of SAP Production system with invalid password error",
        "Unable to release PO in SAP MM module due to missing authorization",
        "SAP Finance module error posting GL account line item",
        "SAP logon pad error connection to message server failed",
        "Transaction SU53 shows authorization check failed for object S_TABU_DIS",
    ],
    "Network Team": [
        "VPN Connection Fails with Certificate Error when working remotely",
        "Cisco AnyConnect VPN disconnected repeatedly with posture check fail",
        "Wi-Fi connection drops in 3rd floor office conference room",
        "Ethernet port in desk 4B has no internet connection",
        "DNS resolution failure when pinging internal server address",
        "Firewall blocking outgoing HTTPS traffic to cloud API endpoint",
        "High network latency and packet loss on corporate WAN gateway",
        "GlobalProtect VPN client unable to connect to secondary gateway",
        "Corporate Wi-Fi SSID asking for certificate re-authentication",
        "VPN split tunneling configuration issue on macOS client",
    ],
    "Database Team": [
        "Database Connection Timeout on MySQL Production Cluster",
        "Cluster Database Failover primary node unreachable in datacenter",
        "PostgreSQL query execution time exceeded 30 second limit",
        "MongoDB replica set secondary node out of sync with primary",
        "Database deadlocks reported on transaction table during peak load",
        "High CPU utilization on RDS MySQL instance due to unindexed query",
        "Database backup script failed with disk full error on /var/lib/mysql",
        "Connection pool exhausted on Spring Boot service to Postgres DB",
        "Redis cluster node failover triggered automatically",
        "Database migration script failed on migration version V4.2",
    ],
    "Security Team": [
        "Okta 2FA push notification not arriving on mobile device",
        "Phishing email report suspicious attachment received from external sender",
        "Malware alert triggered on Windows workstation endpoint protection",
        "SSL certificate expired on internal portal web app",
        "SSO login failure with SAML assertion signature mismatch",
        "Security vulnerability scan flagged open port 22 on staging server",
        "User account locked after 5 failed password attempts in Active Directory",
        "Request for elevated sudo administrative privileges on Linux server",
        "USB drive blocked by endpoint security policy on corporate laptop",
        "BitLocker recovery key needed to boot Windows laptop",
    ],
    "IT Support": [
        "Outlook Desktop Client Keeps Prompting for Password every 10 minutes",
        "Laptop screen flickering and turning black randomly",
        "Wireless mouse and keyboard not connecting to USB dongle",
        "Dual monitor display not recognized after Windows update",
        "Office printer paper jam and offline status in department bay",
        "Microphone and camera not working in Teams video meeting",
        "Blue Screen of Death (BSOD) crash code CRITICAL_PROCESS_DIED",
        "MacBook Pro battery draining rapidly and overheating",
        "Request for new monitor stand and ergonomic keyboard",
        "Clear cache and cookies instruction needed for Chrome browser",
    ],
    "HR Support": [
        "Workday payroll direct deposit bank account change request",
        "Annual leave timeoff balance incorrect in HR portal",
        "Payslip tax withholding breakdown inquiry for current month",
        "Onboarding checklist access needed for new hire starting Monday",
        "Health insurance benefit enrollment status confirmation",
        "Request for employment verification letter for mortgage application",
        "Performance review self-assessment submission form error",
        "Commuter benefit card balance not updated after payroll deduction",
        "Maternity leave policy document and application procedure",
        "Internal job transfer application status update request",
    ],
    "Billing & Payments": [
        "Invoice payment failed on Stripe checkout portal",
        "Corporate credit card charged twice for software subscription",
        "Vendor invoice approval status inquiry for PO #94821",
        "Request for VAT tax invoice download for quarterly expense report",
        "Refund status update for cancelled SaaS service license",
        "Billing address update needed on corporate AWS master account",
        "Payment gateway API returning 402 Payment Required error",
        "Wire transfer confirmation receipt requested by supplier",
        "Annual subscription renewal discount quote request",
        "Billing contact email update for enterprise account statements",
    ],
}

data = []
# Generate 100 augmented sentences per team
for team, phrases in templates.items():
    for phrase in phrases:
        data.append({"description": phrase, "assigned_team": team})
        # Simple variations
        data.append({"description": f"URGENT: {phrase}", "assigned_team": team})
        data.append({"description": f"User reported: {phrase}", "assigned_team": team})
        data.append({"description": f"Help needed with {phrase.lower()}", "assigned_team": team})
        data.append({"description": f"Ticket regarding {phrase.lower()} on corporate system", "assigned_team": team})

df = pd.DataFrame(data)
df.to_csv(DATASET_PATH, index=False)
print(f"[DATASET BUILD] Created synthetic enterprise dataset with {len(df)} samples across {df['assigned_team'].nunique()} teams.")

# Train ML router
le = LabelEncoder()
y = le.fit_transform(df["assigned_team"])
X_raw = df["description"].tolist()

embedder = SentenceTransformer("all-MiniLM-L6-v2")
X_vec = embedder.encode(X_raw, show_progress_bar=False)

clf = LogisticRegression(max_iter=3000, C=2.0, random_state=42)
clf.fit(X_vec, y)

# Save artifacts
with open(os.path.join(MODELS_DIR, "router.pkl"), "wb") as f:
    pickle.dump(clf, f)

with open(os.path.join(MODELS_DIR, "label_encoder.pkl"), "wb") as f:
    pickle.dump(le, f)

print(f"[MODEL RETRAINED] Router model trained on {len(df)} samples across classes: {le.classes_}")
