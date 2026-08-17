import os
import json
import pickle
import joblib
import numpy as np
from app.core.embeddings import embed_text

MODELS_DIR = "model_assets/models"
ROUTER_PATH = os.path.join(MODELS_DIR, "router.pkl")
LABEL_ENCODER_PATH = os.path.join(MODELS_DIR, "label_encoder.pkl")
BUNDLE_PATH = os.path.join(MODELS_DIR, "tfidf_lgbm_bundle.joblib")

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
    "Hardware": "Desktop Support",
    "Access": "Identity & Access Management",
    "Administrative rights": "IT Admin",
    "HR Support": "HR Operations",
    "Internal Project": "Application Support",
    "Storage": "Infrastructure Support",
    "Purchase": "Procurement",
    "Miscellaneous": "General Support",
}

ALLOWED_TEAMS = [
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
                    model="llama-3.1-8b-instant",
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
    "Access",
    "Administrative rights",
    "HR Support",
    "Hardware",
    "Internal Project",
    "Miscellaneous",
    "Purchase",
    "Storage",
]

ALLOWED_PRIORITIES = ["Critical", "High", "Medium", "Low"]
ALLOWED_SLA_TARGETS = ["4 hours", "24 hours", "48 hours", "72 hours"]

def classify_and_route_ticket(title: str, description: str) -> dict:
    """
    Single-pass LLM classifier using Groq client ('llama-3.1-8b-instant').
    Dynamically predicts Category, Assigned Team, Priority, and SLA Target using semantic reasoning.
    Falls back safely on error.
    """
    fallback_res = {
        "category": "Internal Project",
        "assigned_team": "Application Support",
        "priority": "Medium",
        "sla_target": "48 hours",
        "category_confidence": 0.95
    }

    try:
        from ai.rag.groq_client import get_groq_api_keys, Groq

        api_keys = get_groq_api_keys()
        if not api_keys:
            print("[UNIFIED LLM CLASSIFIER WARN] No GROQ_API_KEY available. Returning fallback.")
            return fallback_res

        sys_prompt = """You are an enterprise IT Service Management (ITSM) dispatcher AI. Your job is to classify and route IT support tickets in a single pass based on the ticket title and description.

You MUST strictly follow these rules:

1. Category (Select strictly ONE from the 8 allowed categories):
- "Access": IAM, SSO, MFA, VPN, passwords, user permissions.
- "Administrative rights": Elevated privileges, sudo access, admin roles.
- "HR Support": Leaves, payroll, benefits, policy inquiries.
- "Hardware": STRICTLY physical device failures (monitors, keyboards, docks, laptops, chargers, cables).
- "Internal Project": Software development, internal tools, microservices, gRPC, APIs, application updates, bugs, database issues.
- "Miscellaneous": General queries not fitting other categories.
- "Purchase": Procurement requests, new software/hardware purchase orders.
- "Storage": Disk quotas, cloud buckets (S3), network shares, backup space.

2. Assigned Team (Select strictly ONE from the allowed support teams):
- "Application Support" (Internal app bugs, microservices, gRPC timeouts, API errors, frontend crashes, application updates, internal tools)
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

3. Priority & SLA Target (Select strictly ONE matching pair):
- "Critical" -> "4 hours" (Production outages, payment/checkout failures, widespread blockers)
- "High" -> "24 hours" (Service timeouts, gRPC connection timeouts, update failures, build/staging blocks, replica lag)
- "Medium" -> "48 hours" (Non-blocking single-user issues, quota warnings)
- "Low" -> "72 hours" (General inquiries, non-urgent procurement)

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
                    model="llama-3.1-8b-instant",
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
                            cat = "Internal Project"
                        if team not in ALLOWED_TEAMS:
                            team = "Application Support"
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
      - Override category to 'Internal Project'
      - Assign team to 'Application Support'
    Otherwise, map assigned team using CATEGORY_TEAM_MAP.
    """
    text_lower = str(text).lower()

    has_software_kw = any(kw in text_lower for kw in SOFTWARE_KEYWORDS)
    has_hardware_kw = any(kw in text_lower for kw in HARDWARE_KEYWORDS)

    final_category = predicted_category
    is_overridden = False

    if predicted_category == "Hardware" and has_software_kw and not has_hardware_kw:
        final_category = "Internal Project"
        is_overridden = True

    assigned_team = CATEGORY_TEAM_MAP.get(final_category, "General Support")

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
