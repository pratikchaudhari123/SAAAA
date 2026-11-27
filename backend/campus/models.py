from django.db import models
from django.conf import settings
class Institution(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
class Membership(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    role = models.CharField(max_length=30,choices=[('admin','Administrator'),('admissions','Admission Officer'),('viewer','Read only'),('faculty','Faculty'),('finance','Finance Officer'),('warden','Hostel Warden'),('principal','Principal')])
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

class AttendanceEntry(models.Model):
    student = models.ForeignKey(Student,on_delete=models.PROTECT)
    day = models.DateField()
    course = models.CharField(max_length=100)
    present = models.BooleanField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['student','day','course'],name='unique_attendance_session')]

class FeeAccount(models.Model):
    student = models.ForeignKey(Student,on_delete=models.PROTECT)
    period = models.CharField(max_length=20)
    assessed = models.DecimalField(max_digits=12,decimal_places=2)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['student','period'],name='unique_fee_period'),models.CheckConstraint(condition=models.Q(assessed__gt=0),name='positive_assessed_fee')]

class FeeReceipt(models.Model):
    account = models.ForeignKey(FeeAccount,on_delete=models.PROTECT,related_name='receipts')
    reference = models.UUIDField(unique=True)
    amount = models.DecimalField(max_digits=12,decimal_places=2)
    method = models.CharField(max_length=20,choices=[('cash','Cash'),('bank','Bank transfer')])
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0),name='positive_fee_receipt')]

class HostelBed(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.PROTECT)
    code = models.CharField(max_length=50)
    student = models.OneToOneField(Student,on_delete=models.PROTECT,null=True,blank=True)
    usable = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['institution','code'],name='unique_hostel_bed')]

class HostelCheck(models.Model):
    bed = models.ForeignKey(HostelBed,on_delete=models.PROTECT)
    student = models.ForeignKey(Student,on_delete=models.PROTECT)
    day = models.DateField()
    status = models.CharField(max_length=20,choices=[('present','Present'),('absent','Absent'),('leave','Approved leave reported')])
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['student','day'],name='unique_hostel_daily_student')]

class Department(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.PROTECT)
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['institution','code'],name='unique_department_code')]

class AcademicProgram(models.Model):
    department = models.ForeignKey(Department,on_delete=models.PROTECT)
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    duration_years = models.PositiveSmallIntegerField()
    intake = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['department','code'],name='unique_program_code')]

class AcademicCourse(models.Model):
    program = models.ForeignKey(AcademicProgram,on_delete=models.PROTECT)
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    semester = models.PositiveSmallIntegerField()
    credits = models.PositiveSmallIntegerField()
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['program','code'],name='unique_course_code')]

class AcademicPeriod(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.PROTECT)
    code = models.CharField(max_length=20)
    starts = models.DateField()
    ends = models.DateField()
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['institution','code'],name='unique_academic_period'),models.CheckConstraint(condition=models.Q(ends__gte=models.F('starts')),name='valid_academic_period')]
