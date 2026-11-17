"""
backend/tests/test_ticket_attachments.py

Tests for Document Attachment Feature:
1. Uploading single and multiple valid document attachments to a ticket.
2. Timeline audit entry created when document is attached.
3. Rejection of forbidden dangerous executable file extensions (e.g. .exe, .bat).
4. Rejection of oversized files exceeding 15MB limit.
5. Listing attachments via GET /{ticket_id}/attachments.
6. Downloading attachment via GET /attachments/{id}/download with correct headers.
7. Employee and agent detail endpoints surfacing attachment metadata.
8. Deletion of attachments and disk cleanup.
"""

import io
import os
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.models.ticket import Ticket
from app.models.comment import TicketComment
from app.models.attachment import TicketAttachment
from app.tickets.routes import (
    upload_ticket_attachments,
    get_ticket_attachments,
    download_ticket_attachment,
    delete_ticket_attachment,
    get_employee_ticket_detail,
    UPLOAD_DIR,
)
from app.agent.routes import get_ticket_detail

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)


def dummy_request(user_id=1, user_role="employee", user_name="Alice Employee"):
    req = MagicMock()
    req.headers = {
        "X-User-Id": str(user_id),
        "X-User-Role": user_role,
        "X-User-Name": user_name,
        "X-User-Email": f"{user_name.lower().replace(' ', '.')}@company.com",
    }
    return req


@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr("app.tickets.routes.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.agent.routes.SessionLocal", TestingSessionLocal)
    
    # Use temporary upload directory for isolation
    temp_upload = tmp_path / "attachments"
    temp_upload.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.tickets.routes.UPLOAD_DIR", str(temp_upload))

    yield

    Base.metadata.drop_all(bind=test_engine)


def create_sample_ticket():
    db = TestingSessionLocal()
    ticket = Ticket(
        title="VPN Gateway connectivity failure",
        description="Cannot authenticate with AnyConnect gateway from home office.",
        category="Network Operations",
        priority="High",
        status="open",
        requester_name="Alice Employee",
        requester_department="Finance",
    )
    db.add(ticket)
    db.commit()
    t_id = ticket.id
    db.close()
    return t_id


@pytest.mark.anyio
async def test_upload_and_list_attachments():
    t_id = create_sample_ticket()
    req = dummy_request()

    pdf_content = b"%PDF-1.4 sample PDF content for vpn error log"
    docx_content = b"sample docx document content"

    file1 = UploadFile(filename="vpn_error.pdf", file=io.BytesIO(pdf_content))
    file2 = UploadFile(filename="network_trace.docx", file=io.BytesIO(docx_content))

    res = await upload_ticket_attachments(ticket_id=t_id, request=req, files=[file1, file2])

    assert "Successfully attached 2 document(s)" in res["message"]
    assert len(res["attachments"]) == 2
    assert res["attachments"][0]["filename"] == "vpn_error.pdf"
    assert res["attachments"][1]["filename"] == "network_trace.docx"

    # Verify listing endpoint
    listed = get_ticket_attachments(ticket_id=t_id)
    assert len(listed) == 2
    assert listed[0]["filename"] == "vpn_error.pdf"
    assert listed[1]["filename"] == "network_trace.docx"

    # Verify timeline comment was generated
    db = TestingSessionLocal()
    comments = db.query(TicketComment).filter(TicketComment.ticket_id == t_id).all()
    assert any("Attached document: vpn_error.pdf" in c.content for c in comments)
    assert any("Attached document: network_trace.docx" in c.content for c in comments)
    db.close()


@pytest.mark.anyio
async def test_reject_dangerous_extension():
    t_id = create_sample_ticket()
    req = dummy_request()

    exe_file = UploadFile(filename="trojan.exe", file=io.BytesIO(b"binary payload"))

    with pytest.raises(HTTPException) as exc_info:
        await upload_ticket_attachments(ticket_id=t_id, request=req, files=[exe_file])

    assert exc_info.value.status_code == 400
    assert "forbidden extension" in exc_info.value.detail.lower()


@pytest.mark.anyio
async def test_reject_oversized_file():
    t_id = create_sample_ticket()
    req = dummy_request()

    # Oversized mock content (> 15MB)
    huge_data = b"X" * (15 * 1024 * 1024 + 1024)
    huge_file = UploadFile(filename="large_dump.log", file=io.BytesIO(huge_data))

    with pytest.raises(HTTPException) as exc_info:
        await upload_ticket_attachments(ticket_id=t_id, request=req, files=[huge_file])

    assert exc_info.value.status_code == 400
    assert "exceeds the maximum allowed limit" in exc_info.value.detail.lower()


@pytest.mark.anyio
async def test_download_and_delete_attachment():
    t_id = create_sample_ticket()
    req = dummy_request()

    content = b"Error log line 1\nError log line 2"
    file = UploadFile(filename="server_error.log", file=io.BytesIO(content))

    upload_res = await upload_ticket_attachments(ticket_id=t_id, request=req, files=[file])
    att_id = upload_res["attachments"][0]["id"]

    # Test download response
    download_res = download_ticket_attachment(attachment_id=att_id)
    assert download_res.filename == "server_error.log"
    assert "server_error.log" in download_res.headers.get("content-disposition", "")

    # Test delete
    del_res = delete_ticket_attachment(attachment_id=att_id, request=req)
    assert "deleted successfully" in del_res["message"]

    # Listing should now be empty
    after_del = get_ticket_attachments(ticket_id=t_id)
    assert len(after_del) == 0


@pytest.mark.anyio
async def test_detail_endpoints_include_attachments():
    t_id = create_sample_ticket()
    req_employee = dummy_request(user_role="employee", user_name="Alice Employee")
    req_agent = dummy_request(user_role="agent", user_name="Sarah Agent")

    file = UploadFile(filename="screenshot.png", file=io.BytesIO(b"fake image bytes"))
    await upload_ticket_attachments(ticket_id=t_id, request=req_employee, files=[file])

    # Employee detail endpoint
    emp_detail = get_employee_ticket_detail(ticket_id=t_id, request=req_employee)
    assert "attachments" in emp_detail
    assert len(emp_detail["attachments"]) == 1
    assert emp_detail["attachments"][0]["filename"] == "screenshot.png"

    # Agent detail endpoint
    agent_detail = get_ticket_detail(ticket_id=t_id, request=req_agent)
    assert "attachments" in agent_detail
    assert len(agent_detail["attachments"]) == 1
    assert agent_detail["attachments"][0]["filename"] == "screenshot.png"
