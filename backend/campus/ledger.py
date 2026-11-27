"""Controlled opening receivables, balanced journals and fee posting. Evaluation accounting."""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Institution, FeeAccount, LedgerConfiguration, LedgerAccount, LedgerJournal, LedgerLine
from .academic_engine import member, parse, log

ZERO=Decimal('0.00')
CHART=[('1000','Cash','asset'),('1010','Bank','asset'),('1100','Student fees receivable','asset'),('2000','Accounts payable','liability'),('3000','Opening balance equity','equity'),('4000','Student fee income','income'),('4100','Other income','income'),('5000','General expense','expense')]
PROTECTED={'1100','3000','4000'}

def active(i):
    return LedgerConfiguration.objects.filter(institution=i).exists()

def post(i,user,source,description,lines,day=None):
    """Call inside a transaction holding the institution row lock."""
    if len(lines)<2 or len({code for code,_,_ in lines})!=len(lines):
        raise ValidationError('Use at least two distinct ledger accounts.')
    if any(not ((dr>0 and cr==0) or (cr>0 and dr==0)) for _,dr,cr in lines):
        raise ValidationError('Each line requires one positive side.')
    if sum(dr for _,dr,_ in lines)!=sum(cr for _,_,cr in lines):
        raise ValidationError('Journal debits and credits must balance.')
    accounts={a.code:a for a in LedgerAccount.objects.filter(institution=i,code__in=[code for code,_,_ in lines])}
    if len(accounts)!=len(lines): raise ValidationError('Unknown ledger account.')
    journal=LedgerJournal.objects.create(institution=i,actor=user,source_key=source,description=description,day=day or timezone.localdate())
    LedgerLine.objects.bulk_create([LedgerLine(journal=journal,account=accounts[code],debit=dr,credit=cr) for code,dr,cr in lines])
    return journal

def assess(m,account):
    if active(m.institution):
        post(m.institution,m.user,'fee:'+str(account.pk),'Fee assessment '+account.student.student_id,[('1100',account.assessed,ZERO),('4000',ZERO,account.assessed)])

def receive(m,receipt):
    if active(m.institution):
        post(m.institution,m.user,'receipt:'+str(receipt.reference),'Fee receipt '+str(receipt.reference),[('1000' if receipt.method=='cash' else '1010',receipt.amount,ZERO),('1100',ZERO,receipt.amount)])

class Activate(serializers.Serializer):
    confirmed=serializers.BooleanField()
class Line(serializers.Serializer):
    code=serializers.CharField(max_length=30)
    debit=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=ZERO)
    credit=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=ZERO)
class Manual(serializers.Serializer):
    request_key=serializers.UUIDField()
    description=serializers.CharField(max_length=300)
    lines=Line(many=True,min_length=2,max_length=20)

@api_view(['GET'])
def workspace(request,slug):
    m=member(request,slug,['admin','finance'])
    i=m.institution
    config=LedgerConfiguration.objects.filter(institution=i).first()
    rows=[]
    total_dr=ZERO;total_cr=ZERO;assets=ZERO;liabilities=ZERO;equity=ZERO;income=ZERO;expenses=ZERO
    for a in LedgerAccount.objects.filter(institution=i).order_by('code'):
        sums=LedgerLine.objects.filter(account=a,journal__institution=i).aggregate(dr=Sum('debit'),cr=Sum('credit'))
        dr=sums['dr'] or ZERO;cr=sums['cr'] or ZERO
        net=dr-cr;total_dr+=dr;total_cr+=cr
        if a.category=='asset': assets+=net
        elif a.category=='liability': liabilities-=net
        elif a.category=='equity': equity-=net
        elif a.category=='income': income-=net
        elif a.category=='expense': expenses+=net
        rows.append({'code':a.code,'name':a.name,'category':a.category,'debit':str(dr),'credit':str(cr),'balance':str(net)})
    fees=FeeAccount.objects.filter(student__institution=i)
    outstanding=(fees.aggregate(v=Sum('assessed'))['v'] or ZERO)
    from .models import FeeReceipt
    outstanding-=FeeReceipt.objects.filter(account__in=fees).aggregate(v=Sum('amount'))['v'] or ZERO
    ar=next((Decimal(r['balance']) for r in rows if r['code']=='1100'),ZERO)
    journals=LedgerJournal.objects.filter(institution=i).order_by('-pk').prefetch_related('lines__account')[:100]
    response=Response({'active':bool(config),'activated_at':config.activated_at if config else None,'accounts':rows,'total_debit':str(total_dr),'total_credit':str(total_cr),'balanced':total_dr==total_cr,'fee_outstanding':str(outstanding),'receivable_reconciled':bool(config and ar==outstanding),'statement':{'assets':str(assets),'liabilities':str(liabilities),'opening_equity':str(equity),'income':str(income),'expenses':str(expenses),'surplus':str(income-expenses)},'journals':[{'reference':str(j.reference),'day':j.day,'description':j.description,'source':j.source_key,'lines':[{'code':l.account.code,'debit':str(l.debit),'credit':str(l.credit)} for l in j.lines.all()]} for j in journals]})
    response['Cache-Control']='private, no-store'
    return response

@api_view(['POST'])
def activate(request,slug):
    m=member(request,slug,['admin'])
    d=parse(Activate,request)
    if not d['confirmed']: raise ValidationError('Confirm the opening receivables snapshot.')
    with transaction.atomic():
        i=Institution.objects.select_for_update().get(pk=m.institution_id)
        if active(i): raise ValidationError('Ledger already activated.')
        LedgerAccount.objects.bulk_create([LedgerAccount(institution=i,code=c,name=n,category=k) for c,n,k in CHART])
        fees=FeeAccount.objects.filter(student__institution=i).select_related('student').annotate(paid=Sum('receipts__amount'))
        for fee in fees:
            due=fee.assessed-(fee.paid or ZERO)
            if due<0: raise ValidationError('Overpaid existing account requires reconciliation.')
            if due>0:
                post(i,m.user,'opening:'+str(fee.pk),'Opening outstanding '+fee.student.student_id,[('1100',due,ZERO),('3000',ZERO,due)])
        row=LedgerConfiguration.objects.create(institution=i,activated_by=m.user)
        log(m,'ledger.activate',row)
    return Response({'id':row.pk},status=201)

@api_view(['POST'])
def manual(request,slug):
    m=member(request,slug,['admin','finance'])
    d=parse(Manual,request)
    lines=[(r['code'],r['debit'],r['credit']) for r in d['lines']]
    if any(code in PROTECTED for code,_,_ in lines): raise ValidationError('Protected fee and opening accounts require system transactions.')
    with transaction.atomic():
        i=Institution.objects.select_for_update().get(pk=m.institution_id)
        if not active(i): raise ValidationError('Activate ledger before posting.')
        key='manual:'+str(d['request_key'])
        old=LedgerJournal.objects.filter(institution=i,source_key=key).first()
        if old:
            recorded=sorted(old.lines.values_list('account__code','debit','credit'))
            if old.description!=d['description'] or recorded!=sorted(lines): raise ValidationError('Request key already used for another journal.')
            return Response({'reference':str(old.reference),'duplicate':True})
        row=post(i,m.user,key,d['description'],lines)
        log(m,'ledger.manual',row)
    return Response({'reference':str(row.reference),'duplicate':False},status=201)
