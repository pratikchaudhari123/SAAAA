"""Local HTTP acceptance checks against a running SAAAA instance.
Creates an isolated synthetic institution and temporary users; retains test records
for evidence, disables temporary users in finally. Never modifies GCOEA records.
Run from the host: python3 scripts/live_acceptance.py
"""
import datetime
import http.cookiejar
import json
import secrets
import subprocess
import sys
import urllib.request
import urllib.error
from decimal import Decimal
from zoneinfo import ZoneInfo

BASE = "http://127.0.0.1:5175"
CONTAINER = "saaaa-erp-api-1"
run = secrets.token_hex(5)
slug = "acceptance-" + run
roles = ("admin", "admissions", "faculty", "finance", "warden", "principal", "viewer")
accounts = {role: {"username": "qa_" + run + "_" + role, "password": secrets.token_urlsafe(24)} for role in roles}
passed = 0
failed = 0
created = False

def shell(code):
    proc = subprocess.run(["docker", "exec", "-i", CONTAINER, "python", "manage.py", "shell"], input=code, text=True, capture_output=True, timeout=60)
    if proc.returncode or "Traceback (most recent call last)" in proc.stderr or "Traceback (most recent call last)" in proc.stdout:
        raise RuntimeError("Django setup or cleanup failed; inspect container logs locally.")
    return proc.stdout

class Client:
    def __init__(self):
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
    def request(self, path, payload=None):
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers.update({"Content-Type":"application/json", "X-CSRFToken": next((c.value for c in self.cookies if c.name=="csrftoken"), ""), "Origin":BASE, "Referer":BASE+"/"})
        req = urllib.request.Request(BASE + path, data=data, headers=headers)
        try:
            with self.opener.open(req, timeout=20) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as res:
            try: body = json.loads(res.read())
            except ValueError: body = {}
            return res.code, body

def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS | " + label, flush=True)
    else:
        failed += 1
        print("FAIL | " + label, flush=True)
    return condition

def expect(client, path, status, label, payload=None):
    actual, body = client.request(path, payload)
    if not check(label + " (HTTP " + str(actual) + ")", actual == status):
        raise RuntimeError("Required step failed: " + label)
    return body

