import uuid
from django.db import models
from django.conf import settings
class Institution(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
class Membership(models.Model):
    institution = models.ForeignKey(Institution,on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    role = models.CharField(max_length=30,choices=[('admin','Administrator'),('admissions','Admission Officer'),('viewer','Read only'),('faculty','Faculty'),('finance','Finance Officer'),('warden','Hostel Warden'),('principal','Principal'),('student','Student'),('coe','Examination Controller'),('tpo','Placement Officer'),('tpo_assistant','Placement Assistant'),('company','Recruitment Company'),('alumni','Alumni'),('applicant','Admission Applicant')])
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
    status = models.CharField(max_length=20,choices=[('Active','Active'),('Pending','Pending'),('On Hold','On Hold'),('Graduated','Graduated')],default='Pending')
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
    request_key = models.UUIDField(null=True,blank=True,editable=False)
    amount = models.DecimalField(max_digits=12,decimal_places=2)
    method = models.CharField(max_length=20,choices=[('cash','Cash'),('bank','Bank transfer')])
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0),name='positive_fee_receipt'),models.UniqueConstraint(fields=['account','request_key'],name='unique_fee_receipt_request')]

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
    expected_pages=models.PositiveSmallIntegerField(null=True,blank=True)
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

class AnswerPage(models.Model):
    evaluation=models.ForeignKey(BookEvaluation,on_delete=models.PROTECT,related_name='pages')
    number=models.PositiveSmallIntegerField()
    image=models.BinaryField(editable=False)
    sha256=models.CharField(max_length=64,editable=False)
    width=models.PositiveIntegerField()
    height=models.PositiveIntegerField()
    uploaded_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    uploaded_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['evaluation','number'],name='unique_answer_page'),models.CheckConstraint(condition=models.Q(number__gt=0),name='positive_answer_page')]

class PageAnnotation(models.Model):
    page=models.ForeignKey(AnswerPage,on_delete=models.PROTECT,related_name='annotations')
    x=models.PositiveSmallIntegerField()
    y=models.PositiveSmallIntegerField()
    note=models.CharField(max_length=300)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(x__lte=10000,y__lte=10000),name='valid_page_annotation_position')]

class Employee(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    membership=models.OneToOneField(Membership,on_delete=models.PROTECT,null=True,blank=True)
    code=models.CharField(max_length=50)
    name=models.CharField(max_length=150)
    designation=models.CharField(max_length=100)
    category=models.CharField(max_length=20,choices=[('teaching','Teaching'),('non_teaching','Non-teaching'),('contract','Contractual')])
    joined_on=models.DateField()
    active=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['institution','code'],name='unique_employee_code')]

class EmployeeDeviceIdentity(models.Model):
    source=models.ForeignKey(IntegrationSource,on_delete=models.PROTECT)
    employee=models.ForeignKey(Employee,on_delete=models.PROTECT)
    subject_ref=models.CharField(max_length=100)
    effective_from=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['source','subject_ref'],name='unique_employee_device_identity'),models.UniqueConstraint(fields=['source','employee'],name='unique_employee_per_source')]

class EmployeePunch(models.Model):
    event=models.OneToOneField(IntegrationEvent,on_delete=models.PROTECT,related_name='employee_punch')
    employee=models.ForeignKey(Employee,on_delete=models.PROTECT)
    mapped_at=models.DateTimeField(auto_now_add=True)

class EmployeeLeave(models.Model):
    employee=models.ForeignKey(Employee,on_delete=models.PROTECT)
    category=models.CharField(max_length=40)
    starts=models.DateField()
    ends=models.DateField()
    reason=models.CharField(max_length=300)
    status=models.CharField(max_length=20,choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected'),('withdrawn','Withdrawn')],default='pending')
    created_at=models.DateTimeField(auto_now_add=True)
    reviewed_at=models.DateTimeField(null=True,blank=True)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True)
    review_note=models.CharField(max_length=300,blank=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(ends__gte=models.F('starts')),name='valid_employee_leave_dates')]

