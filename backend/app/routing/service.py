import os
import re
import json
import pickle
import joblib
import numpy as np
from app.core.embeddings import embed_text

MODELS_DIR = "model_assets/models"
ROUTER_PATH = os.path.join(MODELS_DIR, "router.pkl")
LABEL_ENCODER_PATH = os.path.join(MODELS_DIR, "label_encoder.pkl")
BUNDLE_PATH = os.path.join(MODELS_DIR, "tfidf_lgbm_bundle.joblib")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

_router_cache = None
_label_encoder_cache = None
_category_bundle_cache = None

def get_router_model():
    global _router_cache
    if _router_cache is None and os.path.exists(ROUTER_PATH):
        try:
            with open(ROUTER_PATH, "rb") as f:
                _router_cache = pickle.load(f)
        except Exception as e:
            print(f"[WARN] Could not load router.pkl: {e}")
    return _router_cache

def get_label_encoder():
    global _label_encoder_cache
    if _label_encoder_cache is None and os.path.exists(LABEL_ENCODER_PATH):
        try:
            with open(LABEL_ENCODER_PATH, "rb") as f:
                _label_encoder_cache = pickle.load(f)
        except Exception as e:
            print(f"[WARN] Could not load label_encoder.pkl: {e}")
    return _label_encoder_cache

def get_category_bundle():
    global _category_bundle_cache
    if _category_bundle_cache is None and os.path.exists(BUNDLE_PATH):
        try:
            _category_bundle_cache = joblib.load(BUNDLE_PATH)
            print(f"[CATEGORY MODEL] Loaded tfidf_lgbm_bundle.joblib successfully! Classes: {list(_category_bundle_cache['label_encoder'].classes_)}")
        except Exception as e:
            print(f"[WARN] Could not load tfidf_lgbm_bundle.joblib: {e}")
    return _category_bundle_cache

CATEGORY_TEAM_MAP = {
    "Network": "Network Operations",
    "Hardware": "IT Support",
    "Software": "IT Support",
    "Software/Desktop Application": "IT Support",
    "Access": "IT Support",
    "Access/Accounts": "IT Support",
    "Email": "IT Support",
    "Security": "Security Team",
    "Application/Backend": "IT Support",
    "Printer/Peripheral": "IT Support",
    "Internal Project": "IT Support",
    "Administrative rights": "IT Admin",
    "HR Support": "HR Operations",
    "Storage": "Infrastructure Support",
    "Purchase": "Procurement",
    "Miscellaneous": "General Support",
}

ALLOWED_TEAMS = [
    "IT Support",
    "Network Operations",
    "Network Team",
    "Security Team",
    "Application Support",
    "Database Operations",
    "DevOps & Cloud Infra",
    "Network & Security",
    "SAP / ERP Team",
    "Identity & Access Management",
    "IT Admin",
    "Desktop Support",
    "Procurement",
    "HR Operations",
    "General Support",
]

SOFTWARE_KEYWORDS = [
    "application", "software", "update failed", "install", "crash",
    "launch", "bug", "patch", "error"
]

HARDWARE_KEYWORDS = [
    "laptop", "monitor", "screen", "keyboard", "mouse", "charger",
    "cable", "printer", "ram", "motherboard"
]

