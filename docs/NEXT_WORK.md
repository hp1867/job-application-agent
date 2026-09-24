# Remaining work and acceptance boundary

Continue the existing project and database. Keep candidate intake deferred, DRY_RUN=true, automation level 2 and final submission disabled. Gmail and all post-application follow-up belong to the user and are excluded.

## Implemented in the latest engineering pass

- Shared fill-only AIHawk executor connected to the durable queue. It verifies the exact active claim, application revision, observed page, website permission, safe source answer and actual control before typing, uploading or continuing. No submit, arbitrary click, login or script-execution action is exposed.
- Actual AIHawk multi-page local acceptance passed after replay protection. Unknown-answer resumption stays on the same page and retains the earlier observed upload.
- Public Greenhouse inspection and a conservative mapping adapter were exercised against the saved nCino Associate Software Engineer page. Real controls were observed with zero blocked requests on the second read-only run. This did not enter applicant data, upload documents or establish automation permission.
- Word extraction preserves paragraph/table order and source paths. PDF extraction retains page provenance, flags blank pages and refuses encrypted or oversized resumes. Ambiguous layouts, revisions, headers/footers and text boxes still require source review. XML and mocked PDF tests are not visual acceptance of a candidate resume.
- Detailed resume coverage is displayed in the local dashboard, with separate required/optional skills and education/experience terms. Unassessed dimensions stay unscored. Post-application navigation and Gmail setup prompts are removed from the active scope.
- Raw education and employment requirements without structured checks now remain NEEDS_REVIEW instead of being silently ignored.

## Still required before calling the whole system finished

1. The user's supplied master resume and verified candidate information, followed by source-backed extraction review and real DOCX/PDF rendering/visual acceptance. Do not ask repeatedly while intake remains deferred.
2. Live employer acceptance: review each website's automation rules, exact application identity and current controls; connect a trusted live observer to AIHawkExecutor. The Greenhouse mapping is a proposal, not a completed permission/evidence observer.
3. Complex dropdowns, date/number controls, multi-frame forms and unmapped uploads must be completed manually or receive a separately tested site-specific adapter. The current generic executor deliberately refuses unsupported controls; it is not a universal ATS bot.
   Standard native single-select dropdowns now have a tested executor extension using exact verified labels and one confirmed selection. A site observer must still review the mapping; the Greenhouse proposal does not automatically approve complex controls.
4. A candidate-backed full dry run that reaches final review on an actual permitted employer form, with every upload and answer observed. Never turn local fixture success into employer acceptance or silently enable production.

## Next execution

Read this file and BUILD_STATUS.md, then resume with the existing state. Run the complete Python suite and the relevant AIHawk fixture test after related changes. The saved-job dry run on 9 September completed without errors, preserved seven duplicates and submitted zero applications. No Gmail access is required for any of the remaining scope.
