export function registerJobTools({getState,openApplication}) {
 const context=document.modelContext;
 if(!context?.registerTool)return ()=>{};
 const lifecycle=new AbortController();
 const tools=[{
  name:'read_job_agent_summary',title:'Read job tracker',description:'Read saved job counts and workflow mode. Does not search, edit, approve or submit applications.',
  inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},
  async execute(input){if(!input||Object.keys(input).length)throw Error('No parameters accepted');const state=await getState();return {metrics:state.metrics,dry_run:state.settings.dry_run,candidate_intake_deferred:!!state.profile.intake_deferred,jobs:state.jobs.map(j=>({job_id:j.job_id,application_id:state.applications.find(a=>a.job_id===j.job_id)?.application_id,company:j.company,title:j.title,score:j.analysis?.scoring?.overall_score??null}))}}
 },{
  name:'open_application_detail',title:'Open application details',description:'Navigate to a saved application detail panel. Does not approve, fill or submit an employer application.',
  inputSchema:{type:'object',properties:{application_id:{type:'string',minLength:1}},required:['application_id'],additionalProperties:false},annotations:{readOnlyHint:false,untrustedContentHint:false},
  async execute(input){if(!input||Object.keys(input).some(k=>k!=='application_id')||typeof input.application_id!=='string')throw Error('A valid application_id is required');const state=await getState();if(!state.applications.some(a=>a.application_id===input.application_id))throw Error('Application not found');openApplication(input.application_id);return {opened:true,application_id:input.application_id,submitted:false}}
 }];
 for(const tool of tools)try{Promise.resolve(context.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{})}catch{}
 return ()=>lifecycle.abort();
}
