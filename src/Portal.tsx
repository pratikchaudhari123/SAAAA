import { useState } from 'react';
import {modules} from './data';
export const roles=['Institution Administrator','Principal','Student','Applicant','Faculty','HOD','Employee','Parent','Accountant','Admission Officer','Examination Controller','Examiner','Hostel Warden','Placement Officer','Recruiter','Alumni','SaaS Administrator'] as const;
export type Role=typeof roles[number];
const views:Record<Role,string[]>={
'Institution Administrator':modules.flatMap(m=>m.pages),Principal:modules.flatMap(m=>m.pages),
Student:['My Profile','My Courses','Academic Calendar','Timetable','Attendance','Learning Management','Assignments & Quizzes','360° Feedback','Outstanding Fees','Online Payments','Scholarships','Payment Receipts','Registration & Eligibility','Hall Tickets','Results & Marksheets','My Answer Sheets','Revaluation','Certificates & ID Cards','Hostel Applications','Leave Requests','Campus Drives','Eligibility & Applications','Internships','Notices & Circulars','Grievances'],
Applicant:['Student Self-Registration','Applications','Document Verification','Online Payments'],
Faculty:['Teaching Plans','Timetable','Attendance','Learning Management','Assignments & Quizzes','360° Feedback','Faculty Achievements','Leave Management','Notices & Circulars'],
HOD:['Departments','Academic Programs','Courses & Syllabus','Timetable','Teaching Plans','Attendance','Leave Management','Faculty Achievements','CO–PO Attainment'],
Employee:['My Profile','Biometric Attendance','Leave Management','Salary Records','Notices & Circulars'],
Parent:['Outstanding Fees','Online Payments','Payment Receipts'],
Accountant:modules.find(m=>m.key==='finance')!.pages,
'Admission Officer':modules.find(m=>m.key==='admissions')!.pages,
'Examination Controller':modules.find(m=>m.key==='exams')!.pages,
Examiner:['Examiner Allocation','Digital Evaluation','Marks & Moderation'],
'Hostel Warden':modules.find(m=>m.key==='hostel')!.pages,
'Placement Officer':modules.find(m=>m.key==='placements')!.pages,
Recruiter:['Company Registration','Campus Drives','Recruitment Outcomes'],
Alumni:['My Profile','Employment & Entrepreneurs','Donations','Recruitment Network'],
'SaaS Administrator':['Institution Profile','User Management','Roles & Permissions','Integrations','Security & Audit','Backups','Support Tickets']};

const groups=[
 {name:'Academics',keys:['academics'],extra:['My Courses','My Profile'],description:'Teaching, learning and attendance'},
 {name:'Students',keys:['admissions'],extra:['My Answer Sheets'],description:'Admissions, certificates and student services'},
 {name:'Finance',keys:['finance'],extra:['Payment Receipts'],description:'Fees, receipts and accounts'},
 {name:'Examinations',keys:['exams'],extra:[],description:'Exams, evaluation and results'},
 {name:'Administration',keys:['administration'],extra:[],description:'People and campus operations'},
 {name:'Hostel',keys:['hostel'],extra:[],description:'Rooms, occupancy and residential services'},
 {name:'Careers & alumni',keys:['placements','alumni'],extra:[],description:'Internships, recruitment and alumni'},
 {name:'Reports & setup',keys:['accreditation','settings'],extra:[],description:'Reports, configuration and access'},
 {name:'Daily work',keys:['overview'],extra:[],description:'Tasks, notifications and approvals'}
];
const liveRoles:Partial<Record<Role,string>>={'Institution Administrator':'Administrator','Principal':'Principal','Faculty':'Faculty','Accountant':'Finance Officer','Admission Officer':'Admission Officer','Hostel Warden':'Hostel Warden'};
export function Portal({role,institution,onExit,onLive}:{role:Role;institution:string;onExit:()=>void;onLive?:()=>void}){
 const [group,G]=useState('Home'),[query,Q]=useState(''),[selected,S]=useState('');
 const allowed=new Set(views[role]);
 const sections=groups.map(g=>({...g,pages:[...new Set([...modules.filter(m=>g.keys.includes(m.key)).flatMap(m=>m.pages),...g.extra])].filter(p=>allowed.has(p)&&p!=='Institution Dashboard'&&!p.endsWith(' Dashboard'))})).filter(g=>g.pages.length);
 const current=sections.find(g=>g.name===group);
 const matches=sections.flatMap(g=>g.pages.filter(p=>p.toLowerCase().includes(query.trim().toLowerCase())).map(p=>({page:p,group:g.name})));
 const move=(g:string)=>{G(g);S('');Q('')};
 return <div className="saas-shell"><aside className="saas-nav"><div className="saas-brand"><div className="brand-logo">S</div><div><strong>SAAAA</strong><small>Education Cloud</small></div></div><div className="saas-account"><b>{role}</b><small>Evaluation preview</small></div><nav aria-label="Workspaces"><button aria-current={group==='Home'?'page':undefined} onClick={()=>move('Home')}>Home</button>{sections.map(g=><button key={g.name} aria-current={group===g.name?'page':undefined} onClick={()=>move(g.name)}>{g.name}</button>)}</nav><button className="saas-exit" onClick={onExit}>Back to product</button></aside><div className="saas-main"><header className="saas-header"><span>{institution}</span><button className="ghost-button" onClick={onExit}>Exit preview</button></header><main className="saas-content"><div className="saas-kicker">ROLE PREVIEW · NO LIVE ACCESS</div><h1>{group==='Home'?'Your workspace':group}</h1><p className="saas-muted">{group==='Home'?'Find your daily services in one place.':current?.description}</p>{group==='Home'&&liveRoles[role]&&onLive&&<section className="saas-callout"><div><h2>Use the connected workspace</h2><p>Sign in with your assigned {liveRoles[role]} account to access available database-backed functions.</p></div><button className="primary" onClick={onLive}>Go to sign in</button></section>}<label className="saas-search">Find a service<input value={query} onChange={e=>{Q(e.target.value);S('')}} placeholder="Try attendance, fees or approvals"/></label>{query.trim()?<section className="panel"><h2>Matching services</h2>{matches.length?matches.map(x=><button className="saas-service" key={x.group+x.page} onClick={()=>{G(x.group);S(x.page);Q('')}}><strong>{x.page}</strong><small>{x.group}</small></button>):<p>No matching services. Try a different word.</p>}</section>:group==='Home'?<div className="saas-card-grid">{sections.map(g=><button className="saas-card" key={g.name} onClick={()=>move(g.name)}><strong>{g.name}</strong><span>{g.description}</span><small>{g.pages.length} services · Open workspace</small></button>)}</div>:<section className="panel">{selected?<><button className="ghost-button" onClick={()=>S('')}>Back to {group}</button><h2 style={{marginTop:20}}>{selected}</h2><p>This service is shown in the tender evaluation preview. It does not create or approve institutional records.</p>{liveRoles[role]&&onLive&&<button className="primary" onClick={onLive}>Check available live services</button>}</>:<><h2>Available services</h2><div className="saas-card-grid">{current?.pages.map(p=><button className="saas-card" key={p} onClick={()=>S(p)}><strong>{p}</strong><span>View service details</span></button>)}</div></>}</section>}</main></div></div>
}
