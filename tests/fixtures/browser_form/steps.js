'use strict';
document.getElementById('next').addEventListener('click',()=>{
  const receipt=JSON.parse(document.getElementById('receipt').textContent);
  if(receipt.name!=='Test Candidate'||receipt.email!=='candidate@example.test'||!receipt.file_selected)return;
  document.getElementById('contact').hidden=true;
  document.getElementById('review-step').hidden=false;
  document.getElementById('application').dataset.step='review';
});
