"""Live permission and document evaluation acceptance using isolated synthetic records."""
from datetime import datetime,timedelta,timezone
import secrets
import live_acceptance as qa

def main():
    tag=secrets.token_hex(5)
    slug='document-qa-'+tag
    name='qa_'+tag+'_admin'
    password=secrets.token_urlsafe(24)
    names=[name]
    clients=[]
    root='/api/institutions/'+slug+'/'
    try:
        qa.shell("from django.contrib.auth import get_user_model\nfrom django.db import transaction\nfrom campus.models import Institution, Membership\nwith transaction.atomic():\n    i=Institution.objects.create(slug="+repr(slug)+",name='Synthetic document QA')\n    u=get_user_model().objects.create_user(username="+repr(name)+",password="+repr(password)+")\n    Membership.objects.create(institution=i,user=u,role='admin')\n")
        def login(credentials,label):
            c=qa.Client()
            qa.expect(c,'/api/csrf/',200,label+' CSRF')
            qa.expect(c,'/api/login/',200,label+' login',credentials)
            clients.append((label,c))
            return c
        a=login({'username':name,'password':password},'Administrator')
        def post(c,path,data,label,status=201):
            return qa.expect(c,root+path,status,label,data)
        def get(c,path,label,status=200):
            return qa.expect(c,root+path,status,label)
        for sid in ['QA-ONE','QA-TWO']:
            post(a,'students/',{'student_id':sid,'name':sid,'email':sid.lower()+'@example.invalid','program':'Engineering','year':1},'Create '+sid)
            post(a,'students/'+sid+'/admission/',{'status':'Active'},'Approve '+sid,200)
        def provision(role,suffix,student_id=None):
            username='qa_'+tag+'_'+suffix
            names.append(username)
            payload={'username':username,'role':role}
            if student_id: payload['student_id']=student_id
            info=post(a,'accounts/',payload,'Provision '+suffix)
            return login({'username':info['username'],'password':info['password']},suffix),username
        student,_=provision('student','student','QA-ONE')
        other,_=provision('student','other','QA-TWO')
        faculty,faculty_name=provision('faculty','faculty')
        finance,_=provision('finance','finance')
        principal,_=provision('principal','principal')
        policy=post(a,'documents/policy/',{'code':'QA-BON','kind':'bonafide','title':'Synthetic bonafide','text':'Student {student_name} at {institution}.','allow_duplicate':True,'clearance_units':['finance']},'Configure certificate policy')['id']
        parent=post(a,'permissions/role/',{'name':'Report reader','permissions':['document.report']},'Create base custom role')['id']
        role=post(a,'permissions/role/',{'name':'Temporary issuer','parent':parent,'permissions':['document.issue']},'Create inherited role')['id']
        member_id=next(r['id'] for r in get(a,'permissions/','Read staff assignment choices')['members'] if r['user__username']==faculty_name)
        fee=post(finance,'operations/fees/',{'student_id':'QA-ONE','period':'QA','assessed':'100.00'},'Assess synthetic fee')['id']
        post(student,'documents/apply/',{'policy':policy,'copy_kind':'duplicate','reason':'Test duplicate'},'Duplicate without original denied',400)
        req=post(student,'documents/apply/',{'policy':policy,'copy_kind':'original','reason':'Synthetic evaluation'},'Submit student certificate request')['id']
        qa.check('Other student sees no requests',get(other,'documents/','Other student workspace')['requests']==[])
        review={'id':req,'decision':'issued','note':'Synthetic approval','confirmed':True}
        post(faculty,'documents/review/',review,'Unassigned staff cannot issue',403)
        post(a,'documents/review/',review,'Incomplete clearance blocks issuance',400)
        clearance={'id':req,'unit':'finance','cleared':True,'note':'Synthetic reconciliation'}
        post(finance,'documents/clearance/',clearance,'Outstanding fees block clearance',400)
        post(finance,'operations/receipts/',{'account':fee,'amount':'100.00','method':'bank'},'Settle synthetic fee')
        post(finance,'documents/clearance/',clearance,'Record verified finance clearance')
        now=datetime.now(timezone.utc)
        grant=post(a,'permissions/grant/',{'role':role,'membership':member_id,'starts':(now-timedelta(minutes=1)).isoformat(),'ends':(now+timedelta(minutes=20)).isoformat(),'reason':'Synthetic temporary duty'},'Delegate issuance')['id']
        caps=get(faculty,'documents/','Delegated workspace')['capabilities']
        qa.check('Inherited and explicit permissions effective',set(caps)=={'document.issue','document.report'})
        post(faculty,'documents/review/',review,'Issue through delegated permission')
        issued=get(student,'documents/','Student issued document')['requests'][0]
        qa.check('Issued serial and rendered snapshot',issued['status']=='issued' and bool(issued['serial']) and issued['issued']['text']=='Student QA-ONE at Synthetic document QA.')
        qa.check('Non-financial certificate has no fee amounts','fee_assessed' not in issued['issued'])
        qa.check('Report-only principal sees no document snapshot',get(principal,'documents/','Principal document register')['requests'][0]['issued'] is None)
        duplicate=post(student,'documents/apply/',{'policy':policy,'copy_kind':'duplicate','reason':'Synthetic replacement'},'Request permitted duplicate')['id']
        post(finance,'documents/clearance/',{**clearance,'id':duplicate},'Clear duplicate')
        post(a,'documents/review/',{**review,'id':duplicate},'Issue duplicate')
        records=get(student,'documents/','Student original and duplicate')['requests']
        dup=next(r for r in records if r['copy_kind']=='duplicate')
        qa.check('Duplicate linked to original serial',dup['issued']['original_serial']==issued['serial'])
        post(a,'permissions/revoke/',{'id':grant},'Revoke delegated permission')
        post(faculty,'documents/review/',{'id':req,'decision':'revoked','note':'Denied'},'Revoked delegate cannot change document',403)
        post(a,'documents/review/',{'id':req,'decision':'revoked','note':'Synthetic revocation'},'Authorized revocation')
        qa.check('Revoked document snapshot hidden',next(r for r in get(student,'documents/','Revoked student record')['requests'] if r['id']==req)['issued'] is None)
        qa.expect(faculty,'/api/institutions/gcoea-demo/documents/',403,'Existing college isolated')
        for label,c in clients:
            qa.expect(c,'/api/csrf/',200,label+' refresh CSRF')
            qa.expect(c,'/api/logout/',200,label+' logout',{})
    finally:
        qa.shell("from django.contrib.auth import get_user_model\nget_user_model().objects.filter(username__in="+repr(names)+").update(is_active=False)\n")
        print('Temporary accounts disabled; synthetic evidence retained: '+slug)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        qa.failed+=1
        print('STOP | '+str(exc))
    print('DOCUMENT RESULT | '+str(qa.passed)+' passed | '+str(qa.failed)+' failed')
    raise SystemExit(1 if qa.failed else 0)
