from decimal import Decimal
from uuid import uuid4
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Institution,Membership,Student,FeeAccount,FeeReceipt,LedgerJournal
class LedgerTests(TestCase):
    def test_opening_snapshot_and_balanced_posting(self):
        i=Institution.objects.create(name='A',slug='ledger-a')
        j=Institution.objects.create(name='B',slug='ledger-b')
        users={}
        for role in ['admin','finance','faculty','foreign']:
            u=get_user_model().objects.create_user(username='ledger-'+role)
            Membership.objects.create(institution=j if role=='foreign' else i,user=u,role='finance' if role=='foreign' else role)
            users[role]=u
        s=Student.objects.create(institution=i,student_id='S1',name='Synthetic',email='s@example.invalid',program='Engineering',year=1,status='Active')
        a=FeeAccount.objects.create(student=s,period='OLD',assessed=1000)
        FeeReceipt.objects.create(account=a,reference=uuid4(),amount=400,method='cash',recorded_by=users['finance'])
        root='/api/institutions/ledger-a/'
        def post(path,data,status=201):
            r=self.client.post(root+path,data,content_type='application/json')
            self.assertEqual(r.status_code,status,r.content)
            return r.json()
        self.client.force_login(users['finance'])
        post('ledger/activate/',{'confirmed':True},403)
        self.client.force_login(users['admin'])
        post('ledger/activate/',{'confirmed':False},400)
        post('ledger/activate/',{'confirmed':True})
        post('ledger/activate/',{'confirmed':True},400)
        self.client.force_login(users['finance'])
        d=self.client.get(root+'ledger/').json()
        self.assertEqual(Decimal(d['fee_outstanding']),600)
        self.assertEqual(Decimal(d['statement']['assets']),600)
        self.assertTrue(d['receivable_reconciled'])
        new=post('operations/fees/',{'student_id':'S1','period':'NEW','assessed':'500.00'})['id']
        payload={'account':new,'amount':'200.00','method':'bank','request_key':str(uuid4())}
        r=post('operations/receipts/',payload)
        self.assertEqual(post('operations/receipts/',payload,200)['reference'],r['reference'])
        post('operations/receipts/',{**payload,'amount':'201.00'},400)
        post('operations/receipts/',{**payload,'request_key':str(uuid4()),'amount':'301.00'},400)
        manual={'request_key':str(uuid4()),'description':'Synthetic expense','lines':[{'code':'5000','debit':'50.00','credit':'0'},{'code':'1010','debit':'0','credit':'50.00'}]}
        post('ledger/manual/',{**manual,'lines':[manual['lines'][0],{**manual['lines'][1],'credit':'49.00'}]},400)
        post('ledger/manual/',{**manual,'lines':[manual['lines'][0],{**manual['lines'][1],'code':'1100'}]},400)
        post('ledger/manual/',manual)
        post('ledger/manual/',manual,200)
        d=self.client.get(root+'ledger/').json()
        self.assertTrue(d['balanced'])
        self.assertTrue(d['receivable_reconciled'])
        self.assertEqual(Decimal(d['fee_outstanding']),900)
        self.assertEqual(Decimal(d['statement']['income']),500)
        self.assertEqual(Decimal(d['statement']['expenses']),50)
        self.assertEqual(LedgerJournal.objects.count(),4)
        self.assertEqual(FeeReceipt.objects.count(),2)
        for role in ['faculty','foreign']:
            self.client.force_login(users[role])
            self.assertEqual(self.client.get(root+'ledger/').status_code,403)
