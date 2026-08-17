import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("\n=======================================================================")
print("  TESTING 8-CLASS LIGHTGBM IT TICKET CATEGORY CLASSIFIER")
print("=======================================================================")

test_cases = [
    {
        "title": "Account Access Issue",
        "description": "My account cannot access the company application",
        "expected_category_hint": "Access"
    },
    {
        "title": "Admin Rights Request",
        "description": "I need administrator privileges on my workstation for developer setup",
        "expected_category_hint": "Administrative rights"
    },
    {
        "title": "HR Query",
        "description": "I have an HR-related issue with my employee records and payroll",
        "expected_category_hint": "HR Support"
    },
    {
        "title": "Hardware Malfunction",
        "description": "My laptop keyboard and display screen are not working",
        "expected_category_hint": "Hardware"
    },
    {
        "title": "Internal Project Assistance",
        "description": "I need help with an internal project repository deployment",
        "expected_category_hint": "Internal Project"
    },
    {
        "title": "General Query",
        "description": "General IT issue that does not fit another category",
        "expected_category_hint": "Miscellaneous"
    },
    {
        "title": "Purchase Order Request",
        "description": "I need to purchase new IT equipment and software licenses",
        "expected_category_hint": "Purchase"
    },
    {
        "title": "Database Storage Limit",
        "description": "The server disk storage volume is full",
        "expected_category_hint": "Storage"
    }
]

EXPECTED_8_CLASSES = {
    'Access', 'Administrative rights', 'HR Support', 'Hardware',
    'Internal Project', 'Miscellaneous', 'Purchase', 'Storage'
}

for i, test in enumerate(test_cases, 1):
    print(f"\n--- TEST CASE {i}: {test['title']} ---")
    req = {
        "title": test["title"],
        "description": test["description"],
        "requester_name": f"Tester {i}",
        "requester_department": "Engineering",
        "skip_duplicate_check": True
    }
    
    # 1. Preview API Endpoint Test
    res_preview = client.post("/ticket/route-ticket", json={"title": test["title"], "description": test["description"]})
    assert res_preview.status_code == 200
    prev_data = res_preview.json()
    print(f"Preview Pred Category : {prev_data['predicted_category']} (Conf: {prev_data['category_confidence']*100:.1f}%)")
    print(f"Preview Support Team  : {prev_data['predicted_team']}")
    assert prev_data["predicted_category"] in EXPECTED_8_CLASSES

    # 2. Ticket Creation Endpoint & DB Save Test
    res_create = client.post("/ticket/create", json=req)
    assert res_create.status_code == 200
    create_data = res_create.json()
    ticket = create_data["ticket"]
    
    print(f"Created Ticket ID     : #{ticket['id']}")
    print(f"Saved DB Category     : {ticket['category']}")
    print(f"Assigned Support Team : {ticket['assigned_team']}")
    print(f"Priority              : {ticket['priority']}")
    print(f"SLA Target            : {ticket['sla_hours']} hours")
    
    assert ticket["category"] in EXPECTED_8_CLASSES

print("\n=======================================================================")
print("[OK] ALL 8-CLASS TICKET CATEGORY CLASSIFICATION TESTS PASSED SUCCESSFULLY!")
print("=======================================================================\n")