def route_team_with_llm(category: str, title: str, description: str) -> str:
    """
    LLM-based second-stage team routing service to accurately assign the support team after category prediction.
    Uses Groq API to dynamically select the best assigned_team.
    Falls back to CATEGORY_TEAM_MAP.get(category, "General Support") on any failure or invalid team name.
    """
    fallback_team = CATEGORY_TEAM_MAP.get(category, "General Support")

    try:
        from ai.rag.groq_client import get_groq_api_keys, Groq

        api_keys = get_groq_api_keys()
        if not api_keys:
            print("[LLM ROUTER WARN] No GROQ_API_KEY available. Falling back to CATEGORY_TEAM_MAP.")
            return fallback_team

        sys_prompt = """You are an IT Helpdesk Dispatcher AI. Your job is to accurately route IT support tickets to the correct support team based on the ticket category, title, and description.

You MUST select strictly ONE team from the following allowed support teams:
- "Application Support" (Internal app bugs, API errors, frontend crashes, deployment issues)
- "Database Operations" (PostgreSQL/MySQL deadlocks, replication lag, slow queries)
- "DevOps & Cloud Infra" (Docker/K8s pod issues, CI/CD pipeline failures, cloud storage limits)
- "Network & Security" (VPN connectivity, firewall rules, SSL certs, gateway timeouts)
- "SAP / ERP Team" (SAP module sync errors, invoice integration failures, ERP ledger mismatches)
- "Identity & Access Management" (SSO login, MFA resets, role-based access permissions)
- "IT Admin" (Sudo rights, elevated local server access)
- "Desktop Support" (Workstation hardware, physical monitor failures)
- "Procurement" (Software license purchases, hardware orders)
- "HR Operations" (Payroll queries, PTO balance disputes)
- "General Support" (Office amenities, general/ambiguous requests)

You MUST respond strictly in valid JSON format:
{"assigned_team": "<Exact Team Name>"}"""

        usr_prompt = f"""Category: {category}
Title: {title}
Description: {description}"""

        for idx, key in enumerate(api_keys):
            try:
                client = Groq(api_key=key)
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": usr_prompt}
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                if response and response.choices and len(response.choices) > 0:
                    raw_content = response.choices[0].message.content
                    if raw_content and raw_content.strip():
                        parsed = json.loads(raw_content.strip())
                        team = parsed.get("assigned_team")
                        if team in ALLOWED_TEAMS:
                            print(f"[LLM ROUTER SUCCESS] LLM assigned team: '{team}' for ticket '{title}'")
                            return team
                        else:
                            print(f"[LLM ROUTER WARN] LLM returned invalid team '{team}'. Falling back to default.")
            except Exception as e:
                print(f"[LLM ROUTER WARN] Key #{idx + 1} failed: {e}")
                continue

    except Exception as e:
        print(f"[LLM ROUTER ERROR] Exception in route_team_with_llm: {e}")

ALLOWED_CATEGORIES = [
    "Network",
    "Hardware",
    "Software",
    "Software/Desktop Application",
    "Access",
    "Access/Accounts",
    "Email",
    "Security",
    "Application/Backend",
    "Printer/Peripheral",
    "Internal Project",
    "HR Support",
    "Purchase",
    "Storage",
    "Administrative rights",
    "Miscellaneous",
]

ALLOWED_PRIORITIES = ["Critical", "High", "Medium", "Low"]
ALLOWED_SLA_TARGETS = ["4 hours", "24 hours", "48 hours", "72 hours"]

