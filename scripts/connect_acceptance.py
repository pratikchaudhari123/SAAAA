"""Local synthetic integration acceptance. No existing college records are changed."""
import json
import secrets
import urllib.request
import urllib.error
from datetime import datetime, timezone
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
        qa.expect(c,'/api/institutions/gcoea-demo/connect/events/',403,'Existing college isolated')
        qa.expect(c,'/api/csrf/',200,'Refresh CSRF')
        qa.expect(c,'/api/logout/',200,'Logout',{})
    finally:
        qa.shell("from django.contrib.auth import get_user_model\nfrom campus.models import IntegrationSource\nIntegrationSource.objects.filter(institution__slug="+repr(slug)+").update(active=False)\nget_user_model().objects.filter(username="+repr(username)+").update(is_active=False)\n")
        print('QA user and source disabled; isolated evidence retained: '+slug)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        qa.failed+=1
        print('STOP | '+str(exc))
    print('CONNECT RESULT | '+str(qa.passed)+' passed | '+str(qa.failed)+' failed')
    raise SystemExit(1 if qa.failed else 0)