class RecruitmentCompany(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    membership=models.OneToOneField(Membership,on_delete=models.PROTECT)
    name=models.CharField(max_length=150)
    contact_email=models.EmailField()
    description=models.CharField(max_length=500,blank=True)
    status=models.CharField(max_length=20,choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')],default='pending')
    review_note=models.CharField(max_length=300,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['institution','name'],name='unique_recruitment_company')]

class CareerProfile(models.Model):
    student=models.OneToOneField(Student,on_delete=models.PROTECT)
    skills=models.CharField(max_length=500)
    summary=models.CharField(max_length=1000)
    updated_at=models.DateTimeField(auto_now=True)

class RecruitmentDrive(models.Model):
    company=models.ForeignKey(RecruitmentCompany,on_delete=models.PROTECT,related_name='drives')
    title=models.CharField(max_length=150)
    kind=models.CharField(max_length=20,choices=[('job','Employment'),('internship','Internship'),('training','Training')])
    program=models.CharField(max_length=150,blank=True)
    min_year=models.PositiveSmallIntegerField()
    max_year=models.PositiveSmallIntegerField()
    deadline=models.DateField()
    drive_day=models.DateField()
    instructions=models.CharField(max_length=1000)
    status=models.CharField(max_length=20,choices=[('open','Open'),('closed','Closed')],default='open')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['company','title','drive_day'],name='unique_recruitment_drive'),models.CheckConstraint(condition=models.Q(min_year__gte=1,max_year__lte=8,max_year__gte=models.F('min_year'),drive_day__gte=models.F('deadline')),name='valid_recruitment_drive')]

class RecruitmentApplication(models.Model):
    drive=models.ForeignKey(RecruitmentDrive,on_delete=models.PROTECT,related_name='applications')
    student=models.ForeignKey(Student,on_delete=models.PROTECT)
    skills=models.CharField(max_length=500)
    summary=models.CharField(max_length=1000)
    status=models.CharField(max_length=20,choices=[('submitted','Submitted'),('shortlisted','Shortlisted'),('selected','Selected'),('rejected','Rejected'),('withdrawn','Withdrawn')],default='submitted')
    applied_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['drive','student'],name='unique_recruitment_application')]

class AlumniRecord(models.Model):
    student=models.OneToOneField(Student,on_delete=models.PROTECT,related_name='alumni_record')
    graduation_day=models.DateField()
    approval_reference=models.CharField(max_length=100)
    approved_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    program_snapshot=models.CharField(max_length=150)
    occupation=models.CharField(max_length=20,choices=[('unknown','Not provided'),('employee','Employee'),('entrepreneur','Entrepreneur'),('other','Other')],default='unknown')
    employer=models.CharField(max_length=150,blank=True)
    location=models.CharField(max_length=150,blank=True)
    updated_at=models.DateTimeField(auto_now=True)

class AlumniOpportunity(models.Model):
    alumni=models.ForeignKey(AlumniRecord,on_delete=models.PROTECT)
    kind=models.CharField(max_length=20,choices=[('recruitment','Recruitment'),('training','Training'),('mentoring','Mentoring')])
    title=models.CharField(max_length=150)
    description=models.CharField(max_length=1000)
    contact_url=models.URLField(blank=True)
    status=models.CharField(max_length=20,choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')],default='pending')
    created_at=models.DateTimeField(auto_now_add=True)

class AlumniSettings(models.Model):
    institution=models.OneToOneField(Institution,on_delete=models.PROTECT)
    donation_url=models.URLField(blank=True)

class LearningResource(models.Model):
    offering=models.ForeignKey(CourseOffering,on_delete=models.PROTECT)
    title=models.CharField(max_length=150)
    text=models.TextField(blank=True)
    url=models.URLField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

class LearningAssignment(models.Model):
    offering=models.ForeignKey(CourseOffering,on_delete=models.PROTECT)
    title=models.CharField(max_length=150)
    instructions=models.TextField()
    deadline=models.DateTimeField()
    maximum=models.PositiveIntegerField()

class LearningSubmission(models.Model):
    assignment=models.ForeignKey(LearningAssignment,on_delete=models.PROTECT)
    enrollment=models.ForeignKey(CourseEnrollment,on_delete=models.PROTECT)
    answer=models.TextField()
    marks=models.PositiveIntegerField(null=True,blank=True)
    feedback=models.CharField(max_length=1000,blank=True)
    submitted_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['assignment','enrollment'],name='unique_learning_submission')]

class LearningQuiz(models.Model):
    offering=models.ForeignKey(CourseOffering,on_delete=models.PROTECT)
    title=models.CharField(max_length=150)
    deadline=models.DateTimeField()
    questions=models.JSONField()

class QuizAttempt(models.Model):
    quiz=models.ForeignKey(LearningQuiz,on_delete=models.PROTECT)
    enrollment=models.ForeignKey(CourseEnrollment,on_delete=models.PROTECT)
    answers=models.JSONField()
    score=models.PositiveIntegerField()
    submitted_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['quiz','enrollment'],name='unique_learning_quiz_attempt')]

class LedgerConfiguration(models.Model):
    institution=models.OneToOneField(Institution,on_delete=models.PROTECT)
    activated_at=models.DateTimeField(auto_now_add=True)
    activated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

