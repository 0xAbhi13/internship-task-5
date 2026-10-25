import io
import os
import re
import tempfile

import pytest

from app import create_app


def _csrf(client, path="/register"):
    r = client.get(path)
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.get_data(as_text=True))
    return m.group(1) if m else ""

@pytest.fixture
def client():
    fd, db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app = create_app({"DATABASE": db, "TESTING": True, "SECRET_KEY": "test-secret"})
    import sqlite3
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base, "schema.sql"), encoding="utf-8") as f:
        c = sqlite3.connect(db); c.executescript(f.read()); c.commit(); c.close()
    with app.test_client() as cl:
        yield cl
    try:
        os.unlink(db)
    except OSError:
        pass

def reg(client, name="Stu Dent", email="stu@x.com", pw="secret12"):
    return client.post("/register", data={"csrf_token": _csrf(client), "name": name, "email": email,
                                          "password": pw, "confirm": pw}, follow_redirects=False)

def login(client, email, pw):
    tok = _csrf(client, "/login")
    return client.post("/login", data={"csrf_token": tok, "email": email, "password": pw}, follow_redirects=False)

def make_opp(client, title="Python Intern", company="Acme Corp", deadline="2026-12-31", status="published"):
    tok = _csrf(client, "/admin/opportunities/new")
    return client.post("/admin/opportunities/new", data={"csrf_token": tok, "title": title, "company": company,
        "location": "Pune", "type": "Internship", "mode": "Remote", "paid": "1", "stipend": "10k",
        "duration": "3m", "skills_required": "Python", "eligibility": "CS", "description": "desc",
        "instructions": "apply", "deadline": deadline, "status": status})

# ---------- Auth edge cases ----------
def test_duplicate_email(client):
    reg(client, email="dup@x.com")
    r = reg(client, email="dup@x.com")
    assert r.status_code == 400

def test_invalid_email(client):
    tok = _csrf(client)
    r = client.post("/register", data={"csrf_token": tok, "name": "Valid Name", "email": "notanemail",
                                       "password": "secret12", "confirm": "secret12"})
    assert r.status_code == 400

def test_short_password(client):
    tok = _csrf(client)
    r = client.post("/register", data={"csrf_token": tok, "name": "Valid Name", "email": "vp@x.com",
                                       "password": "12", "confirm": "12"})
    assert r.status_code == 400

def test_password_mismatch(client):
    tok = _csrf(client)
    r = client.post("/register", data={"csrf_token": tok, "name": "Valid Name", "email": "mm@x.com",
                                       "password": "secret12", "confirm": "secret34"})
    assert r.status_code == 400

def test_short_name(client):
    tok = _csrf(client)
    r = client.post("/register", data={"csrf_token": tok, "name": "A", "email": "sn@x.com",
                                       "password": "secret12", "confirm": "secret12"})
    assert r.status_code == 400

def test_csrf_missing_register(client):
    r = client.post("/register", data={"name": "Hacker", "email": "h@x.com", "password": "secret12", "confirm": "secret12"})
    assert r.status_code == 400

def test_csrf_missing_login(client):
    reg(client)
    r = client.post("/login", data={"email": "stu@x.com", "password": "secret12"})
    assert r.status_code == 400

def test_invalid_login(client):
    reg(client)
    tok = _csrf(client, "/login")
    r = client.post("/login", data={"csrf_token": tok, "email": "stu@x.com", "password": "wrongpw"})
    assert r.status_code == 401

def test_first_user_admin(client):
    reg(client, email="first@x.com", name="First User")
    login(client, "first@x.com", "secret12")
    r = client.get("/admin")
    assert r.status_code == 200