def main():
    global created
    anon = Client()
    check("Frontend responds HTTP 200", urllib.request.urlopen(BASE+"/", timeout=15).status == 200)
    health = expect(anon, "/api/health/", 200, "API health through frontend proxy")
    if not check("PostgreSQL connected", health.get("database") == "connected"): return
    expect(anon, "/api/session/", 200, "Anonymous session endpoint")
    check("Anonymous session unauthenticated", anon.request("/api/session/")[1].get("authenticated") is False)
    print("Creating isolated synthetic QA institution: " + slug, flush=True)
    created = True
    shell("from django.contrib.auth import get_user_model\nfrom django.db import transaction\nfrom campus.models import Institution, Membership\nwith transaction.atomic():\n    i=Institution.objects.create(slug="+repr(slug)+",name="+repr("Synthetic acceptance test "+run)+")\n    for role, a in "+repr(accounts)+".items():\n        u=get_user_model().objects.create_user(username=a['username'],password=a['password'])\n        Membership.objects.create(institution=i,user=u,role=role)\n")
    root = "/api/institutions/" + slug + "/"
    expect(anon, root+"students/", 403, "Anonymous student access denied")
    expect(anon, "/api/csrf/", 200, "CSRF cookie issued")
    expect(anon, "/api/login/", 401, "Incorrect password denied", {"username":accounts["admin"]["username"],"password":"incorrect"})
    clients={}
    for role, a in accounts.items():
        c=Client()
        expect(c,"/api/csrf/",200,role+" CSRF")
        expect(c,"/api/login/",200,role+" login",a)
        session=expect(c,"/api/session/",200,role+" session")
        check(role+" correct institutional membership", session.get("authenticated") is True and any(m["institution__slug"]==slug and m["role"]==role for m in session.get("institutions",[])))
        clients[role]=c
    a=clients["admin"]; adm=clients["admissions"]; fac=clients["faculty"]; fin=clients["finance"]; ward=clients["warden"]; pr=clients["principal"]; view=clients["viewer"]
    d=expect(a,root+"setup/departments/",201,"Create department",{"code":"QA","name":"QA Engineering"})
    p=expect(a,root+"setup/programs/",201,"Create program",{"code":"QA-BE","name":"QA Engineering","department":d["id"],"duration_years":4,"intake":60})
    course=expect(a,root+"setup/courses/",201,"Create course",{"code":"QA101","name":"QA Course","program":p["id"],"semester":1,"credits":3})
    day=datetime.datetime.now(ZoneInfo("Asia/Kolkata")).date()
    period=expect(a,root+"setup/periods/",201,"Create academic period",{"code":"QA-2026","starts":str(day-datetime.timedelta(days=30)),"ends":str(day+datetime.timedelta(days=30))})
    student={"student_id":"QA-STUDENT","name":"Synthetic QA Student","email":"qa@example.invalid","program":"QA Engineering","year":1,"status":"Active"}
    expect(adm,root+"students/",201,"Create synthetic application",student)
    rows=expect(adm,root+"students/",200,"Retrieve saved application")
    check("Admission creation forced to Pending",any(r["student_id"]=="QA-STUDENT" and r["status"]=="Pending" for r in rows))
    expect(adm,root+"students/QA-STUDENT/admission/",200,"Approve admission",{"status":"Active"})
    rows=expect(a,root+"students/",200,"Retrieve approved student")
    check("Approved admission persisted",any(r["student_id"]=="QA-STUDENT" and r["status"]=="Active" for r in rows))
    today=datetime.datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    entry={"student_id":"QA-STUDENT","day":today,"course":"QA101","present":True}
    expect(fac,root+"operations/attendance/",403,"Unassigned legacy attendance denied",entry)
    check("Unassigned faculty directory empty",expect(fac,root+"students/",200,"Scoped faculty directory")==[])
    master=expect(a,root+"academic-engine/",200,"Read faculty choices")
    member=next(r["id"] for r in master["faculty"] if r["user__username"]==accounts["faculty"]["username"])
    offering=expect(a,root+"academic-engine/offering/",201,"Assign faculty to course",{"course":course["id"],"period":period["id"],"faculty":member,"batch":"QA"})["id"]
    expect(a,root+"academic-engine/enrollment/",201,"Enroll assigned student",{"offering":offering,"student_id":"QA-STUDENT"})
    check("Assigned faculty sees enrolled student",len(expect(fac,root+"students/",200,"Assigned faculty directory"))==1)
    expect(fac,root+"operations/attendance/",201,"Record attendance",entry)
    records=expect(fac,root+"operations/attendance/",200,"Retrieve attendance")
    check("Attendance persisted",any(r["student__student_id"]=="QA-STUDENT" and r["present"] is True for r in records))
    account=expect(fin,root+"operations/fees/",201,"Assess synthetic fees",{"student_id":"QA-STUDENT","period":"QA-2026","assessed":"1000.00"})
    expect(fin,root+"operations/receipts/",201,"Record synthetic receipt",{"account":account["id"],"amount":"400.00","method":"cash"})
    expect(fin,root+"operations/receipts/",400,"Reject overpayment",{"account":account["id"],"amount":"601.00","method":"cash"})
    fees=expect(fin,root+"operations/fees/",200,"Retrieve fee balance")
    check("Outstanding fees equal INR 600",any(r["id"]==account["id"] and Decimal(r["balance"])==Decimal("600") for r in fees))
    expect(ward,root+"operations/beds/",201,"Allocate bed",{"code":"QA-101-A","student_id":"QA-STUDENT"})
    expect(ward,root+"operations/beds/",400,"Reject duplicate bed allocation",{"code":"QA-101-B","student_id":"QA-STUDENT"})
    expect(ward,root+"operations/hostel_checks/",201,"Record daily hostel verification",{"code":"QA-101-A","status":"present"})
    checks=expect(ward,root+"operations/hostel_checks/",200,"Retrieve hostel verification")
    check("Hostel verification persisted",any(r["student__student_id"]=="QA-STUDENT" and r["status"]=="present" for r in checks))
    dash=expect(pr,root+"dashboard/",200,"Principal live dashboard")
    check("Principal totals reflect transactions",dash["students"]==1 and dash["active_students"]==1 and dash["allocated_beds"]==1 and dash["present_entries_today"]==1 and dash["hostel_checks_today"]==1 and Decimal(dash["fee_outstanding"])==Decimal("600"))
    check("Principal audit details restricted",dash["recent_activity"]==[])
    expect(fin,root+"ledger/activate/",403,"Finance cannot activate ledger",{"confirmed":True})
    expect(a,root+"ledger/activate/",201,"Activate opening receivables",{"confirmed":True})
    ledger=expect(fin,root+"ledger/",200,"Read opening trial balance")
    check("Opening receivables reconcile",ledger["receivable_reconciled"] and Decimal(ledger["fee_outstanding"])==Decimal("600") and Decimal(ledger["statement"]["income"])==0)
    new=expect(fin,root+"operations/fees/",201,"Post new fee to ledger",{"student_id":"QA-STUDENT","period":"QA-NEXT","assessed":"500.00"})
    import uuid
    payload={"account":new["id"],"amount":"200.00","method":"bank","request_key":str(uuid.uuid4())}
    receipt=expect(fin,root+"operations/receipts/",201,"Post new bank receipt",payload)
    retry=expect(fin,root+"operations/receipts/",200,"Retry receipt safely",payload)
    check("Same receipt reference on retry",retry["reference"]==receipt["reference"])
    expect(fin,root+"operations/receipts/",400,"Reject conflicting receipt key",{**payload,"amount":"201.00"})
    ledger=expect(fin,root+"ledger/",200,"Reconcile posted fee movements")
    check("Ledger balanced and receivable INR 900",ledger["balanced"] and ledger["receivable_reconciled"] and Decimal(ledger["fee_outstanding"])==900)
    expect(fac,root+"ledger/",403,"Faculty denied ledger")

    expect(pr,root+"students/QA-STUDENT/admission/",403,"Principal cannot alter admission",{"status":"On Hold"})
    expect(pr,root+"setup/departments/",403,"Principal cannot modify setup")
    expect(fac,root+"operations/fees/",403,"Faculty denied finance")
    expect(fin,root+"operations/attendance/",403,"Finance denied attendance")
    expect(ward,root+"operations/fees/",403,"Warden denied finance")
    expect(view,root+"students/",403,"Viewer cannot create student",dict(student,student_id="QA-DENIED"))
    expect(a,"/api/institutions/gcoea-demo/students/",403,"Cross-institution access denied")
    audit=expect(a,root+"audit/",200,"Administrator audit trail")
    check("Audit records identify departmental actors",all(any(r["actor__username"]==accounts[role]["username"] for r in audit) for role in ("admin","admissions","faculty","finance","warden")))
    for role,c in clients.items():
        expect(c,"/api/csrf/",200,role+" refresh CSRF")
        expect(c,"/api/logout/",200,role+" logout",{})
        check(role+" session terminated",c.request("/api/session/")[1].get("authenticated") is False)

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        failed+=1
        print("STOP | "+str(exc),flush=True)
    finally:
        if created:
            try:
                shell("from django.contrib.auth import get_user_model\nget_user_model().objects.filter(username__in="+repr([a["username"] for a in accounts.values()])+").update(is_active=False)\n")
                print("Temporary QA users disabled. Synthetic evidence retained in "+slug,flush=True)
            except Exception:
                failed+=1
                print("WARNING | Disable temporary QA users with prefix qa_"+run+"_ locally.",flush=True)
        print("RESULT | "+str(passed)+" passed | "+str(failed)+" failed",flush=True)
    sys.exit(1 if failed else 0)
