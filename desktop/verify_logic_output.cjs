// Read actual synthetic outputs through the production frontend parser.
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
  const {parseReviewResponse, reviewQuoteStatus} = await import(pathToFileURL(path.join(root, 'frontend/src/utils/reviewPresentation.js')).href);
  const bundle = JSON.parse(fs.readFileSync(path.join(root, 'desktop/role_bundle.json'), 'utf8'));
  const source = JSON.parse(fs.readFileSync(path.join(root, 'build/logic-v9-check/results.json'), 'utf8'));
  const records = source.records.filter(record => record.persona !== 'source-editor').map(record => {
    const persona = {id:record.persona, ...bundle.personas[record.persona]};
    const parsed = parseReviewResponse({content:record.content}, persona, record.draft);
    assert.ok(parsed.comments.length, record.case + ' lost all comments');
    assert.equal(parsed.rating.status, 'ok', record.case + ' rating evidence invalid');
    for (const comment of parsed.comments) {
      assert.equal(reviewQuoteStatus(comment.detail.basis, record.draft), 'matched');
      assert.equal(reviewQuoteStatus(comment.detail.context, record.draft), 'matched');
    }
    return {case:record.case, comments:parsed.comments.length, ratingStatus:parsed.rating.status, allQuotesMatch:true};
  });
  const result = {syntheticOnly:true, productionFrontendParser:true, records};
  fs.writeFileSync(path.join(root, 'build/logic-v9-check/frontend.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
})().catch(error => {console.error(error); process.exitCode = 1;});