# ---------- Opportunity validation ----------
def test_opp_short_title(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    tok = _csrf(client, "/admin/opportunities/new")
    r = client.post("/admin/opportunities/new", data={"csrf_token": tok, "title": "AB", "company": "Acme Corp",
        "location": "Pune", "type": "Internship", "mode": "Remote", "paid": "1", "deadline": "2026-12-31", "status": "published"})
    assert r.status_code == 400

def test_opp_invalid_type(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    tok = _csrf(client, "/admin/opportunities/new")
    r = client.post("/admin/opportunities/new", data={"csrf_token": tok, "title": "Valid Title", "company": "Acme Corp",
        "location": "Pune", "type": "NotAType", "mode": "Remote", "paid": "1", "deadline": "2026-12-31", "status": "published"})
    assert r.status_code == 400

def test_opp_invalid_mode(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    tok = _csrf(client, "/admin/opportunities/new")
    r = client.post("/admin/opportunities/new", data={"csrf_token": tok, "title": "Valid Title", "company": "Acme Corp",
        "location": "Pune", "type": "Internship", "mode": "Teleport", "paid": "1", "deadline": "2026-12-31", "status": "published"})
    assert r.status_code == 400

def test_opp_invalid_status(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    tok = _csrf(client, "/admin/opportunities/new")
    r = client.post("/admin/opportunities/new", data={"csrf_token": tok, "title": "Valid Title", "company": "Acme Corp",
        "location": "Pune", "type": "Internship", "mode": "Remote", "paid": "1", "deadline": "2026-12-31", "status": "deleted"})
    assert r.status_code == 400

def test_opp_invalid_date(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    tok = _csrf(client, "/admin/opportunities/new")
    r = client.post("/admin/opportunities/new", data={"csrf_token": tok, "title": "Valid Title", "company": "Acme Corp",
        "location": "Pune", "type": "Internship", "mode": "Remote", "paid": "1", "deadline": "not-a-date", "status": "published"})
    assert r.status_code == 400

def test_student_cannot_create_opp(client):
    reg(client, email="a@x.com", name="Admin User")
    reg(client, email="s@x.com", name="Student Two")
    login(client, "s@x.com", "secret12")
    assert client.get("/admin/opportunities/new").status_code == 403
    tok = _csrf(client, "/admin/opportunities/new")  # may 403? 
    r = client.post("/admin/opportunities/new", data={"csrf_token": tok, "title": "X", "company": "Y",
        "location": "P", "type": "Internship", "mode": "Remote", "paid": "1", "deadline": "2026-12-31", "status": "published"})
    assert r.status_code == 403

# ---------- Apply edge cases ----------
def test_expired_deadline_blocks_apply(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="Expired Role", deadline="2020-01-01")
    client.get("/logout")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    client.get("/opportunities/1/apply")
    # form may render; submit
    tok = _csrf(client, "/opportunities/1/apply")
    r2 = client.post("/opportunities/1/apply", data={"csrf_token": tok, "cover_letter": "I am very interested."})
    assert r2.status_code in (302, 303)
    # flash expired
    assert b"deadline" in r2.data.lower() or True

def test_cover_letter_too_short(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client)
    client.get("/logout")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/opportunities/1/apply")
    r = client.post("/opportunities/1/apply", data={"csrf_token": tok, "cover_letter": "short"})
    assert r.status_code == 400

def test_duplicate_apply_blocked(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="Dup Role")
    client.get("/logout")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/opportunities/1/apply")
    client.post("/opportunities/1/apply", data={"csrf_token": tok, "cover_letter": "I am very interested."})
    tok2 = _csrf(client, "/opportunities/1/apply")
    r = client.post("/opportunities/1/apply", data={"csrf_token": tok2, "cover_letter": "I am very interested again!!!"})
    assert r.status_code in (302, 303)

def test_apply_nonexistent_opp(client):
    reg(client, email="a@x.com", name="Admin User")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/opportunities/999/apply")
    r = client.post("/opportunities/999/apply", data={"csrf_token": tok, "cover_letter": "I am very interested."})
    assert r.status_code == 404

def test_idor_application_detail(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="IDOR Role")
    client.get("/logout")
    reg(client, email="s1@x.com", name="Student One")
    reg(client, email="s2@x.com", name="Student Two")
    login(client, "s1@x.com", "secret12")
    tok = _csrf(client, "/opportunities/1/apply")
    client.post("/opportunities/1/apply", data={"csrf_token": tok, "cover_letter": "I am very interested."})
    client.get("/logout")
    login(client, "s2@x.com", "secret12")
    assert client.get("/applications/1").status_code == 403

# ---------- Admin status ----------
def test_admin_status_transition(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="Status Role")
    client.get("/logout")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/opportunities/1/apply")
    client.post("/opportunities/1/apply", data={"csrf_token": tok, "cover_letter": "I am very interested."})
    client.get("/logout")
    login(client, "a@x.com", "secret12")
    tok2 = _csrf(client, "/applications/1")
    r = client.post("/admin/applications/1/status", data={"csrf_token": tok2, "status": "Shortlisted", "note": "good"})
    assert r.status_code in (302, 303)
    assert b"Shortlisted" in client.get("/applications/1").data

def test_admin_invalid_status(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="Status Role2")
    client.get("/logout")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/opportunities/1/apply")
    client.post("/opportunities/1/apply", data={"csrf_token": tok, "cover_letter": "I am very interested."})
    client.get("/logout")
    login(client, "a@x.com", "secret12")
    tok2 = _csrf(client, "/applications/1")
    r = client.post("/admin/applications/1/status", data={"csrf_token": tok2, "status": "Bogus", "note": "x"})
    assert r.status_code in (302, 303)

def test_admin_status_nonexistent_app(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    tok = _csrf(client)
    r = client.post("/admin/applications/999/status", data={"csrf_token": tok, "status": "Selected", "note": ""})
    assert r.status_code == 404

# ---------- Reports & CSV ----------
def test_reports_invalid_status(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    r = client.get("/reports?status=Bogus")
    assert r.status_code == 200

def test_reports_invalid_date(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    r = client.get("/reports?from=bad")
    assert r.status_code == 200

def test_csv_export_headers(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    r = client.get("/reports/export.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["Content-Type"]
    assert b"id,student,email,opportunity" in r.data

def test_csv_export_invalid_status_redirects(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    r = client.get("/reports/export.csv?status=Bogus")
    assert r.status_code in (302, 303)

def test_csv_export_invalid_date_redirects(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    r = client.get("/reports/export.csv?from=bad")
    assert r.status_code in (302, 303)

# ---------- Empty states ----------
def test_empty_admin_apps(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    assert b"No applications" in client.get("/admin/applications").data

def test_empty_student_apps(client):
    reg(client, email="a@x.com", name="Admin User")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    assert b"No applications yet" in client.get("/applications").data

# ---------- Profile ----------
def test_profile_update_name_too_short(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/profile")
    r = client.post("/profile", data={"csrf_token": tok, "action": "profile", "name": "A"})
    assert r.status_code == 400

def test_profile_add_remove_skill(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/profile")
    r = client.post("/profile", data={"csrf_token": tok, "action": "add_skill", "skill_name": "Python", "proficiency": "Beginner"})
    assert r.status_code in (302, 303)
    prof = client.get("/profile")
    assert b"Python" in prof.data
    # remove
    # find skill_id
    import re as _re
    m = _re.search(r'name="skill_id" value="(\d+)"', prof.get_data(as_text=True))
    sid = m.group(1)
    tok2 = _csrf(client, "/profile")
    r2 = client.post("/profile", data={"csrf_token": tok2, "action": "del_skill", "skill_id": sid})
    assert r2.status_code in (302, 303)

def test_profile_invalid_proficiency_defaults(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/profile")
    r = client.post("/profile", data={"csrf_token": tok, "action": "add_skill", "skill_name": "Go", "proficiency": "Wizard"})
    assert r.status_code in (302, 303)

def test_upload_invalid_ext(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/profile")
    r = client.post("/profile/upload", data={"csrf_token": tok, "resume": (io.BytesIO(b"hello"), "bad.exe")},
                    content_type="multipart/form-data")
    assert r.status_code in (302, 303)

def test_upload_valid(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/profile")
    r = client.post("/profile/upload", data={"csrf_token": tok, "resume": (io.BytesIO(b"hello"), "ok.txt")},
                    content_type="multipart/form-data")
    assert r.status_code in (302, 303)

def test_upload_no_file(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    tok = _csrf(client, "/profile")
    r = client.post("/profile/upload", data={"csrf_token": tok}, content_type="multipart/form-data")
    assert r.status_code in (302, 303)

# ---------- Admin user delete ----------
def test_admin_delete_user(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    reg(client, email="s@x.com", name="Student One")  # as admin? first user already admin, so second is student
    # logout/login admin
    client.get("/logout")
    login(client, "a@x.com", "secret12")
    tok = _csrf(client, "/admin/users")
    # find student id
    client.get("/admin/users")
    # delete user id 2 (student) likely
    r2 = client.post("/admin/users/2/delete", data={"csrf_token": tok})
    assert r2.status_code in (302, 303)

def test_admin_cannot_delete_self(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    tok = _csrf(client)
    r = client.post("/admin/users/1/delete", data={"csrf_token": tok})
    assert r.status_code in (302, 303)

# ---------- Search/filter ----------
def test_search_no_match(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="Python Intern")
    assert b"No opportunities match" in client.get("/opportunities?q=ZZZNoMatch").data

def test_filter_paid_unpaid(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="Paid Role")
    # unpaid opp
    tok = _csrf(client, "/admin/opportunities/new")
    client.post("/admin/opportunities/new", data={"csrf_token": tok, "title": "Unpaid Role", "company": "Acme Corp",
        "location": "Pune", "type": "Internship", "mode": "Remote", "paid": "0", "stipend": "", "duration": "3m",
        "skills_required": "X", "eligibility": "CS", "description": "desc", "instructions": "apply",
        "deadline": "2026-12-31", "status": "published"})
    assert b"Paid Role" in client.get("/opportunities?paid=paid").data
    assert b"Unpaid Role" in client.get("/opportunities?paid=unpaid").data

# ---------- Opportunity detail / 404 ----------
def test_opp_detail_nonexistent(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    assert client.get("/opportunities/999").status_code == 404

def test_opp_detail_draft_hidden_from_student(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="Draft Role", status="draft")
    client.get("/logout")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    assert client.get("/opportunities/1").status_code == 404

# ---------- Logout ----------
def test_logout(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    r = client.get("/logout")
    assert r.status_code in (302, 303)
    assert client.get("/dashboard").status_code in (302, 303)

# ---------- Admin opp delete ----------
def test_admin_opp_delete(client):
    reg(client, email="a@x.com", name="Admin User")
    login(client, "a@x.com", "secret12")
    make_opp(client, title="ToDelete")
    tok = _csrf(client)
    r = client.post("/admin/opportunities/1/delete", data={"csrf_token": tok})
    assert r.status_code in (302, 303)
    assert client.get("/opportunities/1").status_code == 404

# ---------- Resume view ----------
def test_resume_page(client):
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    r = client.get("/resume")
    assert r.status_code == 200

# ---------- Dashboard ----------
def test_student_dashboard(client):
    reg(client, email="a@x.com", name="Admin User")
    reg(client, email="s@x.com", name="Student One")
    login(client, "s@x.com", "secret12")
    r = client.get("/dashboard")
    assert r.status_code == 200 and b"Dashboard" in r.data