class LedgerAccount(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    code=models.CharField(max_length=30)
    name=models.CharField(max_length=150)
    category=models.CharField(max_length=20,choices=[('asset','Asset'),('liability','Liability'),('equity','Equity'),('income','Income'),('expense','Expense')])
    class Meta:
        constraints=[models.UniqueConstraint(fields=['institution','code'],name='unique_ledger_account_code')]

class LedgerJournal(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    reference=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    source_key=models.CharField(max_length=100)
    day=models.DateField()
    description=models.CharField(max_length=300)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['institution','source_key'],name='unique_ledger_source')]

class LedgerLine(models.Model):
    journal=models.ForeignKey(LedgerJournal,on_delete=models.PROTECT,related_name='lines')
    account=models.ForeignKey(LedgerAccount,on_delete=models.PROTECT)
    debit=models.DecimalField(max_digits=16,decimal_places=2,default=0)
    credit=models.DecimalField(max_digits=16,decimal_places=2,default=0)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(debit__gt=0,credit=0)|models.Q(credit__gt=0,debit=0)),name='ledger_line_one_side')]

class CampusNotice(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    title=models.CharField(max_length=150)
    body=models.TextField()
    kind=models.CharField(max_length=20,choices=[('notice','Notice'),('memo','Memo'),('news','News'),('event','Event'),('task','Task')])
    audience=models.CharField(max_length=30)
    recipient=models.ForeignKey(Membership,on_delete=models.PROTECT,null=True,blank=True)
    starts=models.DateTimeField()
    ends=models.DateTimeField()
    link=models.URLField(blank=True)
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    withdrawn=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(ends__gt=models.F('starts')),name='valid_notice_window')]

class NoticeAcknowledgment(models.Model):
    notice=models.ForeignKey(CampusNotice,on_delete=models.PROTECT)
    membership=models.ForeignKey(Membership,on_delete=models.PROTECT)
    acknowledged_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['notice','membership'],name='unique_notice_ack')]

class FeedbackSurvey(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    offering=models.ForeignKey(CourseOffering,on_delete=models.PROTECT,null=True,blank=True)
    title=models.CharField(max_length=150)
    kind=models.CharField(max_length=20,choices=[('academic','Academic'),('teaching','Teaching'),('non_teaching','Non-teaching'),('infrastructure','Infrastructure'),('exit','Exit')])
    scale=models.CharField(max_length=10,choices=[('grade','Grade'),('marks','Marks')])
    questions=models.JSONField()
    opens=models.DateTimeField()
    closes=models.DateTimeField()
    min_attendance=models.PositiveSmallIntegerField(default=0)
    min_fee_paid=models.PositiveSmallIntegerField(default=0)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    cancelled=models.BooleanField(default=False)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(closes__gt=models.F('opens'),min_attendance__lte=100,min_fee_paid__lte=100),name='valid_feedback_window')]

class FeedbackInvite(models.Model):
    survey=models.ForeignKey(FeedbackSurvey,on_delete=models.PROTECT,related_name='invites')
    student=models.ForeignKey(Student,on_delete=models.PROTECT)
    submitted_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['survey','student'],name='unique_feedback_invite')]

class FeedbackResponse(models.Model):
    survey=models.ForeignKey(FeedbackSurvey,on_delete=models.PROTECT,related_name='responses')
    scores=models.JSONField()
    submitted_at=models.DateTimeField(auto_now_add=True)

class RegistrationRule(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    program=models.ForeignKey(AcademicProgram,on_delete=models.PROTECT)
    code=models.CharField(max_length=30)
    opens=models.DateField()
    closes=models.DateField()
    qualification=models.CharField(max_length=100)
    minimum_percent=models.DecimalField(max_digits=5,decimal_places=2)
    seats=models.PositiveIntegerField()
    estimated_fee=models.DecimalField(max_digits=12,decimal_places=2)
    required_documents=models.JSONField(default=list)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['institution','code'],name='unique_registration_rule'),models.CheckConstraint(condition=models.Q(closes__gte=models.F('opens'),minimum_percent__gte=0,minimum_percent__lte=100,seats__gt=0,estimated_fee__gte=0),name='valid_registration_rule')]

