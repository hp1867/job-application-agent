import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
let server,View;
before(async()=>{server=await createServer({server:{middlewareMode:true},appType:'custom'});View=(await server.ssrLoadModule('/src/ResumeRelevance.jsx')).default;});
after(async()=>{await server?.close();});
const render=report=>renderToStaticMarkup(React.createElement(View,{report}));
test('missing validation does not invent a score',()=>{assert.match(render(null),/after the next document validation/);});
test('failed facts display an unavailable explanation',()=>{assert.match(render({status:'UNAVAILABLE',reason:'Facts need review'}),/Facts need review/);});
test('partial report distinguishes missing dimensions and optional skills',()=>{
 const html=render({status:'PARTIAL',overall_score:100,required_skills:{percent:100,missing:[]},preferred_skills:{percent:0,missing:['Rust']},education:{percent:null},experience:{percent:null}});
 for(const phrase of ['Partial assessment','Required skills','Optional skills','Not assessed','Rust','not an employer ATS score'])assert.ok(html.includes(phrase),phrase);
});
test('listing text is escaped, not executable markup',()=>{
 const html=render({status:'PARTIAL',education:{requirements:[{requirement:'<script>alert(1)</script>',status:'NEEDS_REVIEW'}]}});
 assert.ok(!html.includes('<script>'));assert.ok(html.includes('&lt;script&gt;'));
});
