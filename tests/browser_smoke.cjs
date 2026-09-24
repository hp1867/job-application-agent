/** Actual local browser transport test, never an employer application driver.
 * Uses a fresh non-persistent browser, a loopback-only fixture, and synthetic data.
 * The durable Python workflow still owns every field, upload and approval gate.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const ROOT = path.resolve(__dirname, '..');
const PYTHON = process.env.JOB_AGENT_TEST_PYTHON;
const PLAYWRIGHT = process.env.JOB_AGENT_TEST_PLAYWRIGHT || 'playwright';
const BROWSER_CHANNEL = process.env.JOB_AGENT_TEST_BROWSER_CHANNEL || 'msedge';
const ORIGIN = 'http://127.0.0.1:8767';
const FIXTURE = path.join(__dirname, 'fixtures', 'browser_form');
if (!PYTHON) throw new Error('Set JOB_AGENT_TEST_PYTHON or run test-browser.ps1.');

function launch(args) {
  return spawn(PYTHON, args, { cwd: ROOT, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
}
function collect(child) {
  let stdout = '', stderr = '';
  child.stdout.on('data', chunk => { stdout += chunk; });
  child.stderr.on('data', chunk => { stderr += chunk; });
  return new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', code => resolve({ code, stdout, stderr }));
  });
}
async function python(args, allowFailure = false) {
  const result = await collect(launch(args));
  if (result.code !== 0 && !allowFailure) throw new Error(result.stderr || result.stdout || 'Python command failed');
  return result;
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

async function main() {
  const fixture = JSON.parse((await python(['-m', 'tests.browser_fixture_setup'])).stdout);
  assert.equal(fixture.test_validation_stub, true);
  assert.equal(fixture.browser_url, ORIGIN + '/');
  assert.ok(path.resolve(fixture.root).startsWith(path.join(ROOT, 'tmp') + path.sep));
  const allowedFiles = new Map([
    ['/', { bytes: await fs.readFile(path.join(FIXTURE, 'index.html')), type: 'text/html; charset=utf-8' }],
    ['/app.js', { bytes: await fs.readFile(path.join(FIXTURE, 'app.js')), type: 'text/javascript; charset=utf-8' }],
  ]);
  const server = http.createServer((request, response) => {
    if (request.headers.host !== '127.0.0.1:8767' || !['GET', 'HEAD'].includes(request.method)) {
      response.writeHead(403); return response.end('Test server rejects this request');
    }
    const file = allowedFiles.get(request.url);
    if (!file) { response.writeHead(404); return response.end('Not found'); }
    response.writeHead(200, { 'Content-Type': file.type, 'Cache-Control': 'no-store',
      'Content-Security-Policy': "default-src 'self'; connect-src 'none'; form-action 'none'; frame-src 'none'; object-src 'none'" });
    response.end(request.method === 'HEAD' ? undefined : file.bytes);
  });
  let browser, worker, workerResult, workerDone;
  const commands = [], blockedRequests = [], pageErrors = [];
  try {
    await new Promise((resolve, reject) => { server.once('error', reject); server.listen(8767, '127.0.0.1', resolve); });
    const { chromium } = require(PLAYWRIGHT);
    browser = await chromium.launch({ channel: BROWSER_CHANNEL, headless: true });
    const context = await browser.newContext({ serviceWorkers: 'block', acceptDownloads: false, viewport: { width: 1100, height: 850 } });
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== ORIGIN || !['GET', 'HEAD'].includes(request.method())) {
        blockedRequests.push({ url: url.origin + url.pathname, method: request.method() });
        return route.abort('blockedbyclient');
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => pageErrors.push(error.message));
    const cli = async (...args) => JSON.parse((await python(['-m', 'backend.app.cli', '--root', fixture.root, ...args])).stdout);
    let lastObservation;
    async function observe() {
      assert.equal(page.url(), ORIGIN + '/');
      const policy = await page.locator('#policy').innerText();
      assert.match(policy, /Automated filling and file selection are permitted here/);
      assert.equal(await page.getByRole('button', { name: 'Submit disabled in dry run', exact: true }).isDisabled(), true);
      const controls = await page.locator('input').evaluateAll(inputs => inputs.map(input => ({
        label: [...input.labels].map(label => label.textContent.trim()).join(' '), type: input.type, value: input.type === 'file' ? null : input.value,
      })));
      assert.deepEqual(controls.map(control => [control.label, control.type]), [['Full name', 'text'], ['Email', 'email'], ['Preferred name', 'text'], ['Test resume', 'file']]);
      const fileStatus = await page.locator('#file-status').innerText();
      const reviewStatus = await page.getByRole('status').innerText();
      const result = {
        observation_source: 'Actual isolated Edge browser at ' + page.url(),
        observed_url: page.url(), website_permits_automation: true, website_policy_evidence: policy,
        fields: controls.filter(control => control.type !== 'file').map(control => ({
          question: control.label, candidate_field: { 'Full name':'full_name', Email:'email' }[control.label] || null, locator: { label: control.label },
        })),
        upload_controls: { resume: { label: 'Test resume' } },
        captcha: false, mfa: false, login_required: false, form_reviewed: true, legal_review_complete: true,
        fields_filled: controls[0].value === 'Test Candidate' && controls[1].value === 'candidate@example.test' && controls[2].value === 'Test',
        uploads_confirmed: fileStatus === 'Test resume selected: synthetic-browser-resume.txt',
        review_status: reviewStatus,
      };
      lastObservation = result;
      return result;
    }
    const phases = [];
    for (const phase of [1, 2]) {
    workerResult = undefined;
    worker = launch(['-m', 'backend.app.cli', '--root', fixture.root, 'browser-run', fixture.application_id, '--timeout', '120']);
    workerDone = collect(worker).then(result => { workerResult = result; return result; });
    const firstCommand = commands.length;
    const deadline = Date.now() + 120000;
    while (!workerResult && Date.now() < deadline) {
      if (worker.exitCode !== null) { await workerDone; break; }
      assert.equal(worker.exitCode, null, 'The known workflow worker must be live before claiming another action');
      const { command } = await cli('browser-next');
      if (!command) { await pause(100); continue; }
      assert.equal(command.application_id, fixture.application_id);
      let result;
      try {
        if (command.action === 'NAVIGATE') {
          assert.equal(command.payload.test_only, true); assert.equal(command.payload.url, ORIGIN + '/');
          await page.goto(command.payload.url, { waitUntil: 'domcontentloaded' });
          await observe(); result = { ok: true, observation_source: 'Actual isolated browser navigation to ' + page.url() };
        } else if (command.action === 'OBSERVE') {
          result = await observe();
        } else if (command.action === 'FILL') {
          await observe();
          const allowed = { 'Full name': 'Test Candidate', Email: 'candidate@example.test', ...(phase === 2 ? { 'Preferred name':'Test' } : {}) };
          const label = command.payload.locator.label;
          assert.equal(command.payload.value, allowed[label]); assert.ok(Object.hasOwn(allowed, label));
          const input = page.getByLabel(label, { exact: true });
          await input.fill(command.payload.value); assert.equal(await input.inputValue(), command.payload.value);
          result = { ok: true, observation_source: 'Actual isolated browser field value checked: ' + label };
        } else if (command.action === 'UPLOAD') {
          await observe(); assert.equal(command.payload.locator.label, 'Test resume');
          assert.equal(path.resolve(command.payload.path), path.resolve(fixture.resume_file));
          const bytes = await fs.readFile(command.payload.path);
          assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), command.payload.sha256);
          assert.match(bytes.toString('utf8'), /SYNTHETIC_TEST_CANDIDATE/);
          await page.getByLabel('Test resume', { exact: true }).setInputFiles(command.payload.path);
          await page.waitForFunction(() => document.getElementById('file-status').textContent === 'Test resume selected: synthetic-browser-resume.txt');
          assert.equal((await observe()).uploads_confirmed, true);
          result = { ok: true, observation_source: 'Actual isolated browser confirmed the synthetic test file selection' };
        } else {
          throw new Error('This test controller cannot execute submission or unknown actions');
        }
        await cli('browser-reply', command.command_id, '--token=' + command.claim_token, '--result-json', JSON.stringify(result));
        commands.push({ phase, action: command.action, state: 'OBSERVED_AND_ACKNOWLEDGED' });
      } catch (error) {
        await cli('browser-reply', command.command_id, '--token=' + command.claim_token, '--result-json', '{}', '--error=' + error.message).catch(() => {});
        throw error;
      }
    }
    if (!workerResult) throw new Error('Local browser workflow timed out; never repeat an uncertain action');
    assert.equal(workerResult.code, 0, workerResult.stderr);
    const workflowResult = JSON.parse(workerResult.stdout.slice(workerResult.stdout.indexOf('{')));
    assert.equal(workflowResult.submitted, false);
    if (phase === 1) {
      assert.equal(workflowResult.status, 'READY_TO_APPLY');
      assert.deepEqual(workflowResult.unresolved_questions, ['Preferred name']);
      assert.equal(await page.getByLabel('Preferred name', { exact:true }).inputValue(), '');
      await page.screenshot({ path: path.join(fixture.root, 'browser-paused-for-question.png'), fullPage:true });
      assert.deepEqual(commands.slice(firstCommand).map(command => command.action), ['NAVIGATE', 'OBSERVE', 'FILL', 'FILL', 'UPLOAD', 'OBSERVE']);
      // Deliberate synthetic fixture input, not a claim of real user confirmation.
      await fs.writeFile(path.join(fixture.root, 'data', 'application_answers.json'), JSON.stringify([
        { question:'Preferred name', normalised_question:'preferred name', answer:'Test', verified:true,
          requires_manual_confirmation:false, last_verified:new Date().toISOString(), source:'Synthetic browser test input only' },
      ], null, 2));
    } else {
      assert.equal(workflowResult.status, 'WAITING_FOR_APPROVAL');
      assert.deepEqual(workflowResult.unresolved_questions, []);
      assert.deepEqual(commands.slice(firstCommand).map(command => command.action), ['NAVIGATE', 'OBSERVE', 'FILL', 'FILL', 'FILL', 'UPLOAD', 'OBSERVE']);
    }
    phases.push({ phase, status:workflowResult.status, unresolved_questions:workflowResult.unresolved_questions, submitted:false });
    }
    assert.equal(lastObservation.review_status, 'READY FOR REVIEW — no application submitted.');
    assert.equal(pageErrors.length, 0, pageErrors.join('\n')); assert.equal(blockedRequests.length, 0);
    const queue = await cli('browser-status');
    assert.ok(queue.commands.every(command => command.state === 'ACKNOWLEDGED'));
    assert.equal(queue.runs[0].state, 'DONE');
    const refusal = await python(['-m', 'backend.app.cli', '--root', fixture.root, 'browser-run', fixture.application_id, '--phase', 'submit'], true);
    assert.notEqual(refusal.code, 0); assert.match(refusal.stderr, /local browser fixture cannot submit/);
    const screenshot = path.join(fixture.root, 'browser-ready-for-review.png');
    await page.screenshot({ path: screenshot, fullPage: true });
    const report = { result: 'PASS', tested_at: new Date().toISOString(), scope: 'Actual local browser transport only, not a real employer or real resume validation',
      application_id: fixture.application_id, isolated_root: fixture.root, browser_version: browser.version(),
      candidate_data: 'Synthetic test identity only', pause_resume_verified:true, phases, commands, final_status: 'WAITING_FOR_APPROVAL', submitted: false,
      fixture_submission_refused: true, external_page_requests: 0, page_errors: pageErrors, observation: lastObservation, screenshot };
    await fs.writeFile(path.join(fixture.root, 'browser-smoke-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally {
    if (worker && worker.exitCode === null) worker.kill();
    if (workerDone) await workerDone;
    if (browser) await browser.close();
    if (server.listening) await new Promise(resolve => server.close(resolve));
  }
}
main().catch(error => { console.error(error.stack || String(error)); process.exitCode = 1; });
