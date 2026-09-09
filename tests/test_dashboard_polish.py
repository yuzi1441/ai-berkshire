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
    def test_delayed_disposition_response_cannot_close_new_task(self):
        self.run_js(["submitDisposition", "applyDispositionAuthority", "dispositionOverlayMatches"], '''
import assert from 'node:assert/strict';
const task = (fp) => ({ticker:'X', manual_disposition:{disposition_target_fingerprint:fp}, action_guidance:{requires_user_action:true}});
const state = {pendingDisposition:{ticker:'X'}, companyState:new Map([['X',task('A')]])};
const els = {dispositionConfirm:{},dispositionDialog:{close(){}}};
const currentRecord = ticker => state.companyState.get(ticker);
let respond;
const fetch = () => new Promise(resolve => {respond=resolve;});
let reloads=0;
const loadData = async () => {reloads++;};
const renderAll=()=>{}, renderDetail=()=>{}, toast=()=>{};
''', '''
const saving=submitDisposition();
state.companyState.set('X',task('B'));
const oldOverlay={...task('A'),action_guidance:{requires_user_action:false}};
respond({ok:true,json:async()=>({resolved_current_task:oldOverlay})});
await saving;
assert.equal(reloads,1);
assert.equal(currentRecord('X').action_guidance.requires_user_action,true);
applyDispositionAuthority({authorized:true,payload:{resolved_companies:[oldOverlay]}});
assert.equal(currentRecord('X').action_guidance.requires_user_action,true);
applyDispositionAuthority({authorized:true,payload:{resolved_companies:[{...task('B'),action_guidance:{requires_user_action:false}}]}});
assert.equal(currentRecord('X').action_guidance.requires_user_action,false);
''')

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
        self.run_js(["loadJson", "loadDispositionAuthority", "applyDispositionAuthority", "dispositionOverlayMatches",
                     "loadData", "indexByTicker", "normalizeTracking",
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
const fetch = (url, options) => String(url).startsWith('/api/')
 ? Promise.resolve({ok:false,status:403})
 : new Promise(resolve => pending.push({url, options, resolve}));
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

    def test_light_thesis_reason_and_checklist_labels_are_display_only(self):
        app = APP.read_text()
        labels = re.search(r'const CHECKLIST_DISPLAY_LABELS = \{.*?\n\};', app, re.S).group()
        self.run_js(
            ["escapeHtml", "shortText", "checklistDisplayLabel", "lightThesisSignalLabel", "renderLightThesisReason"],
            "import assert from 'node:assert/strict';\n" + labels + '''
function formatDate(value){return value || '—';}
function formatDateTime(value){return value || '—';}
''',
            '''
assert.equal(checklistDisplayLabel('PASS'),'通过');
assert.equal(checklistDisplayLabel('CONDITIONAL_PASS'),'条件通过');
assert.equal(checklistDisplayLabel('FAIL'),'未通过');
assert.equal(checklistDisplayLabel('UNKNOWN'),'尚未检查');
assert.equal(checklistDisplayLabel('unexpected'),'尚未检查');
const record={light_thesis_signal:{
 status:'current',signal:'improved',summary:'订单兑现与盈利质量改善',
 checked_at:'2026-09-07T18:00:00+08:00',model:'luna',provider:'codex',provenance:'local',
 material_evidence:[1,2,3,4,5].map(n=>({summary:'证据'+n,source:'来源'+n,date:'2026-09-0'+n}))
}};
const html=renderLightThesisReason(record);
for (const expected of ['轻量投资逻辑','改善','为什么','订单兑现与盈利质量改善','关键证据','检查时间','轻量检查，不等于正式 Thesis Drift','luna · codex · local']) assert.ok(html.includes(expected));
for (const expected of ['证据1','证据2','证据3','证据4']) assert.ok(html.includes(expected));
assert.ok(!html.includes('证据5'));
assert.equal(renderLightThesisReason({light_thesis_signal:{status:'stale'}}),'');
''',
        )
        index = (ROOT / "site/index.html").read_text()
        for value, label in {
            "PASS": "通过", "CONDITIONAL_PASS": "条件通过",
            "FAIL": "未通过", "UNKNOWN": "尚未检查",
        }.items():
            self.assertIn(f'<option value="{value}">{label}</option>', index)
        self.assertIn('checklistStatus === filters.checklist', app)

    def test_human_disposition_buttons_are_explicit_localized_and_admin_only(self):
        app = APP.read_text()
        labels = re.search(r'const DISPOSITION_LABELS = \{.*?\n\};', app, re.S).group()
        self.run_js(
            ["escapeHtml", "renderDispositionControls"],
            "import assert from 'node:assert/strict';\n" + labels + '''
const state={dispositionAccess:true};
function formatDateTime(value){return value || '—';}
''',
            '''
const options=['keep_watch','redo_research','formal_drift','archive_drop'];
const actionable={action_guidance:{requires_user_action:true},manual_disposition:{allowed_options:options,status:'none',disposition_target_fingerprint:'a'.repeat(64)}};
const html=renderDispositionControls(actionable);
for (const expected of ['继续观察','重做研究','正式 Drift','停止重点跟踪','需要本人确认']) assert.ok(html.includes(expected));
assert.ok(html.includes('不会删除研究、不改持仓、不设为已退出'));
assert.equal(renderDispositionControls({action_guidance:{requires_user_action:false},manual_disposition:{allowed_options:options,status:'none'}}),'');
state.dispositionAccess=false;
assert.ok(renderDispositionControls(actionable).includes('公开看板不能写入任何决定'));
const recorded={action_guidance:{requires_user_action:false},manual_disposition:{allowed_options:options,status:'current',selected_disposition:'keep_watch',selected_at:'2026-09-09'}};
assert.ok(renderDispositionControls(recorded).includes('已记录'));
assert.ok(!renderDispositionControls(recorded).includes('data-disposition='));
''',
        )
        self.assertIn('body: JSON.stringify(pending)', app)
        self.assertIn('disposition_target_fingerprint', app)

    def test_ai_module_independent_of_zero_and_cleared_company_filters(self):
        self.run_js(["escapeHtml", "aiScanState", "aiScanAssessments", "aiScanClassification",
                     "opportunityScanDisplayTimestamp", "hasDisplayableOpportunityScan",
                     "opportunityScanDisplayMode", "aiOpportunityDisplayStatusText",
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
state.opportunityScanMeta={status:'ok',generated_at:'2026-09-09T10:00:00+08:00',display_result_generated_at:'2026-09-09T10:00:00+08:00',display_scan_count:1,display_expected_scan_count:1};
state.opportunityScans.set('FIXTURE',{ticker:'FIXTURE',status:'ready',assessment:{opportunity_state:'机会'}});
renderAiOpportunities();
assert.ok(els.aiOpportunityList.innerHTML.includes('FIXTURE'));
const before=els.aiOpportunityList.innerHTML;
resetFilterState();renderAiOpportunities();
assert.equal(els.aiOpportunityList.innerHTML,before);
''')

    def test_ai_opportunity_last_success_survives_midnight_and_failed_refresh(self):
        self.run_js(
            ["escapeHtml", "opportunityScanDayStatus", "opportunityScanDisplayTimestamp",
             "hasDisplayableOpportunityScan", "opportunityScanDisplayMode",
             "aiOpportunityDisplayStatusText", "aiNavigationCount", "aiScanState",
             "aiScanAssessments", "aiScanClassification", "aiScanStatusText",
             "aiOpportunityItems", "renderAiOpportunities"],
            '''import assert from 'node:assert/strict';
const yesterday='2026-09-08T22:28:00+08:00';
const state={opportunityScanMeta:{
 status:'ok',scan_generated_at:yesterday,display_result_generated_at:yesterday,
 display_scan_count:93,display_expected_scan_count:93,
 display_current_opportunity_count:1,display_near_opportunity_count:0,
},opportunityScans:new Map(),aiOpportunityExpanded:false};
const els={aiOpportunityMeta:{},aiOpportunityList:{},aiOpportunityViewAll:{}};
function todayInShanghai(){return '2026-09-09';}
function formatDate(value){return String(value || '').slice(0,10);}
function formatDateTime(value){return value || '—';}
function currentRecord(ticker){return {ticker,company:'Fixture'};}
function renderAiOpportunityCard(item){return item.record.ticker;}
''',
            '''
state.opportunityScans.set('FIXTURE',{ticker:'FIXTURE',status:'ready',generated_at:yesterday,assessment:{opportunity_state:'机会'}});
assert.equal(opportunityScanDayStatus(state.opportunityScanMeta),'not_run_today');
assert.equal(hasDisplayableOpportunityScan(state.opportunityScanMeta),true);
assert.equal(aiOpportunityItems().length,1);
assert.equal(aiNavigationCount(),'1');
renderAiOpportunities();
assert.ok(els.aiOpportunityList.innerHTML.includes('FIXTURE'));
assert.ok(els.aiOpportunityMeta.textContent.includes('今日尚未刷新'));
assert.ok(els.aiOpportunityMeta.textContent.includes('展示最近一次成功结果'));
assert.ok(els.aiOpportunityMeta.textContent.includes(yesterday));
state.opportunityScanMeta.status='error';
state.opportunityScanMeta.attempted_at='2026-09-09T18:10:00+08:00';
renderAiOpportunities();
assert.ok(els.aiOpportunityList.innerHTML.includes('FIXTURE'));
assert.ok(els.aiOpportunityMeta.textContent.includes('今日刷新失败'));
assert.ok(!els.aiOpportunityMeta.textContent.includes('已完成'));
state.opportunityScans.clear();
state.opportunityScanMeta={status:'missing'};
assert.equal(aiOpportunityItems().length,0);
assert.equal(aiNavigationCount(),'—');
renderAiOpportunities();
assert.ok(els.aiOpportunityList.innerHTML.includes('暂无'));
''',
        )
