"""
app/availability/providers.py

LeaveProvider interface and implementations for external HR systems.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import csv
import io
from pathlib import Path


class LeaveProvider(ABC):
    @abstractmethod
    def fetch_approved_leave(self) -> List[Dict[str, Any]]:
        """
        Fetches approved leave records from the external provider.
        Must return a list of dicts with keys:
          - user_email: str
          - start: str or datetime ("YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS")
          - end: str or datetime ("YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS")
          - half_day: bool
          - external_id: str
          - status: str ('approved', 'pending', 'cancelled')
        """
        pass


class MockHRProvider(LeaveProvider):
    """
    Simulates an enterprise HR system by reading from a local JSON file (hr_leave.json).
    """
    def __init__(self, file_path: Optional[str] = None):
        if file_path:
            self.file_path = Path(file_path)
        else:
            # Default to backend root/hr_leave.json or workspace/hr_leave.json
            base_backend = Path(__file__).resolve().parent.parent.parent
            self.file_path = base_backend / "hr_leave.json"

    def fetch_approved_leave(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            # Check one directory up as fallback
            alt_path = self.file_path.parent.parent / "hr_leave.json"
            if alt_path.exists():
                self.file_path = alt_path
            else:
                return []

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[MockHRProvider Error] Failed to read {self.file_path}: {e}")
            return []


class CsvImportProvider(LeaveProvider):
    """
    Allows importing HR leave records from uploaded CSV data.
    """
    def __init__(self, csv_content: Optional[str] = None):
        self.csv_content = csv_content or ""

    def set_content(self, csv_content: str):
        self.csv_content = csv_content

    def fetch_approved_leave(self) -> List[Dict[str, Any]]:
        if not self.csv_content or not self.csv_content.strip():
            return []

        records = []
        reader = csv.DictReader(io.StringIO(self.csv_content))
        for row in reader:
            records.append({
                "user_email": row.get("user_email", "").strip(),
                "start": row.get("start", "").strip(),
                "end": row.get("end", "").strip(),
                "half_day": row.get("half_day", "").strip().lower() in ["true", "1", "yes"],
                "external_id": row.get("external_id", "").strip(),
                "status": row.get("status", "approved").strip().lower(),
            })
        return records


# =========================================================================
# REAL HR SYSTEM INTEGRATION (e.g., Workday, BambooHR, Gusto, SAP SuccessFactors)
# =========================================================================
# REAL HR SYSTEM EXTENSION POINT (Keka / Zoho People / greytHR / Workday):
#
# To integrate a real enterprise HR system, create a class implementing LeaveProvider:
#
# class KekaHRProvider(LeaveProvider):
#     """Integration with Keka HR REST API (/v1/timeoff/leaves)."""
#     def fetch_approved_leave(self) -> List[Dict[str, Any]]: ...
#
# class ZohoPeopleProvider(LeaveProvider):
#     """Integration with Zoho People API (timetracker/leave)."""
#     def fetch_approved_leave(self) -> List[Dict[str, Any]]: ...
#
# class GreytHRProvider(LeaveProvider):
#     """Integration with greytHR API (v2/leave/applications)."""
#     def fetch_approved_leave(self) -> List[Dict[str, Any]]: ...
#
# class WorkdayHRProvider(LeaveProvider):
#     def __init__(self, tenant_url: str, client_id: str, client_secret: str):
#         self.tenant_url = tenant_url
#         self.client_id = client_id
#         self.client_secret = client_secret
#
#     def fetch_approved_leave(self) -> List[Dict[str, Any]]:
#         # 1. Obtain OAuth2 access token
#         # token = self._get_oauth_token()
#         # 2. Query Time Off REST API for approved leaves
#         # resp = requests.get(
#         #     f"{self.tenant_url}/ccx/api/v1/timeOff/approved",
#         #     headers={"Authorization": f"Bearer {token}"},
#         #     params={"from_date": datetime.utcnow().strftime("%Y-%m-%d")}
#         # )
#         # 3. Transform API response into standard format:
#         # return [
#         #     {
#         #         "user_email": item["worker"]["email"],
#         #         "start": item["startDate"],
#         #         "end": item["endDate"],
#         #         "half_day": item.get("halfDayIndicator", False),
#         #         "external_id": item["eventRecordId"],
#         #         "status": "approved",
#         #     }
#         #     for item in resp.json().get("data", [])
#         # ]
# =========================================================================
