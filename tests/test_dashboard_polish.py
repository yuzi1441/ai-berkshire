import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "site/assets/app.js"


@unittest.skipUnless(shutil.which("node"), "Node required")
class DashboardPolishTests(unittest.TestCase):
    def run_js(self, names, setup, checks):
        app = APP.read_text()
        functions = []
        for name in names:
            match = re.search(r"(?:async )?function " + name + r"\(", app)
            following = re.search(r"\n(?:async )?function ", app[match.end():])
            end = match.end() + following.start() if following else len(app)
            functions.append(app[match.start():end])
        result = subprocess.run(["node", "--input-type=module"],
                                input=setup + "\n" + "\n".join(functions) + "\n" + checks,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_initial_latest_projection_and_old_response_cannot_overwrite(self):
        records = json.loads((ROOT / "site/data/company_state.json").read_text())["companies"]
        self.run_js(["loadJson", "loadData", "indexByTicker", "normalizeTracking",
                     "lightThesisFilterValue", "shouldRefreshOnPageResume", "refreshDataOnPageResume"],
                    '''import assert from 'node:assert/strict';
const state = {loadSequence: 0, companyState: new Map()};
let dataRequestSequence = 0;
const PAGE_RESUME_REFRESH_AGE_MS = 60000;
const DATA_FILES = {companyState: './data/company_state.json'};
const OPTIONAL_DATA_FALLBACKS = {};
const els = {attentionList:{}, holdingList:{}};
const document = {visibilityState: 'visible'};
function toast() {}
function populateDynamicFilters() {}
function renderAll() {}
function syncWorkspaceFromLocation() {}
const pending = [];
const fetch = (url, options) => new Promise(resolve => pending.push({url, options, resolve}));
const reply = (request, companies) => request.resolve({ok:true,json:async()=>({companies})});
''' + 'const records = ' + json.dumps(records) + ';', '''
const initial = loadData();
assert.equal(pending[0].options.cache, 'no-store');
reply(pending.shift(), records);
await initial;
for (const signal of ['improved','unchanged','weakened','insufficient_evidence']) {
 assert.equal([...state.companyState.values()].filter(r=>lightThesisFilterValue(r)===signal).length,
 records.filter(r=>r.light_thesis_signal?.status==='current' && r.light_thesis_signal.signal===signal).length);
}
const old = loadData({silent:true});
const fresh = loadData({silent:true});
assert.notEqual(pending[0].url, pending[1].url);
reply(pending[1], [{ticker:'NEW',light_thesis_signal:{status:'current',signal:'improved'}}]);
await fresh;
reply(pending[0], [{ticker:'OLD'}]);
assert.equal(await old, false);
assert.deepEqual([...state.companyState.keys()], ['NEW']);
pending.length=0;
state.loadedAt = new Date(Date.now()-61000).toISOString();
const resume = refreshDataOnPageResume();
reply(pending.shift(), records); await resume;
assert.equal(state.companyState.size, records.length);
assert.equal(await refreshDataOnPageResume(), false);
const bfcache = refreshDataOnPageResume({force:true});
reply(pending.shift(), [{ticker:'RESTORED'}]); await bfcache;
assert.deepEqual([...state.companyState.keys()], ['RESTORED']);
const manual = loadData({silent:true});
reply(pending.shift(), records); await manual;
assert.equal(state.companyState.size, records.length);
''')
        app = APP.read_text()
        self.assertIn('bindEvents();\nloadData()', app)
        self.assertIn('if (event.persisted) void refreshDataOnPageResume({ force: true });', app)

    def test_skill_display_and_canonical_filter_values(self):
        app = APP.read_text()
        labels = re.search(r'const SKILL_DISPLAY_LABELS = \{.*?\n\};', app, re.S).group()
        self.run_js(["escapeHtml", "guidanceFor", "skillDisplayLabel", "recommendedSkillIds",
                     "recommendedSkillText", "renderRecommendedSkill", "skillMatches",
                     "setSelectOptions"],
                    "import assert from 'node:assert/strict';\n" + labels, '''
for (const [id, label] of Object.entries(SKILL_DISPLAY_LABELS)) {
 const record={action_guidance:{requires_user_action:true,recommended_skill:[id]}};
 const original=JSON.stringify(record);
 assert.equal(recommendedSkillText(record),label);
 assert.ok(renderRecommendedSkill(record).includes('<small>'+id+'</small>'));
 const select={};setSelectOptions(select,[{value:id,label:skillDisplayLabel(id)}],id);
 assert.ok(select.innerHTML.includes('value="'+id+'"'));
 assert.ok(select.innerHTML.includes(label));
 assert.equal(skillMatches(record,id),true);
 assert.equal(skillMatches(record,label),false);
 assert.equal(JSON.stringify(record),original);
}
''')

    def test_ai_module_independent_of_zero_and_cleared_company_filters(self):
        self.run_js(["escapeHtml", "aiScanState", "aiScanAssessments", "aiScanClassification",
                     "aiOpportunityItems", "renderAiOpportunities", "aiScanStatusText", "resetFilterState"],
                    '''import assert from 'node:assert/strict';
const state={opportunityScanMeta:{status:'missing'},opportunityScans:new Map(),search:'no-match'};
const els={aiOpportunityMeta:{},aiOpportunityList:{},aiOpportunityViewAll:{}};
function opportunityScanDayStatus(meta){return meta.status;}
function currentRecord(ticker){return {ticker,company:'Fixture'};}
function renderAiOpportunityCard(item){return item.record.ticker;}
function formatDateTime(value){return value || '—';}
''', '''
renderAiOpportunities();
assert.ok(els.aiOpportunityList.innerHTML.includes('暂无'));
state.opportunityScanMeta={status:'ok',scan_count:1,expected_scan_count:1};
state.opportunityScans.set('FIXTURE',{ticker:'FIXTURE',status:'ready',assessment:{opportunity_state:'机会'}});
renderAiOpportunities();
assert.ok(els.aiOpportunityList.innerHTML.includes('FIXTURE'));
const before=els.aiOpportunityList.innerHTML;
resetFilterState();renderAiOpportunities();
assert.equal(els.aiOpportunityList.innerHTML,before);
''')
