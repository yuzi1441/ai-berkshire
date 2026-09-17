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
    def test_price_trigger_identifies_exact_zone_and_filters_by_state_or_rule(self):
        self.run_js(
            ["priceRuleExpression", "currentMatchedPriceZoneSummary", "priceTriggerDisplayLabel",
             "priceTriggerPathLabel", "matchedPriceZoneGroups", "priceZoneGroupKey",
             "priceTriggerStateMatches", "priceTriggerZoneMatches", "formatNumber"],
            '''
import assert from 'node:assert/strict';
const zone={rule_id:'moutai-1100-1300',operator:'BETWEEN',price_min:1100,price_max:1300,
 currency:'CNY',action:'OPEN_POSITION',price_role:'CONDITIONAL_ENTRY'};
const record={price_trigger_shadow:{price_state:'PRICE_ZONE_MATCHED',matched_rule_ids:[zone.rule_id],matched_price_zones:[zone]}};
''',
            '''
assert.equal(priceRuleExpression(zone),'1,100–1,300');
assert.equal(currentMatchedPriceZoneSummary(record),'1,100–1,300 CNY · 条件建仓价格参考（非买入资格）');
assert.equal(priceTriggerStateMatches(record,'matched'),true);
assert.equal(priceTriggerStateMatches(record,'OUTSIDE_PRICE_ZONE'),false);
assert.equal(priceTriggerZoneMatches(record,'moutai-1100-1300'),true);
assert.equal(priceTriggerZoneMatches(record,'another-zone'),false);
''',
        )

    def test_same_price_review_and_entry_paths_are_grouped_without_buy_claim(self):
        self.run_js(
            ["priceRuleExpression", "currentMatchedPriceZoneSummary", "priceTriggerDisplayLabel",
             "priceTriggerPathLabel", "matchedPriceZoneGroups", "priceZoneGroupKey",
             "priceTriggerStateLabelForRecord", "formatNumber"],
            '''
import assert from 'node:assert/strict';
const base={operator:'BETWEEN',price_min:43,price_max:46,currency:'CNY',scope:'empty_position'};
const record={price_trigger_shadow:{price_state:'MULTIPLE_PRICE_ZONES_MATCHED',matched_price_zones:[
 {...base,action:'OPEN_POSITION',price_role:'CONDITIONAL_ENTRY',path_semantic_status:'ready'},
 {...base,action:'REVIEW',price_role:'REVIEW_ZONE',path_semantic_status:'ambiguous'},
]}};
''',
            '''
assert.equal(currentMatchedPriceZoneSummary(record),'43–46 CNY · 重新审视区 / 条件建仓价格参考（非买入资格） · 语义待澄清');
assert.equal(matchedPriceZoneGroups(record).length,1);
assert.equal(priceTriggerStateLabelForRecord(record),'已进入关注区间（含多条报告路径）');
assert.ok(!currentMatchedPriceZoneSummary(record).includes('空仓首次建仓'));
''',
        )

    def test_candidate_shadow_localizes_display_without_mutating_machine_values(self):
        self.run_js(
            ["renderCandidateShadow", "candidateDisplayLabel", "candidateMachineValue",
             "candidateListValue", "formatNumber", "escapeHtml"],
            '''
import assert from 'node:assert/strict';
const machine = {
 candidate_state:'BUY_READY', publication_status:'STRONG_REVIEW_PASSED',
 current_price:4.68, currency:'CNY', matched_path_ids:['conditional-4.3-4.8'],
 mandatory_gate_count:1, mandatory_gate_ids:['price-gate'],
 unknown_mandatory_gate_ids:[], alternative_unknown_gate_ids:['catalyst-a','catalyst-b'],
 hard_block_state:'not_applicable', semantic_review_status:'PASS',
 price_cutoff:'2026-09-16', production_eligible:false,
};
const record={candidate_shadow:machine};
''',
            '''
const before=JSON.stringify(machine), html=renderCandidateShadow(record);
assert.ok(html.includes('完整候选判断（研究 / 审计）'));
assert.ok(html.includes('历史快照'));
assert.ok(html.includes('满足候选买入条件'));
assert.ok(html.includes('强复核已通过'));
assert.ok(html.includes('当前价格'));
assert.ok(html.includes('4.68 元'));
assert.ok(html.includes('已命中 1 条路径'));
assert.ok(html.includes('必须条件待确认'));
assert.ok(html.includes('>无<'));
assert.ok(html.includes('2 项待确认'));
assert.ok(html.includes('不适用'));
assert.ok(html.includes('通过'));
assert.ok(html.includes('>否<'));
assert.ok(html.includes('data-machine-value="BUY_READY"'));
assert.ok(html.includes('title="原始值：conditional-4.3-4.8"'));
for (const visibleEnglish of ['Candidate Shadow','Candidate State','Publication','Current Price','NOT PRODUCTION']) {
 assert.ok(!html.includes(visibleEnglish));
}
assert.equal(JSON.stringify(machine),before);
const empty=renderCandidateShadow({candidate_shadow:{...machine,matched_path_ids:[],alternative_unknown_gate_ids:[]}});
assert.ok(!empty.includes('>0<'));
assert.equal(renderCandidateShadow({}), '');
''',
        )

    def test_quote_expiry_repaints_without_network_and_waits_for_confirmation(self):
        self.run_js(["scheduleQuoteExpiry", "quoteIsCurrent"], '''
import assert from 'node:assert/strict';
let now=1000, callback, delay, paints=0;
Date.now=()=>now;
const setTimeout=(fn,ms)=>{callback=fn;delay=ms;return 1;};
const clearTimeout=()=>{};
const formatPrice=()=> '10';
const state={quotes:new Map([['A',{quality:{eligible:true,evaluated_at:new Date(0).toISOString(),valid_until:new Date(2000).toISOString()}}]])};
const document={activeElement:null};
const els={drawer:{hidden:true}};
const renderAll=()=>{paints++;scheduleQuoteExpiry();};
''', '''
scheduleQuoteExpiry();assert.equal(delay,1001);
state.pendingDisposition={};now=2001;callback();assert.equal(paints,0);
state.pendingDisposition=null;callback();assert.equal(paints,1);
assert.equal(quoteIsCurrent(state.quotes.get('A')),false);
''')

    def test_holding_snapshot_never_falls_back_to_another_cycle(self):
        self.run_js(["trackingFor", "originalThesisFor", "lifecycleOf", "renderHoldingReview", "escapeHtml", "formatDate"], '''
import assert from 'node:assert/strict';
const old={position_id:'OLD',ticker:'A',source_text:'old thesis'};
const state={tracking:new Map([['A',{position_id:'OLD'}]]),originalTheses:{active_position_ids:{A:'OLD'},cycles:{OLD:old}}};
const record={ticker:'A',lifecycle:'HOLDING',post_buy_tracking:{position_id:'NEW'}};
''', '''
assert.equal(trackingFor(record).position_id,'NEW');
assert.equal(originalThesisFor(record),null);
state.originalTheses.active_position_ids.A='NEW';assert.equal(originalThesisFor(record),null);
state.originalTheses.cycles.NEW={position_id:'NEW',ticker:'A',source_text:'current'};
assert.equal(originalThesisFor(record).source_text,'current');
state.originalTheses.cycles.NEW.ticker='B';assert.equal(originalThesisFor(record),null);
const invalid={research_binding_status:'binding_mismatch',review_action:'清仓'};
assert.ok(!renderHoldingReview(invalid).includes('清仓'));
assert.ok(renderHoldingReview({...invalid,research_binding_status:'matched',last_review_date:'2026-09-01',next_review_date:'2026-10-01'}).includes('清仓（不是成交记录）'));
''')

    def test_missing_financial_values_never_render_zero_or_minus_100_percent(self):
        self.run_js(["formatNumber", "formatPrice", "holdingReturn", "quoteIsCurrent"], '''
import assert from 'node:assert/strict';
let quote; const quoteFor=()=>quote;
const quality={eligible:true,evaluated_at:new Date().toISOString(),valid_until:new Date(Date.now()+60000).toISOString()};
''', '''
for (const value of [null, undefined, '', ' ', false, true, NaN, Infinity]) {
 assert.equal(formatNumber(value), '—');
 assert.equal(formatPrice({price:value}), '—');
 quote={price:value,quality};assert.equal(holdingReturn({}, {cost_basis:10}), null);
 quote={price:10,quality};assert.equal(holdingReturn({}, {cost_basis:value}), null);
}
for (const value of [0,-1]) {
 quote={price:10,quality};assert.equal(holdingReturn({}, {cost_basis:value}), null);
}
quote={price:12,quality};assert.ok(Math.abs(holdingReturn({}, {cost_basis:10})-.2)<1e-9);
assert.equal(formatNumber(0), '0');
assert.equal(formatPrice({price:12,currency:'HKD'}), 'HK$12');
''')

    def test_timestamps_are_shanghai_instants_not_offset_stripping(self):
        self.run_js(["formatDateTime"], "import assert from 'node:assert/strict';", '''
assert.equal(formatDateTime('2026-09-11T20:00:00Z'), '2026-09-12 04:00');
assert.equal(formatDateTime('2026-09-12T04:00:00+08:00'), '2026-09-12 04:00');
assert.equal(formatDateTime('2026-09-12'), '2026-09-12');
assert.equal(formatDateTime(null), '—');
''')

    def test_quote_load_failure_missing_and_valid_coverage_are_distinct(self):
        self.run_js(["loadOptionalJson", "renderTopMeta", "formatPrice", "formatNumber", "formatDateTime", "formatDate", "quoteIsCurrent"], '''
import assert from 'node:assert/strict';
let error={status:404}; const loadJson=async()=>{throw error;};
const state={board:{},companyStateMeta:{source_sha:'abc12345xxxx'},rulePackages:new Map(),quotes:new Map()};
const records=[{ticker:'A',market:'A股'},{ticker:'H',market:'港股'},{ticker:'U',market:'美股'}];
const stateRecords=()=>records;
const location={hostname:'127.0.0.1'};
const els={lastUpdated:{},dataSource:{},datasetSummary:{},quoteStatus:{dataset:{}},quoteStatusText:{}};
const quality={eligible:true,evaluated_at:new Date().toISOString(),valid_until:new Date(Date.now()+60000).toISOString()};
''', '''
state.quoteMeta=await loadOptionalJson('q',()=>({quotes:[]}));renderTopMeta();
assert.ok(els.quoteStatusText.textContent.includes('尚未取得行情快照'));
assert.ok(els.dataSource.textContent.includes('不代表线上状态'));
error={status:500};state.quoteMeta=await loadOptionalJson('q',()=>({quotes:[]}));renderTopMeta();
assert.ok(els.quoteStatusText.textContent.includes('读取失败'));
state.quoteMeta={source_status:'unavailable',generated_at:'2026-09-12T12:00:00Z'};renderTopMeta();
assert.ok(els.quoteStatusText.textContent.includes('更新失败'));
assert.ok(!els.quoteStatusText.textContent.includes('截至'));
state.quotes=new Map([['A',{price:null}],['H',{price:3,snapshot_status:'preserved_previous'}],['U',{price:5}]]);
state.quoteMeta={source_status:'ok'};renderTopMeta();assert.ok(els.quoteStatusText.textContent.includes('0/2'));
state.quotes.set('A',{price:10,quality});renderTopMeta();assert.ok(els.quoteStatusText.textContent.includes('1/2'));
state.quotes.set('H',{price:3,quality});renderTopMeta();assert.equal(els.quoteStatus.dataset.tone,'fresh');
''')

    def test_review_presence_navigation_and_task_copy_match_projections(self):
        self.run_js(["formalDriftMatches", "attentionReasonType", "guidanceFor", "renderWorkspaceNav", "stateCount", "lifecycleOf", "checklistRecords"], '''
import assert from 'node:assert/strict';
const records=[{lifecycle:'WATCH'},{lifecycle:'HOLDING'},{lifecycle:'EXITED'}];
const stateRecords=()=>records, attentionRecords=()=>[], aiNavigationCount=()=>0;
const els={navWatchlistCount:{}};
''', '''
const checkpoint={drift:{},drift_scan:{checked_at:'2026-09-03',result:'unchanged'}};
assert.equal(formalDriftMatches(checkpoint,'has-review'),true);
assert.equal(formalDriftMatches(checkpoint,'no-review'),false);
assert.equal(formalDriftMatches(checkpoint,'improved'),false);
assert.equal(formalDriftMatches({light_thesis_signal:{checked_at:'2026-09-03'}},'has-review'),false);
assert.equal(attentionReasonType({action_guidance:{task_label:'现在需要研究',next_action_code:'review_portfolio_position'}}),'现在需要研究');
renderWorkspaceNav();assert.equal(els.navWatchlistCount.textContent,'3');
''')

    def test_formal_drift_summary_and_report_are_visible_without_rewriting_authority(self):
        record = next(r for r in json.loads((ROOT / "site/data/company_state.json").read_text())["companies"]
                      if r["ticker"] == "603606.SH")
        self.run_js(["renderFormalDriftResult", "escapeHtml", "formatDateTime"], '''
import assert from 'node:assert/strict';
const label=(_,v)=>v, driftScanLabel=()=>"当前有效", reportHref=p=>'https://example.test/'+p;
''' + 'const record=' + json.dumps(record) + ';', '''
const before=JSON.stringify(record), html=renderFormalDriftResult(record);
assert.ok(html.includes('局部正向漂移但尚未修复'));
assert.ok(html.includes('2026-09-11'));
assert.ok(html.includes('东方电缆-thesis-drift-20260911.md'));
assert.ok(html.includes('不因局部改善自动获得买入资格'));
assert.equal(JSON.stringify(record),before);
assert.equal(renderFormalDriftResult({light_thesis_signal:{signal:'improved'}}),'');
''')

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
                     "loadData", "indexByTicker", "normalizeTracking", "validateDashboardCore",
                     "lightThesisFilterValue", "shouldRefreshOnPageResume", "refreshDataOnPageResume"],
                    '''import assert from 'node:assert/strict';
const state = {loadSequence: 0, companyState: new Map()};
let dataRequestSequence = 0;
const PAGE_RESUME_REFRESH_AGE_MS = 60000;
const DATA_FILES = {core: './data/dashboard_core.json'};
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
const reply = (request, companies) => request.resolve({ok:true,json:async()=>({
 schema_version:1,artifact_role:'derived_dashboard_core',generation_id:'a'.repeat(64),board:{},
 companyState:{companies},rules:{companies:companies.map(c=>({ticker:c.ticker,rules:[]}))}
})});
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
                     "aiOpportunityItems", "renderAiOpportunities", "validScanCount", "aiScanStatusText", "resetFilterState"],
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
             "aiOpportunityItems", "renderAiOpportunities", "validScanCount"],
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
