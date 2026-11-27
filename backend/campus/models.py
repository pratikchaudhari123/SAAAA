import uuid
from django.db import models
from django.conf import settings
class Institution(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
class Membership(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    role = models.CharField(max_length=30,choices=[('admin','Administrator'),('admissions','Admission Officer'),('viewer','Read only'),('faculty','Faculty'),('finance','Finance Officer'),('warden','Hostel Warden'),('principal','Principal'),('student','Student'),('coe','Examination Controller')])
    class Meta:
        constraints = [models.UniqueConstraint(fields=['institution','user'],name='unique_campus_member')]
class Student(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.PROTECT)
    portal_user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True,related_name='campus_student_profiles')
    student_id = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    program = models.CharField(max_length=150)
    year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20,choices=[('Active','Active'),('Pending','Pending'),('On Hold','On Hold')],default='Pending')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['institution','student_id'],name='unique_campus_student'),models.UniqueConstraint(fields=['institution','portal_user'],name='unique_student_portal_user')]
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

class IntegrationSource(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    purpose = models.CharField(max_length=20,choices=[('classroom','Classroom'),('employee','Employee'),('exam','Examination'),('hostel','Hostel')])
    token_digest = models.CharField(max_length=64,unique=True,editable=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_received_at = models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['institution','name'],name='unique_integration_source_name')]

class IntegrationEvent(models.Model):
    source = models.ForeignKey(IntegrationSource,on_delete=models.PROTECT,related_name='events')
    external_id = models.CharField(max_length=100)
    subject_ref = models.CharField(max_length=100)
    event_type = models.CharField(max_length=20,choices=[('attendance','Attendance'),('in','Entry'),('out','Exit')])
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['source','external_id'],name='unique_integration_event')]
        indexes = [models.Index(fields=['source','-received_at'],name='integration_received_idx')]

class StudentImportBatch(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    row_count = models.PositiveIntegerField()
    created_count = models.PositiveIntegerField()
    skipped_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class Classroom(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    code=models.CharField(max_length=40)
    capacity=models.PositiveIntegerField()
    class Meta:
        constraints=[models.UniqueConstraint(fields=['institution','code'],name='unique_classroom_code')]

class CourseOffering(models.Model):
    course=models.ForeignKey(AcademicCourse,on_delete=models.PROTECT)
    period=models.ForeignKey(AcademicPeriod,on_delete=models.PROTECT)
    batch=models.CharField(max_length=40)
    faculty=models.ForeignKey(Membership,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['course','period','batch'],name='unique_course_offering')]

class CourseEnrollment(models.Model):
    offering=models.ForeignKey(CourseOffering,on_delete=models.PROTECT,related_name='enrollments')
    student=models.ForeignKey(Student,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['offering','student'],name='unique_course_enrollment')]

class LectureSession(models.Model):
    offering=models.ForeignKey(CourseOffering,on_delete=models.PROTECT)
    room=models.ForeignKey(Classroom,on_delete=models.PROTECT)
    starts=models.DateTimeField()
    ends=models.DateTimeField()
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(ends__gt=models.F('starts')),name='valid_lecture_times'),models.UniqueConstraint(fields=['offering','starts'],name='unique_lecture_start')]

class SessionAttendance(models.Model):
    session=models.ForeignKey(LectureSession,on_delete=models.PROTECT)
    enrollment=models.ForeignKey(CourseEnrollment,on_delete=models.PROTECT)
    present=models.BooleanField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['session','enrollment'],name='unique_session_attendance')]

class CourseExam(models.Model):
    offering=models.ForeignKey(CourseOffering,on_delete=models.PROTECT)
    title=models.CharField(max_length=100)
    kind=models.CharField(max_length=20,choices=[('regular','Regular'),('backlog','Backlog'),('makeup','Makeup')])
    day=models.DateField()
    maximum=models.PositiveIntegerField()
    passing=models.PositiveIntegerField()
    min_attendance=models.PositiveSmallIntegerField(default=0)
    status=models.CharField(max_length=20,choices=[('open','Applications open'),('closed','Applications closed'),('published','Results published')],default='open')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['offering','title'],name='unique_course_exam'),models.CheckConstraint(condition=models.Q(maximum__gt=0,passing__gt=0,passing__lte=models.F('maximum'),min_attendance__lte=100),name='valid_exam_thresholds')]

class ExamApplication(models.Model):
    exam=models.ForeignKey(CourseExam,on_delete=models.PROTECT,related_name='applications')
    enrollment=models.ForeignKey(CourseEnrollment,on_delete=models.PROTECT)
    marks=models.PositiveIntegerField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['exam','enrollment'],name='unique_exam_application')]

class ExamQuestion(models.Model):
    exam=models.ForeignKey(CourseExam,on_delete=models.PROTECT,related_name='questions')
    code=models.CharField(max_length=20)
    maximum=models.PositiveIntegerField()
    course_outcome=models.CharField(max_length=40,blank=True)
    bloom_level=models.PositiveSmallIntegerField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['exam','code'],name='unique_exam_question'),models.CheckConstraint(condition=models.Q(maximum__gt=0),name='positive_question_maximum')]

class BookEvaluation(models.Model):
    application=models.OneToOneField(ExamApplication,on_delete=models.PROTECT,related_name='evaluation')
    book_ref=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    examiner=models.ForeignKey(Membership,on_delete=models.PROTECT)
    status=models.CharField(max_length=20,choices=[('assigned','Assigned'),('submitted','Submitted'),('returned','Returned'),('approved','Approved')],default='assigned')
    assigned_at=models.DateTimeField(auto_now_add=True)
    submitted_at=models.DateTimeField(null=True,blank=True)
    reviewed_at=models.DateTimeField(null=True,blank=True)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True)
    review_note=models.CharField(max_length=300,blank=True)

class QuestionScore(models.Model):
    evaluation=models.ForeignKey(BookEvaluation,on_delete=models.PROTECT,related_name='scores')
    question=models.ForeignKey(ExamQuestion,on_delete=models.PROTECT)
    marks=models.PositiveIntegerField()
    note=models.CharField(max_length=300,blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['evaluation','question'],name='unique_question_score')]
