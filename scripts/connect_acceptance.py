"""Local synthetic integration acceptance. No existing college records are changed."""
import json
import secrets
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import live_acceptance as qa

def send(token,payload):
    req=urllib.request.Request(qa.BASE+'/api/connect/events/',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            return response.status,json.loads(response.read())
    except urllib.error.HTTPError as response:
        return response.code,{}

def main():
    slug='connect-qa-'+secrets.token_hex(5)
    username='qa_'+slug.replace('-','_')
    password=secrets.token_urlsafe(24)
    staff_name=username+'_faculty'
    principal_name=username+'_principal'
    try:
        qa.shell("from django.contrib.auth import get_user_model\nfrom django.db import transaction\nfrom campus.models import Institution, Membership\nwith transaction.atomic():\n    i=Institution.objects.create(slug="+repr(slug)+",name='Synthetic integration acceptance')\n    u=get_user_model().objects.create_user(username="+repr(username)+",password="+repr(password)+")\n    Membership.objects.create(institution=i,user=u,role='admin')\n")
        c=qa.Client()
        qa.expect(c,'/api/csrf/',200,'CSRF')
        qa.expect(c,'/api/login/',200,'Administrator login',{'username':username,'password':password})
        base='/api/institutions/'+slug+'/connect/'
        source=qa.expect(c,base+'sources/',201,'Register isolated device',{'name':'Synthetic gateway','purpose':'hostel'})
        event={'external_id':'QA-001','subject_ref':'STUDENT-001','event_type':'in','occurred_at':datetime.now(timezone.utc).isoformat()}
        qa.check('Machine event accepted',send(source['token'],event)[0]==201)
        qa.check('Duplicate retry acknowledged',send(source['token'],event)[0]==200)
        qa.check('Conflicting retry rejected',send(source['token'],dict(event,event_type='out'))[0]==409)
        qa.check('Invalid token denied',send('invalid',event)[0]==401)
        events=qa.expect(c,base+'events/',200,'Read persisted inbox')
        qa.check('Exactly one staged event',events['total']==1 and events['events'][0]['subject_ref']=='STUDENT-001')
        qa.expect(c,base+'sources/'+str(source['id'])+'/action/',200,'Disable source',{'action':'disable'})
        qa.check('Disabled source denied',send(source['token'],event)[0]==401)
        raw='student_id,name,email,program,year\nQA-IMPORT,Example Student,example@example.invalid,Engineering,1\n'
        p=qa.expect(c,base+'student-import/',200,'Preview import',{'mode':'preview','csv':raw})
        qa.check('One new record in preview',p['new_rows']==1 and not p['errors'])
        rows=qa.expect(c,'/api/institutions/'+slug+'/students/',200,'Directory before import')
        qa.check('Preview does not write records',len(rows)==0)
        qa.expect(c,base+'student-import/',201,'Apply import',{'mode':'apply','csv':raw,'file_digest':p['file_digest']})
        rows=qa.expect(c,'/api/institutions/'+slug+'/students/',200,'Directory after import')
        qa.check('Imported record persisted as Pending',len(rows)==1 and rows[0]['student_id']=='QA-IMPORT' and rows[0]['status']=='Pending')
        p=qa.expect(c,base+'student-import/',200,'Recheck same export',{'mode':'preview','csv':raw})
        qa.check('Existing record skipped',p['new_rows']==0 and p['existing_rows']==1)
        qa.expect(c,base+'import-history/',200,'Import audit history')
        root='/api/institutions/'+slug+'/'
        def post(client,path,data,label,status=201):
            return qa.expect(client,root+path,status,label,data)
        def get(client,path,label,status=200):
            return qa.expect(client,root+path,status,label)
        clients={}
        for role,name in [('faculty',staff_name),('principal',principal_name)]:
            credential=post(c,'accounts/',{'username':name,'role':role},'Provision '+role)
            client=qa.Client()
            qa.expect(client,'/api/csrf/',200,role+' CSRF')
            qa.expect(client,'/api/login/',200,role+' login',{'username':credential['username'],'password':credential['password']})
            clients[role]=client
        faculty,principal=clients['faculty'],clients['principal']
        department=post(c,'setup/departments/',{'code':'HR-QA','name':'QA Administration'},'Create employee department')['id']
        info=get(c,'hr/','Read employee account choices')
        membership=next(r['id'] for r in info['accounts'] if r['user__username']==staff_name)
        today=datetime.now(ZoneInfo('Asia/Kolkata')).date()
        employee=post(c,'hr/employee/',{'code':'QA-E1','name':'Synthetic Employee','designation':'Lecturer','category':'teaching','department':department,'membership':membership,'joined_on':str(today-timedelta(days=5))},'Register employee')['id']
        device=post(c,'connect/sources/',{'name':'Synthetic employee gate','purpose':'employee'},'Register employee device')
        before={'external_id':'EMP-OLD','subject_ref':'OPAQUE-E1','event_type':'in','occurred_at':datetime.now(timezone.utc).isoformat()}
        status,body=send(device['token'],before)
        qa.check('Unmapped employee event stays staged',status==201 and body.get('status')=='staged')
        post(c,'hr/map/',{'employee':employee,'source':device['id'],'subject_ref':'OPAQUE-E1'},'Map employee identity')
        event={'external_id':'EMP-IN','subject_ref':'OPAQUE-E1','event_type':'in','occurred_at':datetime.now(timezone.utc).isoformat()}
        status,body=send(device['token'],event)
        qa.check('Mapped punch posted immediately',status==201 and body.get('status')=='employee_punch')
        status,body=send(device['token'],event)
        qa.check('Retry does not create another punch',status==200 and body.get('duplicate') is True)
        status,body=send(device['token'],{**event,'external_id':'EMP-OUT','event_type':'out','occurred_at':datetime.now(timezone.utc).isoformat()})
        qa.check('Mapped exit posted immediately',status==201 and body.get('status')=='employee_punch')
        profile=get(faculty,'hr/','Faculty employee self-service')
        qa.check('Only two mapped punches, not historic staged event',len(profile['punches'])==2 and {r['event__event_type'] for r in profile['punches']}=={'in','out'} and all(r['employee__code']=='QA-E1' for r in profile['punches']))
        leave={'category':'Casual','starts':str(today),'ends':str(today+timedelta(days=1)),'reason':'Synthetic leave'}
        lid=post(faculty,'hr/leave/',leave,'Submit leave request')['id']
        post(faculty,'hr/leave/',leave,'Reject overlapping leave',400)
        post(faculty,'hr/review/',{'leave':lid,'decision':'approved'},'Employee cannot approve own request',403)
        post(principal,'hr/review/',{'leave':lid,'decision':'approved'},'Principal approves leave')
        qa.check('Approved status visible to employee',get(faculty,'hr/','Refresh leave history')['leaves'][0]['status']=='approved')
        for role,client in clients.items():
            qa.expect(client,'/api/csrf/',200,role+' refresh CSRF')
            qa.expect(client,'/api/logout/',200,role+' logout',{})
        qa.expect(c,'/api/institutions/gcoea-demo/connect/events/',403,'Existing college isolated')
        qa.expect(c,'/api/csrf/',200,'Refresh CSRF')
        qa.expect(c,'/api/logout/',200,'Logout',{})
    finally:
        qa.shell("from django.contrib.auth import get_user_model\nfrom campus.models import IntegrationSource\nIntegrationSource.objects.filter(institution__slug="+repr(slug)+").update(active=False)\nget_user_model().objects.filter(username__in="+repr([username,staff_name,principal_name])+").update(is_active=False)\n")
        print('QA user and source disabled; isolated evidence retained: '+slug)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        qa.failed+=1
        print('STOP | '+str(exc))
    print('CONNECT RESULT | '+str(qa.passed)+' passed | '+str(qa.failed)+' failed')
    raise SystemExit(1 if qa.failed else 0)
