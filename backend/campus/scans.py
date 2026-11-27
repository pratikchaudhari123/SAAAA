"""Private scanned-page pilot. Images only; bounded decoding and no public media URLs."""
import base64
import binascii
import hashlib
import io
from PIL import Image, UnidentifiedImageError, ImageOps
from django.db import transaction, IntegrityError
from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Institution, AnswerPage, PageAnnotation
from .academic_engine import member, get, parse, log
from .evaluation import scoped

MAX_BYTES=1500000
MAX_PIXELS=8000000

class UploadInput(serializers.Serializer):
    number=serializers.IntegerField(min_value=1,max_value=40)
    image=serializers.CharField(max_length=2000000)
class AnnotationInput(serializers.Serializer):
    x=serializers.IntegerField(min_value=0,max_value=10000)
    y=serializers.IntegerField(min_value=0,max_value=10000)
    note=serializers.CharField(max_length=300)

def normalize(encoded):
    try:
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>MAX_BYTES: raise ValueError()
        with Image.open(io.BytesIO(raw),formats=['JPEG','PNG']) as im:
            if im.width*im.height>MAX_PIXELS or getattr(im,'n_frames',1)!=1: raise ValueError()
            im.load()
            im=ImageOps.exif_transpose(im)
            im=im.convert('RGB')
            # Re-encode rather than retaining original metadata or arbitrary appended bytes.
            out=io.BytesIO()
            im.save(out,format='JPEG',quality=85,optimize=True)
            image=out.getvalue()
            if len(image)>MAX_BYTES: raise ValueError()
            return image,im.width,im.height
    except (ValueError, OSError, SyntaxError, OverflowError, Image.DecompressionBombError, binascii.Error, UnidentifiedImageError):
        raise ValidationError('Use a valid single-page JPEG or PNG, up to 1.5 MB and 8 megapixels.')

def book_for(m,pk):
    return get(scoped(m),pk)

def editable(book):
    return book.application.exam.status=='closed' and book.status in ('assigned','returned')

def check_read(m,book):
    if m.role=='faculty' and not editable(book):
        raise PermissionDenied('Submitted answer pages are restricted to the controller.')

def metadata(page):
    return {'id':page.pk,'number':page.number,'width':page.width,'height':page.height,'sha256':page.sha256}

@api_view(['GET','POST'])
def pages(request,slug,pk):
    m=member(request,slug,['admin','coe','faculty'])
    if request.method=='GET':
        b=book_for(m,pk)
        check_read(m,b)
        response=Response({'expected_pages':b.expected_pages,'status':b.status,'editable':editable(b),'pages':list(b.pages.order_by('number').values('id','number','width','height','sha256'))})
        response['Cache-Control']='private, no-store'
        return response
    if m.role=='faculty': raise PermissionDenied()
    d=parse(UploadInput,request)
    image,width,height=normalize(d['image'])
    try:
        with transaction.atomic():
            Institution.objects.select_for_update().get(pk=m.institution_id)
            b=book_for(m,pk)
            if not editable(b) or b.expected_pages is None or d['number']>b.expected_pages: raise ValidationError('Page outside the declared scan plan or book is locked.')
            digest=hashlib.sha256(image).hexdigest()
            if b.pages.filter(sha256=digest).exists(): raise ValidationError('This normalized image already exists in this book.')
            page=AnswerPage.objects.create(evaluation=b,number=d['number'],image=image,width=width,height=height,sha256=digest,uploaded_by=m.user)
            log(m,'scan.upload',page)
    except IntegrityError:
        raise ValidationError('This page number already exists; original pages are preserved.')
    return Response(metadata(page),status=201)

@api_view(['GET'])
def image_view(request,slug,pk,page_id):
    m=member(request,slug,['admin','coe','faculty'])
    b=book_for(m,pk)
    check_read(m,b)
    page=get(b.pages.all(),page_id)
    response=HttpResponse(bytes(page.image),content_type='image/jpeg')
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    response['Content-Disposition']='inline; filename="answer-page.jpg"'
    return response

@api_view(['GET','POST'])
def annotations(request,slug,pk,page_id):
    m=member(request,slug,['admin','coe','faculty'])
    if request.method=='GET':
        b=book_for(m,pk)
        check_read(m,b)
        page=get(b.pages.all(),page_id)
        response=Response(list(page.annotations.order_by('pk').values('id','x','y','note','created_at')))
        response['Cache-Control']='private, no-store'
        return response
    if m.role!='faculty': raise PermissionDenied()
    d=parse(AnnotationInput,request)
    with transaction.atomic():
        Institution.objects.select_for_update().get(pk=m.institution_id)
        b=book_for(m,pk)
        if not editable(b): raise ValidationError('Submitted or published work is locked.')
        page=get(b.pages.all(),page_id)
        row=PageAnnotation.objects.create(page=page,actor=m.user,**d)
        log(m,'scan.annotation',row)
    return Response({'id':row.pk},status=201)
