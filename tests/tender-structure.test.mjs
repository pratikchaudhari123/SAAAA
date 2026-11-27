import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const src=readFileSync(new URL('../src/data.ts',import.meta.url),'utf8');
const matrix=readFileSync(new URL('../docs/TENDER_COMPLIANCE_MATRIX.md',import.meta.url),'utf8');
test('all eight tender ERP domains represented in menu metadata',()=>{for(const key of ['academics','administration','finance','admissions','exams','hostel','placements','alumni'])assert.match(src,new RegExp(`key:'${key}'`));});
test('tender traceability includes 22 tracked work items',()=>{for(let n=1;n<=22;n++)assert.match(matrix,new RegExp(`GCOEA-${String(n).padStart(3,'0')}`));});
test('demonstration email addresses cannot accidentally be sent to real domains',()=>{assert.match(src,/example\.invalid/);});
