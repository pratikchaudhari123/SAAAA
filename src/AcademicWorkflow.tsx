import {useEffect,useState} from 'react';
type Api=(path:string,data?:unknown)=>Promise<any>;
type Choice={id:number|string;label:string};
type Row=Record<string,any>;
type Academic={rooms?:Row[];courses?:Row[];periods?:Row[];faculty?:Row[];offerings:Row[];enrollments:Row[];sessions:Row[];attendance:Row[]};
const blank:Academic={offerings:[],enrollments:[],sessions:[],attendance:[]};
const when=(s:string)=>new Date(s).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'});
const choices=(rows:Row[],label:(r:Row)=>string):Choice[]=>rows.map(r=>({id:r.id,label:label(r)}));
const num=(v:string|undefined)=>Number(v);
export function AcademicWorkflow({slug,role,students,api,mode='academic'}:{slug:string;role:string;students:{student_id:string;name:string;status:string}[];api:Api;mode?:'academic'|'exam'}){
 const [a,A]=useState<Academic>(blank),[x,X]=useState<{exams:Row[];applications:Row[]}>({exams:[],applications:[]}),[task,T]=useState(role==='admin'?'offering':'attendance'),[form,F]=useState<Record<string,string>>({}),[busy,B]=useState(true),[error,E]=useState(''),[notice,N]=useState('');
 const root='institutions/'+encodeURIComponent(slug)+'/';
 const admin=role==='admin',student=role==='student',examStaff=admin||role==='coe';
 async function load(){const data=await api(root+'academic-engine/');A(data);if(mode==='exam')X(await api(root+'examination/'))}
 useEffect(()=>{B(true);void load().catch(e=>E(String(e))).finally(()=>B(false))},[slug,mode]);
 async function submit(path:string,data:Row){B(true);E('');N('');try{await api(root+path,data);await load();N('Saved to institutional records.');F({})}catch(e){E(String(e))}finally{B(false)}}
 const field=(k:string,label:string,type='text',def='')=><label>{label}<input required type={type} value={form[k]??def} onChange={e=>F(v=>({...v,[k]:e.target.value}))}/></label>;
 const select=(k:string,label:string,opts:Choice[])=><label>{label}<select required value={form[k]??''} onChange={e=>F(v=>({...v,[k]:e.target.value}))}><option value="">Select</option>{opts.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></label>;
 const offeringName=(id:number)=>{const o=a.offerings.find(r=>r.id===id);return o?o.course__code+' · '+o.batch:'Offering '+id};
 const offeringChoices=choices(a.offerings,o=>o.course__code+' · '+o.course__name+' · '+o.batch+' · '+o.period__code);
 const sessionChoices=choices(a.sessions,s=>offeringName(s.offering_id)+' · '+when(s.starts));
 const activeSession=a.sessions.find(r=>r.id===num(form.session));
 const selectedExam=x.exams.find(r=>r.id===num(form.exam));
 const enrolled=(offering:number|undefined)=>choices(a.enrollments.filter(r=>r.offering_id===offering),r=>r.student__student_id+' · '+r.student__name);
 const academicTasks=admin?[['offering','Assign course'],['room','Classroom'],['enrollment','Enroll student'],['session','Schedule lecture'],['attendance','Record attendance']]:[['attendance','Record attendance']];
 const examTasks=examStaff?[['create','Configure exam'],['apply','Register student'],['marks','Enter marks']]:[['apply','Apply for exam']];
 const chosen=mode==='exam'?(examTasks.some(t=>t[0]===task)?task:examTasks[0][0]):task;
 function save(){
  let data:Row={};
  if(mode==='academic'){
   if(chosen==='room')data={code:form.code,capacity:num(form.capacity)};
   if(chosen==='offering')data={course:num(form.course),period:num(form.period),faculty:num(form.faculty),batch:form.batch};
   if(chosen==='enrollment')data={offering:num(form.offering),student_id:form.student_id};
   if(chosen==='session')data={offering:num(form.offering),room:num(form.room),starts:form.starts+'+05:30',ends:form.ends+'+05:30'};
   if(chosen==='attendance')data={session:num(form.session),enrollment:num(form.enrollment),present:form.present==='yes'};
   void submit('academic-engine/'+chosen+'/',data)
  }else{
   if(chosen==='create')data={offering:num(form.offering),title:form.title,kind:form.kind,day:form.day,maximum:num(form.maximum??'100'),passing:num(form.passing??'40'),min_attendance:num(form.min_attendance??'0')};
   if(chosen==='apply')data={exam:num(form.exam),enrollment:num(form.enrollment)};
   if(chosen==='marks')data={application:num(form.application),marks:num(form.marks)};
   void submit('examination/'+chosen+'/',data)
  }
 }
 return <section className="panel"><div className="saas-toolbar"><div><h2>{mode==='exam'?'Examinations & results':student?'My scheduled classes':'Course scheduling & session attendance'}</h2><p className="saas-muted">{mode==='exam'?'Pilot: course-linked applications, total marks and controlled result publication.': 'Pilot: course-linked enrollment, dated lectures and separate attendance for each lecture.'}</p></div><button className="ghost-button" disabled={busy} onClick={()=>{B(true);void load().catch(e=>E(String(e))).finally(()=>B(false))}}>Refresh</button></div>{error&&<p className="saas-error" role="alert">{error}</p>}{notice&&<p className="saas-notice" role="status">{notice}</p>}
 {(!student||mode==='exam')&&<><div className="saas-row-actions">{(mode==='exam'?examTasks:academicTasks).map(([k,label])=><button key={k} className={chosen===k?'primary':'ghost-button'} disabled={busy} onClick={()=>{T(k);F({});E('')}}>{label}</button>)}</div><form className="saas-form" onSubmit={e=>{e.preventDefault();save()}}><div className="form-cols">{mode==='academic'?<>
 {chosen==='room'&&<>{field('code','Classroom code')}{field('capacity','Seating capacity','number')}</>}
 {chosen==='offering'&&<>{select('course','Academic course',choices(a.courses??[],r=>r.code+' · '+r.program__name))}{select('period','Academic period',choices(a.periods??[],r=>r.code))}{select('faculty','Assigned faculty',choices(a.faculty??[],r=>r.user__username))}{field('batch','Batch code')}</>}
 {chosen==='enrollment'&&<>{select('offering','Course offering',offeringChoices)}{select('student_id','Active student',students.filter(s=>s.status==='Active').map(s=>({id:s.student_id,label:s.student_id+' · '+s.name})))}</>}
 {chosen==='session'&&<>{select('offering','Course offering',offeringChoices)}{select('room','Classroom',choices(a.rooms??[],r=>r.code+' · '+r.capacity+' seats'))}{field('starts','Starts (IST)','datetime-local')}{field('ends','Ends (IST)','datetime-local')}</>}
 {chosen==='attendance'&&<>{select('session','Lecture session',sessionChoices)}{select('enrollment','Enrolled student',enrolled(activeSession?.offering_id))}{select('present','Attendance',[{id:'yes',label:'Present'},{id:'no',label:'Absent'}])}</>}
 </>:<>
 {chosen==='create'&&<>{select('offering','Course offering',offeringChoices)}{field('title','Exam title')}{select('kind','Exam type',[{id:'regular',label:'Regular'},{id:'backlog',label:'Backlog'},{id:'makeup',label:'Makeup'}])}{field('day','Exam date','date')}{field('maximum','Maximum marks','number','100')}{field('passing','Passing marks','number','40')}{field('min_attendance','Minimum completed lecture attendance (%)','number','0')}</>}
 {chosen==='apply'&&<>{select('exam','Open examination',choices(x.exams.filter(r=>r.status==='open'),r=>r.title+' · '+r.offering__course__code))}{select('enrollment','Course enrollment',enrolled(selectedExam?.offering_id))}</>}
 {chosen==='marks'&&<>{select('application','Registered student',choices(x.applications.filter(r=>r.exam__status==='closed'),r=>r.enrollment__student__name+' · '+(x.exams.find(e=>e.id===r.exam_id)?.title??r.exam_id)))}{field('marks','Total marks','number')}</>}
 </>}</div><button className="primary" disabled={busy}>{chosen==='apply'?'Submit application':'Save record'}</button></form></>}
 {mode==='academic'?<><h3>Course offerings ({a.offerings.length})</h3>{a.offerings.length?<div className="table-scroll"><table><thead><tr><th>Course</th><th>Period</th><th>Batch</th><th>Faculty</th><th>{student?'My enrollment':'Enrolled'}</th></tr></thead><tbody>{a.offerings.map(o=><tr key={o.id}><td>{o.course__code} · {o.course__name}</td><td>{o.period__code}</td><td>{o.batch}</td><td>{o.faculty__user__username}</td><td>{a.enrollments.filter(r=>r.offering_id===o.id).length}</td></tr>)}</tbody></table></div>:<p>No course offerings assigned yet. Set up course masters, faculty and period first.</p>}<h3>Lecture sessions</h3>{a.sessions.length?<div className="table-scroll"><table><thead><tr><th>Course / batch</th><th>Room</th><th>Starts</th><th>Ends</th><th>Present / recorded</th></tr></thead><tbody>{a.sessions.map(s=><tr key={s.id}><td>{offeringName(s.offering_id)}</td><td>{s.room__code}</td><td>{when(s.starts)}</td><td>{when(s.ends)}</td><td>{a.attendance.filter(r=>r.session_id===s.id&&r.present).length} / {a.attendance.filter(r=>r.session_id===s.id).length}</td></tr>)}</tbody></table></div>:<p>No scheduled lectures.</p>}</>:<><h3>Examination register</h3>{x.exams.length?<div className="table-scroll"><table><thead><tr><th>Exam</th><th>Date</th><th>Passing / maximum</th><th>Status</th>{examStaff&&<th>Action</th>}</tr></thead><tbody>{x.exams.map(r=><tr key={r.id}><td>{r.title} · {r.offering__course__code}</td><td>{r.day}</td><td>{r.passing} / {r.maximum}</td><td>{r.status}</td>{examStaff&&<td>{r.status!=='published'&&<button className="ghost-button" disabled={busy} onClick={()=>{const status=r.status==='open'?'closed':'published';if(window.confirm(status==='published'?'Publish results? Marks will become visible to students and cannot be edited in this pilot.':'Close applications?'))void submit('examination/state/',{exam:r.id,status})}}>{r.status==='open'?'Close applications':'Publish results'}</button>}</td>}</tr>)}</tbody></table></div>:<p>No examinations configured.</p>}<h3>{student?'My applications and published results':'Applications and marks'}</h3>{x.applications.length?<div className="table-scroll"><table><thead><tr><th>Exam</th><th>Student</th><th>Marks</th><th>Result</th></tr></thead><tbody>{x.applications.map(r=><tr key={r.id}><td>{x.exams.find(e=>e.id===r.exam_id)?.title}</td><td>{r.enrollment__student__name}</td><td>{r.marks===null?'Not available':r.marks+' / '+r.exam__maximum}</td><td>{r.result??'Not published'}</td></tr>)}</tbody></table></div>:<p>No examination applications yet.</p>}<p className="saas-muted">Digital answer-sheet scanning, annotations, hall tickets, exam fees and revaluation are not yet implemented.</p></>}
 </section>
}
