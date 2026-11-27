"""Live recruitment acceptance; isolated synthetic institution and disabled QA accounts."""
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo
import live_acceptance as qa

def main():
    tag=secrets.token_hex(5)
    slug='career-qa-'+tag
    username='qa_'+tag+'_admin'
    password=secrets.token_urlsafe(24)
    names=[username]
    clients=[]
    root='/api/institutions/'+slug+'/'
    try:
        qa.shell("from django.contrib.auth import get_user_model\nfrom django.db import transaction\nfrom campus.models import Institution, Membership\nwith transaction.atomic():\n    i=Institution.objects.create(slug="+repr(slug)+",name='Synthetic recruitment QA')\n    u=get_user_model().objects.create_user(username="+repr(username)+",password="+repr(password)+")\n    Membership.objects.create(institution=i,user=u,role='admin')\n")
        def login(creds,label):
            c=qa.Client()
            qa.expect(c,'/api/csrf/',200,label+' CSRF')
            qa.expect(c,'/api/login/',200,label+' login',creds)
            clients.append((label,c))
            return c
        a=login({'username':username,'password':password},'Administrator')
        def post(c,path,payload,label,status=201):
            return qa.expect(c,root+path,status,label,payload)
        def get(c,path,label,status=200):
            return qa.expect(c,root+path,status,label)
        for sid,year in [('QA-SENIOR',4),('QA-JUNIOR',1)]:
            post(a,'students/',{'student_id':sid,'name':sid,'email':sid.lower()+'@example.invalid','program':'Engineering','year':year},'Create '+sid)
            post(a,'students/'+sid+'/admission/',{'status':'Active'},'Approve '+sid,200)
        def provision(role,suffix,student_id=None):
            n='qa_'+tag+'_'+suffix
            names.append(n)
            data={'username':n,'role':role}
            if student_id: data['student_id']=student_id
            info=post(a,'accounts/',data,'Provision '+suffix)
            return login({'username':info['username'],'password':info['password']},suffix)
        t=provision('tpo','tpo')
        c=provision('company','company')
        other=provision('company','other_company')
        s=provision('student','senior','QA-SENIOR')
        junior=provision('student','junior','QA-JUNIOR')
        company=post(c,'careers/company/',{'name':'Synthetic Company','contact_email':'company@example.invalid'},'Register company')['id']
        post(other,'careers/company/',{'name':'Other Company','contact_email':'other@example.invalid'},'Register separate company')
        today=str(datetime.now(ZoneInfo('Asia/Kolkata')).date())
        drive={'company':company,'title':'Synthetic internship','kind':'internship','program':'Engineering','min_year':3,'max_year':4,'deadline':today,'drive_day':today,'instructions':'Synthetic recruitment'}
        post(t,'careers/drive/',drive,'Reject unapproved company',404)
        post(t,'careers/company-review/',{'company':company,'decision':'approved'},'Approve company')
        d=post(t,'careers/drive/',drive,'Publish drive')['id']
        eligible=get(t,'careers/drives/'+str(d)+'/eligible/','Read eligibility list')
        qa.check('Only eligible senior listed',[x['student_id'] for x in eligible]==['QA-SENIOR'])
        qa.check('Junior has no eligible drives',get(junior,'careers/','Junior workspace')['drives']==[])
        post(s,'careers/profile/',{'skills':'SQL','summary':'Synthetic experience'},'Save career profile')
        post(s,'careers/apply/',{'drive':d,'consent':False},'Require sharing consent',400)
        post(junior,'careers/apply/',{'drive':d,'consent':True},'Reject ineligible applicant',400)
        application=post(s,'careers/apply/',{'drive':d,'consent':True},'Apply for internship')['id']
        post(s,'careers/apply/',{'drive':d,'consent':True},'Reject duplicate application',400)
        qa.check('Company sees consented applicant',len(get(c,'careers/','Company applicants')['applications'])==1)
        qa.check('Other company sees no applicants',get(other,'careers/','Other company workspace')['applications']==[])
        get(c,'students/','Company directory denied',403)
        get(c,'careers/drives/'+str(d)+'/eligible/','Company eligibility list denied',403)
        post(t,'careers/close/',{'drive':d},'Close applications')
        post(t,'careers/decision/',{'application':application,'decision':'shortlisted'},'Shortlist applicant')
        post(t,'careers/decision/',{'application':application,'decision':'selected'},'Select applicant')
        qa.check('Student sees selected status',get(s,'careers/','Student status')['applications'][0]['status']=='selected')
        qa.check('TPO sees one internship selection',get(t,'careers/','Placement report')['internship_count']==1)
        get(t,'students/','Placement staff general directory denied',403)
        qa.expect(t,'/api/institutions/gcoea-demo/careers/',403,'Existing college isolated')
        for label,client in clients:
            qa.expect(client,'/api/csrf/',200,label+' refresh CSRF')
            qa.expect(client,'/api/logout/',200,label+' logout',{})
    finally:
        qa.shell("from django.contrib.auth import get_user_model\nget_user_model().objects.filter(username__in="+repr(names)+").update(is_active=False)\n")
        print('Temporary accounts disabled; synthetic evidence retained: '+slug)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        qa.failed+=1
        print('STOP | '+str(exc))
    print('CAREER RESULT | '+str(qa.passed)+' passed | '+str(qa.failed)+' failed')
    raise SystemExit(1 if qa.failed else 0)
