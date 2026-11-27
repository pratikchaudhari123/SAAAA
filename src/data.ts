export type ModuleKey='overview'|'academics'|'administration'|'admissions'|'finance'|'exams'|'hostel'|'placements'|'alumni'|'accreditation'|'settings';
export type NavItem={key:ModuleKey;label:string;subtitle:string;pages:string[]};
export const modules:NavItem[]=[
{key:'overview',label:'Overview',subtitle:'Institution command centre',pages:['Institution Dashboard','Notifications','My Tasks','Approvals']},
{key:'academics',label:'Academic Management',subtitle:'Learning, teaching and attendance',pages:['Departments','Academic Programs','Courses & Syllabus','Academic Calendar','Timetable','Teaching Plans','Attendance','Learning Management','Assignments & Quizzes','360° Feedback']},
{key:'administration',label:'General Administration',subtitle:'Employees and institutional operations',pages:['Employee Directory','Employee Enrollment','Biometric Attendance','Leave Management','Salary Records','Faculty Achievements','Notices & Circulars','Events']},
{key:'admissions',label:'Student Admissions',subtitle:'From application to graduation',pages:['Admission Dashboard','Student Self-Registration','Applications','Document Verification','Student Directory','NEP Multiple Entry / Exit','Academic Promotion','Branch Transfers','Certificates & ID Cards','Clearance & Grievances']},
{key:'finance',label:'Fees & Finance',subtitle:'Fees, accounts and reconciliation',pages:['Finance Dashboard','Fee Structure','Fee Collection','Online Payments','Scholarships','Outstanding Fees','Refunds','Student Ledgers','Supplier Bills','Consultancy Charges','Financial Statements','Tally Integration']},
{key:'exams',label:'Examination Management',subtitle:'Confidential examination lifecycle',pages:['Examination Dashboard','Exam Configuration','Registration & Eligibility','Hall Tickets','Exam Timetables','Seating Plans','Question Paper Vault','Examiner Allocation','Encrypted Barcodes','Answer Sheet Scanning','Digital Evaluation','Marks & Moderation','Results & Marksheets','Revaluation']},
{key:'hostel',label:'Hostel Management',subtitle:'Residential operations',pages:['Hostel Dashboard','Hostel Applications','Room Allocation','Occupancy','Hostel Fees','Mess Billing','Biometric Movement','Leave Requests','Guest House','Grievances']},
{key:'placements',label:'Training & Placement',subtitle:'Recruitment and student opportunities',pages:['Placement Dashboard','Company Registration','Company Directory','Campus Drives','Eligibility & Applications','Internships','Recruitment Outcomes']},
{key:'alumni',label:'Alumni Management',subtitle:'Lifetime institutional engagement',pages:['Alumni Dashboard','Alumni Directory','Batch Records','Employment & Entrepreneurs','Donations','Recruitment Network']},
{key:'accreditation',label:'Accreditation & Reports',subtitle:'NBA, NAAC and NIRF evidence',pages:['NBA Reports','NAAC Reports','NIRF Reports','CO–PO Attainment','Academic Analytics','Finance Reports','Custom Exports']},
{key:'settings',label:'System Administration',subtitle:'Security, permissions and operations',pages:['Institution Profile','User Management','Roles & Permissions','Approval Workflows','Data Migration','Integrations','Security & Audit','Backups','Support Tickets']}
];
export type Student={id:string,name:string,program:string,year:number,status:'Active'|'Pending'|'On Hold',email:string};
export const initialStudents:Student[]=[
{id:'DEMO-2026-001',name:'Aarohi Deshmukh',program:'Computer Engineering',year:2,status:'Active',email:'aarohi@example.invalid'},
{id:'DEMO-2026-002',name:'Rohan Patil',program:'Mechanical Engineering',year:3,status:'Active',email:'rohan@example.invalid'},
{id:'DEMO-2026-003',name:'Sara Khan',program:'Civil Engineering',year:1,status:'Pending',email:'sara@example.invalid'},
{id:'DEMO-2026-004',name:'Nikhil Joshi',program:'Electrical Engineering',year:4,status:'On Hold',email:'nikhil@example.invalid'},
{id:'DEMO-2026-005',name:'Mira Kulkarni',program:'Computer Engineering',year:1,status:'Active',email:'mira@example.invalid'}
];
export const seedMetrics=[{label:'Total students',value:'1,500',delta:'Illustrative baseline',trend:'up'},{label:'Active faculty',value:'86',delta:'Synthetic data',trend:'neutral'},{label:'Attendance today',value:'92.4%',delta:'Sample percentage',trend:'up'},{label:'Fee collection',value:'₹28.6L',delta:'Illustrative only',trend:'neutral'}];
export const seedActivity=[{label:'Admission application received',detail:'Admissions • 10 minutes ago',type:'sky'},{label:'Fee receipt created',detail:'Finance • 28 minutes ago',type:'green'},{label:'Exam timetable draft updated',detail:'Examinations • 1 hour ago',type:'purple'},{label:'Faculty leave request submitted',detail:'Administration • 2 hours ago',type:'orange'}];
