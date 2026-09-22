// ==UserScript==
// @name         X Deep Scanner (following 精评)
// @namespace    x-cleaner
// @version      1.0
// @match        https://x.com/*
// @match        https://twitter.com/*
// @grant        none
// @description  逐个 profile 抓取 粉丝/关注/蓝标/最近发帖，供 x_score.py 精评
// ==/UserScript==
/*
 * x_deepscan.js  ——  深度扫描：抓 profile 级数据（框架1/2/5 的精评支撑）
 * ------------------------------------------------------------------
 * 为什么需要它：following 列表页只给 handle/简介/是否回关，看不到
 *   粉丝数、关注数、蓝标、最近发帖。而这正是评分框架里权重最高的
 *   「被谁关注(声望)」「互关比」「活跃度」的数据来源。
 *
 * 用法（推荐 Tampermonkey，可自动跨页运行）：
 *   1. 安装 Tampermonkey 扩展，新建脚本，把本文件全部内容粘贴保存。
 *      它会在 x.com 下自动运行（也可直接控制台粘贴启动）。
 *   2. 把下方 TARGET_HANDLES 填成要精评的候选 handle（建议 ≤200，别全量）。
 *   3. 打开 x.com 任意页，脚本自动链式跳到每个 profile，抓完跳下一个。
 *   4. 全部完成后自动下载 deepscan.json。把它和 following_audit.json
 *      放同目录，重跑 x_score.py 即得精评（框架1/2/5 维度会被计入）。
 *
 * 风控：每账号间隔 MIN_GAP~MAX_GAP 秒随机；建议单批 ≤200、分多天。
 * 局限：蓝标/最近发帖检测依赖 X 当前 DOM，改版可能失效，失败字段留空。
 */
(function () {
  const TARGET_HANDLES = [
    // 例如 "spam_user_12345_x", "bob_writer", ...
  ];
  const MIN_GAP = 5, MAX_GAP = 10;   // 每账号间隔秒
  const LOAD_WAIT = 20;              // 等页面加载的最大尝试次数
  const NO_NAV = ['home', 'following', 'explore', 'notifications',
                  'messages', 'i', 'search', 'settings', 'compose', 'login'];

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const rand = (a, b) => Math.floor(a + Math.random() * (b - a));
  const KEY_DONE = 'x_deepscan_done';
  const KEY_QUEUE = 'x_deepscan_queue';
  const KEY_DATA = 'x_deepscan_data';

  function getQueue() {
    let q = JSON.parse(sessionStorage.getItem(KEY_QUEUE) || 'null');
    if (!q) {
      q = TARGET_HANDLES.map((h) => h.toLowerCase()).filter(Boolean);
      sessionStorage.setItem(KEY_QUEUE, JSON.stringify(q));
    }
    return q;
  }
  function getDone() {
    return new Set(JSON.parse(sessionStorage.getItem(KEY_DONE) || '[]'));
  }
  function markDone(h) {
    const d = JSON.parse(sessionStorage.getItem(KEY_DONE) || '[]');
    d.push(h);
    sessionStorage.setItem(KEY_DONE, JSON.stringify(d));
  }
  function pushData(rec) {
    const all = JSON.parse(sessionStorage.getItem(KEY_DATA) || '[]');
    all.push(rec);
    sessionStorage.setItem(KEY_DATA, JSON.stringify(all));
  }

  function isProfile() {
    const m = location.pathname.match(/^\/([A-Za-z0-9_]{1,15})$/);
    if (!m) return null;
    if (NO_NAV.includes(m[1].toLowerCase())) return null;
    return m[1].toLowerCase();
  }

  function scrape() {
    const txt = document.body.innerText || '';
    let followers = null, following = null;
    const fm = txt.match(/([\d.,]+\s?[kKmM]?)\s*Followers/i);
    const gm = txt.match(/([\d.,]+\s?[kKmM]?)\s*Following/i);
    if (fm) followers = fm[1].replace(/\s/g, '');
    if (gm) following = gm[1].replace(/\s/g, '');
    // 蓝标：认证 svg / 含 "Verified account" 的 aria-label
    const verified =
      !!document.querySelector('svg[aria-label="Verified account"], svg[aria-label="Verified"], a[href$="/verified"]');
    // 最近发帖时间
    // 发帖总数（供"过度活跃霸屏"维度使用）
    const tm = txt.match(/([\d.,]+\s?[kKmM]?)\s*(Posts|Tweets)/i);
    const tweets = tm ? tm[1].replace(/\s/g, '') : null;
    const t = document.querySelector('article time, main time, time');
    const last_post = t ? (t.getAttribute('datetime') || '') : '';
    return { followers, following, tweets, verified, last_post };
  }

  async function run() {
    const queue = getQueue();
    const done = getDone();
    const remaining = queue.filter((h) => !done.has(h));
    if (remaining.length === 0) { exportAll(); return; }

    const handle = isProfile();
    if (handle) {
      let tries = 0, data = null;
      while (tries < LOAD_WAIT) {
        const d = scrape();
        if (d.followers || d.following || d.last_post) { data = d; break; }
        await sleep(800); tries++;
      }
      if (data) {
        pushData({ handle, ...data });
        markDone(handle);
        console.log(`✅ ${handle}: followers=${data.followers} following=${data.following} verified=${data.verified} last=${data.last_post}`);
      } else {
        console.log(`⚠️ ${handle} 加载超时，跳过`);
        markDone(handle);
      }
    }

    const nowDone = getDone();
    const next = queue.find((h) => !nowDone.has(h));
    if (next) {
      console.log(`➡️ 跳转 ${next}（剩 ${queue.length - nowDone.size} 个）...`);
      await sleep(rand(MIN_GAP * 1000, MAX_GAP * 1000));
      location.href = 'https://x.com/' + next;
    } else {
      exportAll();
    }
  }

  function exportAll() {
    const all = JSON.parse(sessionStorage.getItem(KEY_DATA) || '[]');
    const blob = new Blob([JSON.stringify(all, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'deepscan.json'; a.click();
    console.log(`🎉 完成，导出 deepscan.json（${all.length} 个）。如需重跑：sessionStorage.clear()`);
  }

  const h = isProfile();
  if (!h) {
    const q = getQueue();
    const d = getDone();
    const first = q.find((x) => !d.has(x));
    if (first) { console.log('启动 deepscan，跳转第一个...'); location.href = 'https://x.com/' + first; return; }
    exportAll(); return;
  }
  run();
})();