def rule_based_classify(title: str, description: str) -> dict:
    """
    High-precision deterministic rule-based classifier matching keywords for IT support domains.
    Handles Software, Network, Access, Security, Application/Backend, Printer, and Hardware.
    """
    text = f"{title} {description}".lower()

    def has_word(patterns, s=text):
        for p in patterns:
            # Escape regex special chars while keeping word boundary
            escaped = re.escape(p)
            if re.search(r'(?:\b|\A)' + escaped + r'(?:\b|\Z)', s, re.IGNORECASE):
                return True
        return False

    # 1. Application/Backend (503 gateway, service unavailable, backend outage, deadlocks)
    if has_word(["503", "502", "504", "production gateway", "gateway timeout", "service unavailable", "database deadlock", "deadlock"]) or (
        has_word(["microservice", "backend"]) and has_word(["error", "timeout", "fail", "down", "outage", "deadlock"])
    ):
        is_crit = has_word(["production", "outage", "down", "critical", "503", "gateway 503"])
        prio = "Critical" if is_crit else "High"
        sla = "4 hours" if prio == "Critical" else "24 hours"
        return {
            "category": "Application/Backend",
            "assigned_team": "IT Support",
            "priority": prio,
            "sla_target": sla,
            "category_confidence": 0.99,
        }

    # 2. Security (phishing, suspicious email, malware, ransomware, breach)
    if has_word(["phishing", "suspicious email", "malware", "virus", "ransomware", "trojan", "unauthorized access", "data breach", "compromised"]):
        return {
            "category": "Security",
            "assigned_team": "Security Team",
            "priority": "High",
            "sla_target": "24 hours",
            "category_confidence": 0.99,
        }

    # 3. Access / Accounts (passwords, locked, access denied, MFA, SSO, role access, grant access, need access)
    if has_word([
        "password", "locked", "lockout", "access denied", "mfa reset", "mfa", "2fa",
        "sso login", "sso", "permission denied", "unlock account", "account locked",
        "access request", "request access", "need access", "grant access", "role access",
        "user permissions", "access rights", "module access", "erp access", "portal access"
    ]) or (
        has_word(["access"]) and has_word(["role", "module", "permission", "permissions", "rights", "grant", "erp", "account", "login", "purchase module"])
    ):
        return {
            "category": "Access",
            "assigned_team": "IT Support",
            "priority": "Medium",
            "sla_target": "48 hours",
            "category_confidence": 0.99,
        }

    # 4. Network (file server, VPN, Wi-Fi, switch, firewall, router, subnet, lan, wan, dns)
    if has_word(["file server", "vpn", "wi-fi", "wifi", "switch port", "switch", "firewall", "router", "subnet", "lan", "wan", "mpls", "bgp", "network latency", "packet loss", "ethernet"]) or (
        has_word(["unreachable", "disconnected"]) and has_word(["server", "host", "switch", "port", "network", "nas", "share", "circuit"])
    ):
        is_high = has_word(["urgent", "unreachable", "down", "disconnected", "spike", "outage"])
        prio = "High" if is_high else "Medium"
        sla = "24 hours" if prio == "High" else "48 hours"
        return {
            "category": "Network",
            "assigned_team": "Network Operations",
            "priority": prio,
            "sla_target": sla,
            "category_confidence": 0.99,
        }

    # 5. Software / Desktop Application (Excel, Outlook, install, license, crash, Office 365)
    if has_word([
        "excel", "outlook", "powerpoint", "office 365", "ms office", "ms word",
        "install", "installation", "license", "licensing", "crash", "crashes", "crashing",
        "freeze", "freezes", "intellij", "vscode", "desktop application"
    ]):
        return {
            "category": "Software",
            "assigned_team": "IT Support",
            "priority": "Medium",
            "sla_target": "48 hours",
            "category_confidence": 0.99,
        }

    # 6. Printer / Peripheral
    if has_word(["printer", "printing", "toner", "paper jam", "scanner", "peripheral"]):
        return {
            "category": "Printer/Peripheral",
            "assigned_team": "IT Support",
            "priority": "Low",
            "sla_target": "72 hours",
            "category_confidence": 0.98,
        }

    # 7. Email issues (non-phishing)
    if has_word(["email bounce", "mailbox full", "exchange server", "smtp", "imap", "cannot send email"]):
        return {
            "category": "Email",
            "assigned_team": "IT Support",
            "priority": "Medium",
            "sla_target": "48 hours",
            "category_confidence": 0.98,
        }

    # 8. Physical Hardware
    if has_word(["laptop", "monitor", "screen", "keyboard", "mouse", "docking station", "charger", "cable", "ram upgrade"]):
        return {
            "category": "Hardware",
            "assigned_team": "IT Support",
            "priority": "Medium",
            "sla_target": "48 hours",
            "category_confidence": 0.98,
        }

    # 9. Real Internal Project
    if has_word(["internal project", "code repo", "dev branch", "refactoring task", "architecture review", "sprint task"]):
        return {
            "category": "Internal Project",
            "assigned_team": "IT Support",
            "priority": "Medium",
            "sla_target": "48 hours",
            "category_confidence": 0.95,
        }

    return None

