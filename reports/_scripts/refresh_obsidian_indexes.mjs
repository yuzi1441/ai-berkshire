#!/usr/bin/env node
(async function refreshObsidianInvestmentVault() {
  const fs = await import('node:fs/promises');
  const fss = await import('node:fs');
  const path = await import('node:path');
  const { fileURLToPath } = await import('node:url');

  let vault;
  try {
    const currentFile = fileURLToPath(import.meta.url);
    vault = path.resolve(path.dirname(currentFile), '..');
  } catch {
    vault = 'C:/Users/whatn/Desktop/vibecoding/codex/投资分析/ai-berkshire/reports';
  }
  if (!fss.existsSync(path.join(vault, '.obsidian'))) {
    vault = 'C:/Users/whatn/Desktop/vibecoding/codex/投资分析/ai-berkshire/reports';
  }
  const indexDir = path.join(vault, '00-index');
  const scriptsDir = path.join(vault, '_scripts');
  const templatesDir = path.join(vault, '_templates');
  const inboxDir = path.join(vault, '_inbox');
  await fs.mkdir(indexDir, { recursive: true });
  await fs.mkdir(scriptsDir, { recursive: true });
  await fs.mkdir(templatesDir, { recursive: true });
  await fs.mkdir(inboxDir, { recursive: true });

  const technicalDirs = new Set(['.obsidian', '00-index', '_scripts', '_templates', '_meta', '_data', '_sources']);
  const generatedNames = new Set(['MOC.md']);
  async function walk(dir) {
    const out = [];
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const ent of entries) {
      const p = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        if (technicalDirs.has(ent.name)) continue;
        out.push(...await walk(p));
      } else {
        if (generatedNames.has(ent.name)) continue;
        out.push(p);
      }
    }
    return out;
  }
  function rel(p) { return path.relative(vault, p).replaceAll('\\\\','/').replaceAll('\\','/'); }
  function stat(p) { return fss.statSync(p); }
  function pad(n) { return String(n).padStart(2, '0'); }
  function mtimeStr(p) { const d = stat(p).mtime; return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`; }
  function dateOnly(p) { return mtimeStr(p).slice(0, 10); }
  function ext(p) { return path.extname(p).toLowerCase() || '[no ext]'; }
  function safeLabel(s) { return String(s || '').replaceAll('|','¦').replaceAll('\n',' ').trim(); }
  function wiki(p, label=null) { const r = rel(p).replace(/\.md$/i, ''); return `[[${r}${label ? '|' + safeLabel(label) : ''}]]`; }
  function wikiByRel(r, label=null) { return `[[${r.replace(/\.md$/i,'')}${label ? '|' + safeLabel(label) : ''}]]`; }
  function yaml(title, tags=[]) { return `---\ntitle: "${String(title).replaceAll('"','\\"')}"\ntype: index\ncreated: 2026-07-08\nupdated: 2026-07-08\ntags: [${tags.map(t=>'"'+t+'"').join(', ')}]\n---\n\n`; }
  function inferWorkflow(name) {
    const n = name.toLowerCase();
    if (/funnel|漏斗/.test(n)) return 'funnel';
    if (/checklist|清单/.test(n)) return 'checklist';
    if (/management|管理层/.test(n)) return 'management';
    if (/news|新闻|脉搏/.test(n)) return 'news';
    if (/valuation|估值|dcf/.test(n)) return 'valuation';
    if (/industry|行业/.test(n)) return 'industry';
    if (/team|private/.test(n)) return 'team-private';
    if (/research|研究报告|投资研究/.test(n)) return 'research';
    return 'other';
  }
  function inferType(p) {
    const name = path.basename(p); const n = name.toLowerCase(); const e = ext(p);
    if (e === '.md') {
      if (/funnel|漏斗/.test(n)) return '报告：行业漏斗/筛选';
      if (/checklist|清单/.test(n)) return '报告：Checklist';
      if (/news|新闻|脉搏/.test(n)) return '报告：新闻/异动';
      if (/management|管理层/.test(n)) return '报告：管理层';
      if (/valuation|估值|dcf/.test(n)) return '报告：估值';
      if (/industry|行业/.test(n)) return '报告：行业研究';
      if (/research|研究报告|投资研究/.test(n)) return '报告：投资研究';
      if (/公众号|播客|笔记|对话/.test(n)) return '文章/笔记';
      return 'Markdown：其他';
    }
    if (['.json','.tmp','.out','.base'].includes(e)) return '中间产物/配置草稿';
    if (['.csv','.xls','.xlsx'].includes(e)) return '数据表';
    if (['.pdf','.html','.txt'].includes(e)) return '资料/下载文本';
    if (['.py','.js','.css'].includes(e)) return '脚本/样式';
    return '其他';
  }
  function suggestedAction(p) {
    const e = ext(p); const t = inferType(p);
    if (e === '.md') {
      if (t.startsWith('报告')) return '后续可归入对应公司/主题目录；移动前先确认是否被其他笔记链接。';
      return '先保留，等 MOC 稳定后再决定是否归档。';
    }
    if (['.json','.tmp','.out','.base'].includes(e)) return '可归入 `_meta` 或 `_temp`。';
    if (['.csv','.xls','.xlsx'].includes(e)) return '可归入 `_data`，并在对应报告中链接数据来源。';
    if (['.py','.js','.css'].includes(e)) return '可归入 `_scripts` 或项目脚本目录。';
    if (['.pdf','.html','.txt'].includes(e)) return '可归入 `_sources` 或对应公司资料目录。';
    return '待人工判断。';
  }
  async function readText(p) { try { return await fs.readFile(p, 'utf8'); } catch { return ''; } }
  function titleOf(p, text) { const m = text.match(/^#\s+(.+)$/m); return m ? m[1].trim() : path.basename(p, '.md'); }

  const all = await walk(vault);
  const files = all.map(p => ({ p, rel: rel(p), st: stat(p), ext: ext(p) }));
  const mdPaths = all.filter(p => ext(p) === '.md');
  const mdInfos = [];
  for (const p of mdPaths) {
    const text = await readText(p);
    mdInfos.push({ p, rel: rel(p), name: path.basename(p), top: rel(p).includes('/') ? rel(p).split('/')[0] : '[root]', st: stat(p), title: titleOf(p, text), workflow: inferWorkflow(path.basename(p)), hasH1: /^#\s+.+$/m.test(text), tiny: stat(p).size < 100, long: stat(p).size > 80*1024 });
  }
  mdInfos.sort((a,b)=>b.st.mtimeMs-a.st.mtimeMs);

  const byTop = new Map();
  for (const x of files) {
    const top = x.rel.includes('/') ? x.rel.split('/')[0] : '[root]';
    const v = byTop.get(top) || { files:0, md:0, size:0, latest:0 };
    v.files++; if (x.ext === '.md') v.md++; v.size += x.st.size; v.latest = Math.max(v.latest, x.st.mtimeMs); byTop.set(top,v);
  }
  const topDirs = [...byTop.entries()].sort((a,b)=>b[1].files-a[1].files);
  const byWorkflow = new Map();
  for (const m of mdInfos) { const arr = byWorkflow.get(m.workflow)||[]; arr.push(m); byWorkflow.set(m.workflow, arr); }

  const rootEntries = await fs.readdir(vault, { withFileTypes: true });
  const rootFiles = rootEntries.filter(e=>e.isFile()).map(e=>path.join(vault,e.name));
  const rootInfos = [];
  for (const p of rootFiles) {
    const text = ext(p)==='.md' ? await readText(p) : '';
    rootInfos.push({ p, name:path.basename(p), ext:ext(p), size:stat(p).size, mtime:stat(p).mtimeMs, title:titleOf(p,text), type:inferType(p), action:suggestedAction(p) });
  }
  rootInfos.sort((a,b)=>b.mtime-a.mtime);

  const priorityNames = ['华明装备','思源电气','腾讯','茅台','拼多多','长江电力','招商银行','国电南瑞','英维克','领益智造','赛力斯','中远海控','泡泡玛特','RKLB','BYD','美团','阿里巴巴','工商银行','迈瑞医疗','东方电子','许继电气','四方股份','港股召回池','bottleneck-map'];
  const mocDirs = topDirs.filter(([name,v]) => name !== '[root]' && !technicalDirs.has(name) && (v.md >= 5 || v.files >= 20 || priorityNames.includes(name))).map(([name])=>name);

  // Generate folder MOCs.
  for (const dirName of mocDirs) {
    const dir = path.join(vault, dirName);
    if (!fss.existsSync(dir) || !fss.statSync(dir).isDirectory()) continue;
    const dirMds = mdInfos.filter(m => m.top === dirName).sort((a,b)=>b.st.mtimeMs-a.st.mtimeMs);
    const dirFiles = files.filter(f => f.rel.split('/')[0] === dirName);
    const wfCounts = new Map();
    for (const m of dirMds) wfCounts.set(m.workflow, (wfCounts.get(m.workflow)||0)+1);
    let moc = yaml(`${dirName} MOC`, ['obsidian','investment','moc']);
    moc += `# ${dirName} MOC\n\n> 自动生成的目录导航页。可手工在本页顶部补充你的判断，但刷新脚本会覆盖全文；如果要写长期观点，建议新建单独笔记。\n\n`;
    moc += `## 概况\n\n- 文件数：${dirFiles.length}\n- Markdown：${dirMds.length}\n- 最近更新：${dirMds[0] ? mtimeStr(dirMds[0].p) : '无'}\n\n`;
    moc += `## 工作流分布\n\n${[...wfCounts.entries()].sort((a,b)=>b[1]-a[1]).map(([k,v])=>`- \`${k}\`：${v}`).join('\n') || '- 暂无'}\n\n`;
    moc += `## 推荐阅读顺序\n\n`;
    const preferred = dirMds.filter(m=>['research','funnel','checklist','valuation','management','news','industry'].includes(m.workflow)).slice(0,20);
    moc += (preferred.length ? preferred : dirMds.slice(0,20)).map(m=>`- ${dateOnly(m.p)} · ${wiki(m.p, m.title)} · \`${m.workflow}\``).join('\n') || '- 暂无';
    moc += `\n\n## 最近更新\n\n${dirMds.slice(0,50).map(m=>`- ${mtimeStr(m.p)} · ${wiki(m.p, m.title)} · ${(m.st.size/1024).toFixed(1)} KB`).join('\n') || '- 暂无'}\n`;
    await fs.writeFile(path.join(dir, 'MOC.md'), moc, 'utf8');
  }

  const recent = mdInfos.slice(0, 80);
  const noH1 = mdInfos.filter(m=>!m.hasH1).slice(0,100);
  const tiny = mdInfos.filter(m=>m.tiny).slice(0,100);
  const long = mdInfos.filter(m=>m.long).sort((a,b)=>b.st.size-a.st.size).slice(0,100);

  let home = yaml('投资研究总览', ['obsidian','investment','index']);
  home += `# 投资研究总览\n\n> 这是这个投资报告 Obsidian 库的主入口。索引可通过 \`_scripts/refresh_obsidian_indexes.mjs\` 重新生成。\n\n`;
  home += `## 快速入口\n\n- [[00-index/最近更新|最近更新]]\n- [[00-index/目录导航|目录导航]]\n- [[00-index/工作流索引|工作流索引]]\n- [[00-index/重点公司索引|重点公司索引]]\n- [[00-index/待复核|待复核]]\n- [[00-index/根目录整理建议|根目录整理建议]]\n- [[00-index/新增内容规则|新增内容规则]]\n\n`;
  home += `## 库概况\n\n- Vault：\`${vault}\`\n- 文件总数：${files.length}\n- Markdown：${mdInfos.length}\n- 已生成目录 MOC：${mocDirs.length}\n- 根目录散放文件：${rootFiles.length}\n- 生成时间：2026-07-08\n\n`;
  home += `## 最大目录\n\n${topDirs.slice(0,30).map(([name,v])=>`- ${name==='[root]'?'`[root]`':wikiByRel(`${name}/MOC`, name)}：${v.files} files / ${v.md} md / ${(v.size/1024/1024).toFixed(1)} MB`).join('\n')}\n\n`;
  home += `## 阅读建议\n\n1. 看最新研究：打开 [[00-index/最近更新|最近更新]]。\n2. 按公司/主题深入：打开 [[00-index/目录导航|目录导航]] 或具体目录的 MOC。\n3. 按工作流找报告：打开 [[00-index/工作流索引|工作流索引]]。\n4. 新增内容：先看 [[00-index/新增内容规则|新增内容规则]]。\n`;

  let recentMd = yaml('最近更新', ['obsidian','investment','recent']);
  recentMd += `# 最近更新\n\n${recent.map(m=>`- ${mtimeStr(m.p)} · ${wiki(m.p, m.title)} · \`${m.workflow}\` · ${(m.st.size/1024).toFixed(1)} KB`).join('\n')}\n`;

  let nav = yaml('目录导航', ['obsidian','investment','navigation']);
  nav += `# 目录导航\n\n> 按顶层目录进入。大目录已自动生成 MOC。\n\n`;
  nav += `| 目录 | 文件数 | Markdown | 大小 | 最近更新 |\n|---|---:|---:|---:|---|\n`;
  for (const [name,v] of topDirs) {
    if (name === '[root]') nav += `| \`[root]\` | ${v.files} | ${v.md} | ${(v.size/1024/1024).toFixed(1)} MB | - |\n`;
    else nav += `| ${mocDirs.includes(name) ? wikiByRel(`${name}/MOC`, name) : '`'+name+'`'} | ${v.files} | ${v.md} | ${(v.size/1024/1024).toFixed(1)} MB | ${v.latest ? new Date(v.latest).toISOString().slice(0,10) : '-'} |\n`;
  }

  let workflowMd = yaml('工作流索引', ['obsidian','investment','workflow']);
  workflowMd += `# 工作流索引\n\n`;
  for (const wf of ['research','funnel','checklist','valuation','management','news','industry','team-private','other']) {
    const arr = (byWorkflow.get(wf)||[]);
    workflowMd += `## ${wf} (${arr.length})\n\n${arr.slice(0,120).map(m=>`- ${dateOnly(m.p)} · ${wiki(m.p, m.title)} · \`${m.rel}\``).join('\n') || '- 暂无'}\n\n`;
  }

  let companyMd = yaml('重点公司索引', ['obsidian','investment','company']);
  companyMd += `# 重点公司索引\n\n> 常看公司/主题的快捷入口。更多目录见 [[00-index/目录导航|目录导航]]。\n\n`;
  for (const name of priorityNames) {
    const items = mdInfos.filter(m => m.rel.includes(name) || m.name.includes(name)).slice(0, 15);
    const mocLink = fss.existsSync(path.join(vault, name, 'MOC.md')) ? ` · ${wikiByRel(`${name}/MOC`, 'MOC')}` : '';
    if (items.length) companyMd += `## ${name}${mocLink}\n\n${items.map(m=>`- ${mtimeStr(m.p)} · ${wiki(m.p, m.title)} · \`${m.workflow}\``).join('\n')}\n\n`;
  }

  let reviewMd = yaml('待复核', ['obsidian','investment','review']);
  reviewMd += `# 待复核\n\n> 这里是整理线索，不代表文件一定有错。\n\n`;
  reviewMd += `## 缺少一级标题（前 100）\n\n${noH1.map(m=>`- ${wiki(m.p, m.title)} · \`${m.rel}\``).join('\n') || '- 无'}\n\n`;
  reviewMd += `## 疑似空/占位 Markdown（前 100）\n\n${tiny.map(m=>`- ${wiki(m.p, m.title)} · ${m.st.size} bytes · \`${m.rel}\``).join('\n') || '- 无'}\n\n`;
  reviewMd += `## 超长 Markdown（前 100）\n\n${long.map(m=>`- ${wiki(m.p, m.title)} · ${(m.st.size/1024).toFixed(1)} KB · \`${m.rel}\``).join('\n') || '- 无'}\n`;

  const byExt = new Map();
  const byType = new Map();
  for (const x of rootInfos) { byExt.set(x.ext, (byExt.get(x.ext)||0)+1); const arr=byType.get(x.type)||[]; arr.push(x); byType.set(x.type,arr); }
  let rootAdvice = yaml('根目录整理建议', ['obsidian','investment','cleanup']);
  rootAdvice += `# 根目录整理建议\n\n> 建议清单，不是执行结果。当前刷新脚本不会移动、删除、重命名根目录文件。\n\n`;
  rootAdvice += `## 摘要\n\n- 根目录散放文件：${rootInfos.length}\n- 建议原则：先建索引，再小批量归档；每次移动前确认 Obsidian 链接和报告引用。\n\n## 按扩展名统计\n\n${[...byExt.entries()].sort((a,b)=>b[1]-a[1]).map(([e,c])=>`- \`${e}\`：${c}`).join('\n')}\n\n`;
  rootAdvice += `## 按类型分组清单\n\n`;
  for (const [type, arr] of [...byType.entries()].sort((a,b)=>b[1].length-a[1].length)) {
    rootAdvice += `### ${type}（${arr.length}）\n\n${arr.map(x=>`- ${mtimeStr(x.p)} · ${x.ext==='.md'?wiki(x.p,x.title):'`'+x.name+'`'} · ${(x.size/1024).toFixed(1)} KB · 建议：${x.action}`).join('\n')}\n\n`;
  }

  let rules = yaml('新增内容规则', ['obsidian','investment','workflow']);
  rules += `# 新增内容规则\n\n你之后还会持续新增内容，所以这个库采用“**旧内容稳定 + 索引可刷新 + 新内容有入口**”的方式管理。\n\n## 新内容放哪里？\n\n### 1. 明确公司/主题\n\n直接放进对应目录：\n\n- 公司研究：\`公司名/报告名.md\`\n- 行业研究：\`行业或主题名/报告名.md\`\n- 资料来源：优先放到对应公司/主题目录下，或后续统一进 \`_sources/\`。\n\n### 2. 暂时不知道怎么归类\n\n先放：\n\n- \`_inbox/YYYY-MM/报告名.md\`\n\n等每周/每批整理时再归档。不要为了“立刻分类正确”卡住写作。\n\n## 新报告建议 frontmatter\n\n复制 [[_templates/投资报告模板|投资报告模板]]，至少保留这些字段：\n\n\`\`\`yaml\ntitle: ""\ndate: 2026-07-08\nworkflow: research\ncompany: ""\nticker: ""\nmarket: ""\nstatus: draft\ndecision: watch\ntags: [investment]\n\`\`\`\n\n## 新增后怎么办？\n\n有两种方式：\n\n1. 你对 Codex 说：**刷新 reports 索引**。\n2. 或者在终端运行：\n\n\`\`\`powershell\ncd "${vault.replaceAll('\\','/')}"\nnode .\\_scripts\\refresh_obsidian_indexes.mjs\n\`\`\`\n\n刷新后这些页面会自动更新：\n\n- [[00-index/投资研究总览|投资研究总览]]\n- [[00-index/最近更新|最近更新]]\n- [[00-index/目录导航|目录导航]]\n- [[00-index/工作流索引|工作流索引]]\n- 各大目录的 \`MOC.md\`\n\n## 我建议的长期规则\n\n- 不追求一次性把旧库整理完。\n- 新内容尽量从今天开始规范。\n- 旧内容靠索引和 MOC 提升可读性。\n- 真要移动旧文件时，每次只移动一小批，并保留索引页中的旧路径记录。\n`;

  const template = `---\ntitle: ""\ndate: 2026-07-08\nworkflow: research\ncompany: ""\nticker: ""\nmarket: ""\nstatus: draft\ndecision: watch\ntags: [investment]\n---\n\n# 标题\n\n## 一句话结论\n\n- \n\n## 为什么现在看\n\n- \n\n## 核心判断\n\n1. \n2. \n3. \n\n## 关键数据\n\n| 指标 | 数值 | 来源 |\n|---|---:|---|\n|  |  |  |\n\n## 反方观点 / 风险\n\n- \n\n## 后续跟踪清单\n\n- [ ] \n`;
  const inboxReadme = `# _inbox\n\n这里是“临时入口”。\n\n当你新增内容但暂时不知道放进哪个公司/主题目录时，先放这里，例如：\n\n- \`_inbox/2026-07/某公司初看.md\`\n- \`_inbox/2026-07/某行业线索.md\`\n\n之后运行刷新脚本，内容会出现在“最近更新”和相关索引里。\n`;

  const outputs = new Map([
    [path.join(indexDir, '投资研究总览.md'), home],
    [path.join(indexDir, '最近更新.md'), recentMd],
    [path.join(indexDir, '目录导航.md'), nav],
    [path.join(indexDir, '工作流索引.md'), workflowMd],
    [path.join(indexDir, '重点公司索引.md'), companyMd],
    [path.join(indexDir, '待复核.md'), reviewMd],
    [path.join(indexDir, '根目录整理建议.md'), rootAdvice],
    [path.join(indexDir, '新增内容规则.md'), rules],
    [path.join(templatesDir, '投资报告模板.md'), template],
    [path.join(inboxDir, 'README.md'), inboxReadme],
  ]);
  for (const [p, content] of outputs) await fs.writeFile(p, content, 'utf8');

  return { vault, files: files.length, markdown: mdInfos.length, mocCount: mocDirs.length, outputs: [...outputs.keys()] };
})().then((result) => { console.log(JSON.stringify(result, null, 2)); }).catch((error) => { console.error(error); process.exit(1); });
