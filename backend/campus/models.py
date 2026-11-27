from django.db import models
from django.conf import settings
class Institution(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
class Membership(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    role = models.CharField(max_length=30,choices=[('admin','Administrator'),('admissions','Admission Officer'),('viewer','Read only')])
    class Meta:
        constraints = [models.UniqueConstraint(fields=['institution','user'],name='unique_campus_member')]
class Student(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.PROTECT)
    student_id = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    program = models.CharField(max_length=150)
    year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20,choices=[('Active','Active'),('Pending','Pending'),('On Hold','On Hold')],default='Pending')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['institution','student_id'],name='unique_campus_student')]
class AuditEvent(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    action = models.CharField(max_length=50)
    target = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