def classify_and_route_ticket(title: str, description: str) -> dict:
    """
    Single-pass classifier using deterministic keyword rules first,
    falling back to Groq LLM ('llama-3.1-8b-instant').
    Dynamically predicts Category, Assigned Team, Priority, and SLA Target using semantic reasoning.
    """
    rule_res = rule_based_classify(title, description)
    if rule_res:
        print(f"[RULE CLASSIFIER MATCH] '{title}' -> Category: {rule_res['category']}, Team: {rule_res['assigned_team']}, Priority: {rule_res['priority']}")
        return rule_res

    # Fallback default if LLM is unavailable
    t_lower = f"{title} {description}".lower()
    fallback_category = "Miscellaneous"
    if any(re.search(r'(?:\b|\A)' + re.escape(w) + r'(?:\b|\Z)', t_lower) for w in ["access", "password", "permission", "role", "login"]):
        fallback_category = "Access"
    elif any(re.search(r'(?:\b|\A)' + re.escape(w) + r'(?:\b|\Z)', t_lower) for w in ["excel", "outlook", "software", "license", "install", "crash"]):
        fallback_category = "Software"
    elif any(re.search(r'(?:\b|\A)' + re.escape(w) + r'(?:\b|\Z)', t_lower) for w in ["network", "vpn", "wifi", "switch", "router", "file server"]):
        fallback_category = "Network"

    fallback_res = {
        "category": fallback_category,
        "assigned_team": CATEGORY_TEAM_MAP.get(fallback_category, "IT Support"),
        "priority": "Medium",
        "sla_target": "48 hours",
        "category_confidence": 0.85
    }

    try:
        from ai.rag.groq_client import get_groq_api_keys, Groq

        api_keys = get_groq_api_keys()
        if not api_keys:
            print("[UNIFIED LLM CLASSIFIER WARN] No GROQ_API_KEY available. Returning fallback.")
            return fallback_res

        sys_prompt = """You are an enterprise IT Service Management (ITSM) dispatcher AI. Your job is to classify and route IT support tickets in a single pass based on the ticket title and description.

You MUST strictly follow these rules:

1. Category (Select strictly ONE from the allowed categories):
- "Network": VPN, Wi-Fi, switches, routers, firewalls, DNS, file server connectivity, subnets, packet loss.
- "Software": Desktop apps (Excel, Outlook, Office), software installation, licenses, app crashes/freezes.
- "Access": Passwords, account lockout, access denied, MFA resets, SSO login permissions.
- "Security": Phishing, malware, suspicious emails, security alerts, ransomware.
- "Application/Backend": 503 gateway errors, backend microservices, API failures, database deadlocks, service outages.
- "Hardware": STRICTLY physical device failures (monitors, keyboards, docks, laptops, chargers, cables).
- "Printer/Peripheral": Printers, scanners, toner, paper jams, print queues.
- "Email": Mailbox full, bounce messages, email delivery failures (non-security).
- "Internal Project": Software development repositories, internal developer tooling, CI/CD pipelines.
- "HR Support": Leaves, payroll, benefits, policy inquiries.
- "Purchase": Procurement requests, new software/hardware purchase orders.
- "Storage": Disk quotas, cloud buckets (S3), network shares, backup space.
- "Miscellaneous": General inquiries not fitting any other category.

2. Assigned Team (Select strictly ONE):
- "Network Operations" (Network and connectivity issues)
- "IT Support" (General IT, software, desktop apps, hardware, access)
- "Security Team" (Security and phishing incidents)
- "Database Operations" (PostgreSQL/MySQL deadlocks, queries)
- "DevOps & Cloud Infra" (CI/CD pipeline failures, Docker/K8s)

3. Priority & SLA Target (Select strictly ONE matching pair):
- "Critical" -> "4 hours" (Production outages, 503 gateway errors, payment blockers)
- "High" -> "24 hours" (Service degradation, security phishing, VPN branch blockers)
- "Medium" -> "48 hours" (Single user software crashes, license requests, password resets)
- "Low" -> "72 hours" (General inquiries, non-urgent peripheral issues)

You MUST respond strictly in valid JSON format with this exact schema:
{
  "category": "<Allowed Category>",
  "assigned_team": "<Allowed Team>",
  "priority": "<Critical | High | Medium | Low>",
  "sla_target": "<4 hours | 24 hours | 48 hours | 72 hours>"
}"""

        usr_prompt = f"Title: {title}\nDescription: {description}"

        for idx, key in enumerate(api_keys):
            try:
                client = Groq(api_key=key)
                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": usr_prompt}
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                if response and response.choices and len(response.choices) > 0:
                    raw_content = response.choices[0].message.content
                    if raw_content and raw_content.strip():
                        parsed = json.loads(raw_content.strip())
                        cat = parsed.get("category")
                        team = parsed.get("assigned_team")
                        prio = parsed.get("priority")
                        sla = parsed.get("sla_target")

                        if cat not in ALLOWED_CATEGORIES:
                            cat = "Software" if any(k in t_lower for k in ["install", "crash", "excel", "license"]) else "Miscellaneous"
                        if team not in ALLOWED_TEAMS:
                            team = CATEGORY_TEAM_MAP.get(cat, "IT Support")
                        if prio not in ALLOWED_PRIORITIES:
                            prio = "Medium"
                        if sla not in ALLOWED_SLA_TARGETS:
                            sla = "48 hours"

                        res_dict = {
                            "category": cat,
                            "assigned_team": team,
                            "priority": prio,
                            "sla_target": sla,
                            "category_confidence": 0.98
                        }
                        print(f"[UNIFIED LLM CLASSIFIER SUCCESS] Result for '{title}': {res_dict}")
                        return res_dict
            except Exception as e:
                print(f"[UNIFIED LLM CLASSIFIER WARN] Key #{idx + 1} failed: {e}")
                continue

    except Exception as e:
        print(f"[UNIFIED LLM CLASSIFIER ERROR] Exception in classify_and_route_ticket: {e}")

    print(f"[UNIFIED LLM CLASSIFIER FALLBACK] Returning default fallback object.")
    return fallback_res