class AdmissionApplication(models.Model):
    membership=models.OneToOneField(Membership,on_delete=models.PROTECT)
    rule=models.ForeignKey(RegistrationRule,on_delete=models.PROTECT)
    name=models.CharField(max_length=200,blank=True)
    email=models.EmailField(blank=True)
    qualification=models.CharField(max_length=100,blank=True)
    percent=models.DecimalField(max_digits=5,decimal_places=2,null=True,blank=True)
    status=models.CharField(max_length=20,choices=[('draft','Draft'),('submitted','Submitted'),('returned','Returned'),('approved','Approved'),('rejected','Rejected')],default='draft')
    review_note=models.CharField(max_length=500,blank=True)
    student=models.OneToOneField(Student,on_delete=models.PROTECT,null=True,blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    created_at=models.DateTimeField(auto_now_add=True)

class AdmissionDocument(models.Model):
    application=models.ForeignKey(AdmissionApplication,on_delete=models.PROTECT,related_name='documents')
    kind=models.CharField(max_length=30)
    image=models.BinaryField(editable=False)
    sha256=models.CharField(max_length=64)
    uploaded_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['application','kind'],name='unique_admission_document')]

class InstitutionalRole(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    name=models.CharField(max_length=100)
    parent=models.ForeignKey('self',on_delete=models.PROTECT,null=True,blank=True)
    permissions=models.JSONField(default=list)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['institution','name'],name='unique_institutional_role')]

class InstitutionalRoleGrant(models.Model):
    role=models.ForeignKey(InstitutionalRole,on_delete=models.PROTECT)
    membership=models.ForeignKey(Membership,on_delete=models.PROTECT)
    starts=models.DateTimeField()
    ends=models.DateTimeField(null=True,blank=True)
    revoked_at=models.DateTimeField(null=True,blank=True)
    reason=models.CharField(max_length=300)
    granted_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(ends__isnull=True)|models.Q(ends__gt=models.F('starts')),name='valid_role_grant_window')]

class CertificatePolicy(models.Model):
    institution=models.ForeignKey(Institution,on_delete=models.PROTECT)
    code=models.CharField(max_length=30)
    kind=models.CharField(max_length=30,choices=[('bonafide','Bonafide'),('character','Character'),('fee_statement','Fee statement'),('clearance','Clearance'),('student_id','Student ID')])
    title=models.CharField(max_length=150)
    text=models.TextField()
    allow_duplicate=models.BooleanField(default=False)
    clearance_units=models.JSONField(default=list)
    active=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['institution','code'],name='unique_certificate_policy')]

class CertificateRequest(models.Model):
    policy=models.ForeignKey(CertificatePolicy,on_delete=models.PROTECT)
    student=models.ForeignKey(Student,on_delete=models.PROTECT)
    copy_kind=models.CharField(max_length=10,choices=[('original','Original'),('duplicate','Duplicate')])
    original=models.ForeignKey('self',on_delete=models.PROTECT,null=True,blank=True)
    reason=models.CharField(max_length=300)
    status=models.CharField(max_length=20,choices=[('pending','Pending'),('issued','Issued'),('rejected','Rejected'),('revoked','Revoked')],default='pending')
    policy_snapshot=models.JSONField(default=dict)
    issued_snapshot=models.JSONField(default=dict)
    serial=models.UUIDField(null=True,unique=True,editable=False)
    issued_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True)
    issued_at=models.DateTimeField(null=True,blank=True)
    review_note=models.CharField(max_length=500,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

class CertificateClearance(models.Model):
    request=models.ForeignKey(CertificateRequest,on_delete=models.PROTECT,related_name='clearances')
    unit=models.CharField(max_length=20)
    cleared=models.BooleanField()
    note=models.CharField(max_length=300)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['request','unit'],name='unique_certificate_clearance')]

class AcademicCalendarDay(models.Model):
    period=models.ForeignKey(AcademicPeriod,on_delete=models.PROTECT)
    day=models.DateField()
    title=models.CharField(max_length=150)
    kind=models.CharField(max_length=20,choices=[('holiday','Holiday'),('event','Event'),('academic','Academic milestone')])
    blocks_teaching=models.BooleanField(default=False)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['period','day'],name='unique_academic_calendar_day')]

class LectureTeachingPlan(models.Model):
    session=models.OneToOneField(LectureSession,on_delete=models.PROTECT)
    topics=models.TextField()
    delivery_note=models.TextField(blank=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    updated_at=models.DateTimeField(auto_now=True)

class LearningAttachment(models.Model):
    resource=models.OneToOneField(LearningResource,on_delete=models.PROTECT,related_name='attachment')
    filename=models.CharField(max_length=150)
    content_type=models.CharField(max_length=100)
    content=models.BinaryField(editable=False)
    size=models.PositiveIntegerField()
    sha256=models.CharField(max_length=64)
    uploaded_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    uploaded_at=models.DateTimeField(auto_now_add=True)
