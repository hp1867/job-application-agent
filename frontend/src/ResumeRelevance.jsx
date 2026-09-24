import React from 'react';

const percent=value=>value==null?'Not assessed':`${value}%`;
export default function ResumeRelevance({report}){
 if(!report)return <p className="muted">Detailed resume coverage is available after the next document validation.</p>;
 if(report.status==='UNAVAILABLE')return <section aria-label="Resume relevance"><h2>Resume relevance</h2><p>{report.reason}</p></section>;
 return <section aria-label="Resume relevance"><h2>Resume relevance</h2>
  <p><strong>{percent(report.overall_score)}</strong> assessed-term coverage {report.status==='PARTIAL'?'· Partial assessment':''}</p>
  <p className="muted">This checks words in your validated resume. It is not an employer ATS score or an eligibility decision. Unassessed requirements still need review.</p>
  <dl>{[['Required skills',report.required_skills?.percent],['Optional skills',report.preferred_skills?.percent],['Education terms',report.education?.percent],['Experience and project terms',report.experience?.percent]].map(([label,value])=><React.Fragment key={label}><dt>{label}</dt><dd>{percent(value)}</dd></React.Fragment>)}</dl>
  <p>Required terms not found: {report.required_skills?.missing?.join(', ')||'None listed'}</p>
  <p>Optional terms not found: {report.preferred_skills?.missing?.join(', ')||'None listed'}. Optional gaps do not reduce the assessed score.</p>
  {[...(report.education?.requirements||[]),...(report.experience?.requirements||[])].map((item,index)=><p key={index}><strong>{item.requirement}</strong>: {item.status==='TERM_PRESENT'?'Term present':item.status==='TERM_NOT_FOUND'?'Term not found':'Needs review'}<br/><small>{item.note}</small></p>)}
 </section>;
}