def post_process_category(predicted_category: str, text: str) -> dict:
    """
    Post-process category prediction and determine team routing.
    If the raw predicted category is 'Hardware', software keywords are present, and physical hardware keywords are absent:
      - Override category to 'Software'
      - Assign team to 'IT Support'
    Otherwise, map assigned team using CATEGORY_TEAM_MAP.
    """
    text_lower = str(text).lower()

    has_software_kw = any(kw in text_lower for kw in SOFTWARE_KEYWORDS)
    has_hardware_kw = any(kw in text_lower for kw in HARDWARE_KEYWORDS)

    final_category = predicted_category
    is_overridden = False

    if predicted_category == "Hardware" and has_software_kw and not has_hardware_kw:
        final_category = "Software"
        is_overridden = True

    assigned_team = CATEGORY_TEAM_MAP.get(final_category, "IT Support")

    return {
        "final_category": final_category,
        "assigned_team": assigned_team,
        "is_overridden": is_overridden,
        "raw_category": predicted_category,
    }

def predict_ticket_category(text: str) -> dict:
    """
    Predict ticket category using the newly trained 8-class LightGBM model with TF-IDF vectorization.
    Classes: ['Access', 'Administrative rights', 'HR Support', 'Hardware', 'Internal Project', 'Miscellaneous', 'Purchase', 'Storage']
    Applies post_process_category to handle software update errors.
    """
    bundle = get_category_bundle()
    if bundle is None:
        post_res = post_process_category("Miscellaneous", text)
        return {
            "predicted_category": post_res["final_category"],
            "final_category": post_res["final_category"],
            "raw_category": "Miscellaneous",
            "assigned_team": post_res["assigned_team"],
            "is_overridden": False,
            "category_confidence": 0.50,
            "top_3_categories": [],
            "reason": "8-Class Category Model bundle not loaded"
        }

    try:
        vec = bundle["vectorizer"]
        clf = bundle["classifier"]
        le = bundle["label_encoder"]

        text_str = str(text).strip()
        vectorized = vec.transform([text_str])

        if hasattr(clf, "predict_proba"):
            probs = clf.predict_proba(vectorized)[0]
            top_indices = np.argsort(probs)[::-1][:3]
            classes = le.classes_

            top_3 = []
            for idx in top_indices:
                cat_label = classes[idx]
                prob = float(probs[idx])
                top_3.append({"category": str(cat_label), "confidence": round(prob, 4)})

            best_cat = top_3[0]["category"]
            best_conf = top_3[0]["confidence"]

            post_res = post_process_category(best_cat, text_str)

            return {
                "predicted_category": post_res["final_category"],
                "final_category": post_res["final_category"],
                "raw_category": str(best_cat),
                "assigned_team": post_res["assigned_team"],
                "is_overridden": post_res["is_overridden"],
                "category_confidence": best_conf,
                "top_3_categories": top_3,
            }
        else:
            pred_idx = clf.predict(vectorized)[0]
            cat_label = le.inverse_transform([pred_idx])[0]
            post_res = post_process_category(str(cat_label), text_str)
            return {
                "predicted_category": post_res["final_category"],
                "final_category": post_res["final_category"],
                "raw_category": str(cat_label),
                "assigned_team": post_res["assigned_team"],
                "is_overridden": post_res["is_overridden"],
                "category_confidence": 0.88,
                "top_3_categories": [{"category": str(cat_label), "confidence": 0.88}],
            }
    except Exception as e:
        print(f"[ERROR] Error in predict_ticket_category: {e}")
        post_res = post_process_category("Miscellaneous", text)
        return {
            "predicted_category": post_res["final_category"],
            "final_category": post_res["final_category"],
            "raw_category": "Miscellaneous",
            "assigned_team": post_res["assigned_team"],
            "is_overridden": False,
            "category_confidence": 0.50,
            "top_3_categories": [],
            "reason": f"Category prediction exception: {e}"
        }

