"""Exercise the real academic/exam APIs with disposable synthetic accounts.
Run on the existing developer stack: python3 scripts/academic_acceptance.py
No GCOEA or team demonstration records are modified.
"""
import datetime as dt
import secrets
from zoneinfo import ZoneInfo
import live_acceptance as qa

def main():
    tag=secrets.token_hex(5)
    slug='academic-qa-'+tag
    roles=('admin','faculty','coe','student','viewer','principal')
    accounts={r:{'username':'qa_'+tag+'_'+r,'password':secrets.token_urlsafe(24)} for r in roles}
    accounts['other_faculty']={'username':'qa_'+tag+'_other_faculty','password':secrets.token_urlsafe(24)}
    clients={}
    root='/api/institutions/'+slug+'/'
    today=dt.datetime.now(ZoneInfo('Asia/Kolkata')).date()
    try:
        qa.shell("from django.contrib.auth import get_user_model\nfrom django.db import transaction\nfrom campus.models import Institution, Membership\nwith transaction.atomic():\n    i=Institution.objects.create(slug="+repr(slug)+",name='Synthetic academic acceptance')\n    for role,a in "+repr({r:a for r,a in accounts.items() if r!='student'})+".items():\n        u=get_user_model().objects.create_user(username=a['username'],password=a['password'])\n        Membership.objects.create(institution=i,user=u,role='faculty' if role=='other_faculty' else role)\n")
        for role, account in accounts.items():
            if role=='student': continue
            c=qa.Client()
            qa.expect(c,'/api/csrf/',200,role+' CSRF')
            qa.expect(c,'/api/login/',200,role+' login',account)
            clients[role]=c
        a,f,coe,v,p,other=[clients[r] for r in ('admin','faculty','coe','viewer','principal','other_faculty')]
        def post(c,path,data,label,status=201):
            return qa.expect(c,root+path,status,label,data)
        def get(c,path,label,status=200):
            return qa.expect(c,root+path,status,label)
        dept=post(a,'setup/departments/',{'code':'QA','name':'Computing'},'Create department')['id']
        prog=post(a,'setup/programs/',{'code':'QA-BE','name':'QA Engineering','department':dept,'duration_years':4,'intake':60},'Create program')['id']
        course=post(a,'setup/courses/',{'code':'QA101','name':'Programming','program':prog,'semester':1,'credits':3},'Create course')['id']
        period=post(a,'setup/periods/',{'code':'QA-TERM','starts':str(today-dt.timedelta(days=10)),'ends':str(today+dt.timedelta(days=10))},'Create period')['id']
        for sid in ('QA-ONE','QA-TWO'):
            post(a,'students/',{'student_id':sid,'name':sid,'email':sid.lower()+'@example.invalid','program':'QA Engineering','year':1,'status':'Pending'},'Create '+sid)
            post(a,'students/'+sid+'/admission/',{'status':'Active'},'Approve '+sid,200)
        account=post(a,'accounts/',{'username':accounts['student']['username'],'role':'student','student_id':'QA-ONE'},'Provision student login through administrator API')
        accounts['student']['password']=account['password']
        s=qa.Client()
        qa.expect(s,'/api/csrf/',200,'student CSRF')
        qa.expect(s,'/api/login/',200,'student login',accounts['student'])
        clients['student']=s
        get(s,'accounts/','Student denied account management',403)
        masters=get(a,'academic-engine/','Read academic master choices')
        faculty=next(r['id'] for r in masters['faculty'] if r['user__username']==accounts['faculty']['username'])
        room=post(a,'academic-engine/room/',{'code':'QA-R1','capacity':10},'Create classroom')['id']
        o=post(a,'academic-engine/offering/',{'course':course,'period':period,'faculty':faculty,'batch':'A'},'Assign course')['id']
        e=post(a,'academic-engine/enrollment/',{'offering':o,'student_id':'QA-ONE'},'Enroll first student')['id']
        e2=post(a,'academic-engine/enrollment/',{'offering':o,'student_id':'QA-TWO'},'Enroll second student')['id']
        ids=[]
        for hour in (9,10):
            start=dt.datetime.combine(today-dt.timedelta(days=1),dt.time(hour),tzinfo=ZoneInfo('Asia/Kolkata'))
            payload={'offering':o,'room':room,'starts':start.isoformat(),'ends':(start+dt.timedelta(minutes=45)).isoformat()}
            ids.append(post(a,'academic-engine/session/',payload,'Schedule lecture')['id'])
            post(a,'academic-engine/session/',payload,'Reject overlapping lecture',400)
        qa.check('Unassigned faculty sees no offerings',get(other,'academic-engine/','Unassigned faculty workspace')['offerings']==[])
        post(other,'academic-engine/attendance/',{'session':ids[0],'enrollment':e,'present':True},'Unassigned faculty denied',404)
        for session in ids:
            post(f,'academic-engine/attendance/',{'session':session,'enrollment':e,'present':True},'Record present')
            post(f,'academic-engine/attendance/',{'session':session,'enrollment':e2,'present':False},'Record absent')
        data=get(s,'academic-engine/','Student reads own academic records')
        qa.check('Student sees only own enrollment and two lectures',len(data['enrollments'])==1 and len(data['attendance'])==2 and all(r['present'] for r in data['attendance']))
        get(s,'students/','Student denied institution-wide directory',403)
        get(v,'academic-engine/','Viewer denied academic workspace',403)
        profile=get(s,'my-campus/','Student personal portal')
        qa.check('Student personal identity correct',profile['profile']['student_id']=='QA-ONE')
        config={'offering':o,'title':'QA Examination','kind':'regular','day':str(today),'maximum':100,'passing':40,'min_attendance':75}
        exam=post(coe,'examination/create/',config,'Configure examination')['id']
        post(coe,'examination/apply/',{'exam':exam,'enrollment':e2},'Reject insufficient attendance',400)
        post(s,'examination/apply/',{'exam':exam,'enrollment':e2},'Reject another student application',404)
        app=post(s,'examination/apply/',{'exam':exam,'enrollment':e},'Student applies')['id']
        post(s,'examination/apply/',{'exam':exam,'enrollment':e},'Reject duplicate application',400)
        post(s,'examination/marks/',{'application':app,'marks':90},'Student cannot enter marks',403)
        post(coe,'examination/state/',{'exam':exam,'status':'closed'},'Close application window')
        post(coe,'examination/state/',{'exam':exam,'status':'published'},'Reject incomplete result publication',400)
        post(coe,'examination/marks/',{'application':app,'marks':101},'Reject excess marks',400)
        post(coe,'examination/marks/',{'application':app,'marks':84},'Save marks')
        qa.check('Unpublished marks hidden',get(s,'examination/','Student checks unpublished result')['applications'][0]['marks'] is None)
        post(coe,'examination/state/',{'exam':exam,'status':'published'},'Publish result')
        results=get(s,'examination/','Student reads published result')['applications']
        qa.check('Published result is 84/100 Pass',len(results)==1 and results[0]['marks']==84 and results[0]['result']=='Pass')
        post(coe,'examination/marks/',{'application':app,'marks':10},'Published marks locked',400)
        dashboard=get(p,'dashboard/','Principal dashboard')
        qa.check('Principal sees one published examination',dashboard['published_exams']==1)
        qa.expect(a,'/api/institutions/gcoea-demo/academic-engine/',403,'Existing institution isolated')
        for role,c in clients.items():
            qa.expect(c,'/api/csrf/',200,role+' refresh CSRF')
            qa.expect(c,'/api/logout/',200,role+' logout',{})
            qa.check(role+' session ended',c.request('/api/session/')[1].get('authenticated') is False)
    finally:
        qa.shell("from django.contrib.auth import get_user_model\nget_user_model().objects.filter(username__in="+repr([a['username'] for a in accounts.values()])+").update(is_active=False)\n")
        print('Temporary accounts disabled. Evidence retained in '+slug)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        qa.failed+=1
        print('STOP | '+str(exc))
    print('ACADEMIC RESULT | '+str(qa.passed)+' passed | '+str(qa.failed)+' failed')
    raise SystemExit(1 if qa.failed else 0)