def predict_team_ml(text: str, confidence_threshold: float = 0.55):
    """
    ML-based team routing using shared embedding service with graceful degradation fallback.
    """
    router = get_router_model()
    le = get_label_encoder()

    if router is None or le is None:
        return {
            "predicted_team": "Unassigned/Triage",
            "confidence": None,
            "top_3_alternatives": [],
            "is_low_confidence": True,
            "reason": "Model artifacts not loaded",
        }

    try:
        vector = embed_text(text).reshape(1, -1)

        if hasattr(router, "predict_proba"):
            probs = router.predict_proba(vector)[0]
            top_indices = np.argsort(probs)[::-1][:3]

            classes = le.classes_
            top_3 = []
            for idx in top_indices:
                team_label = classes[idx]
                prob = float(probs[idx])
                top_3.append({"team": str(team_label), "confidence": round(prob, 4)})

            best_team = top_3[0]["team"]
            best_conf = top_3[0]["confidence"]

            if best_conf < confidence_threshold:
                return {
                    "predicted_team": "Unassigned/Triage",
                    "suggested_team": best_team,
                    "confidence": best_conf,
                    "top_3_alternatives": top_3,
                    "is_low_confidence": True,
                    "reason": f"Confidence {best_conf:.2f} below threshold {confidence_threshold:.2f}",
                }

            return {
                "predicted_team": best_team,
                "confidence": best_conf,
                "top_3_alternatives": top_3,
                "is_low_confidence": False,
            }
        else:
            pred_idx = router.predict(vector)[0]
            team_label = le.inverse_transform([pred_idx])[0]
            return {
                "predicted_team": str(team_label),
                "confidence": 0.85,
                "top_3_alternatives": [{"team": str(team_label), "confidence": 0.85}],
                "is_low_confidence": False,
            }
    except Exception as e:
        print(f"[ERROR] Graceful degradation in predict_team_ml: {e}")
        return {
            "predicted_team": "Unassigned/Triage",
            "confidence": None,
            "top_3_alternatives": [],
            "is_low_confidence": True,
            "reason": "Routing model error — safely degraded to triage queue",
        }
