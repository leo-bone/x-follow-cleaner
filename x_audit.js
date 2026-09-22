/*
 * x_audit.js  ——  X（推特）关注列表审计脚本（只读，不取关任何人）
 * ------------------------------------------------------------------
 * 用途：在「关注」页面滚动加载你的全部关注，提取
 *        handle / 显示名 / 是否回关 / 简介，导出为 following_audit.json
 *
 * 用法：
 *   1. 用浏览器打开 https://x.com/<你的用户名>/following
 *   2. 按 F12（Mac 是 Cmd+Option+J）打开「控制台(Console)」
 *   3. 把本文件全部内容粘贴进去，回车运行
 *   4. 脚本会自动滚动并抓取，完成后自动下载 following_audit.json
 *
 * 注意：
 *   - 纯读取，不会取消关注任何人，可放心运行。
 *   - 3000+ 关注会滚动几分钟，期间不要切走标签页。
 *   - X 改版可能导致选择器失效；若抓不到数据，看控制台报错，多半是
 *     [data-testid$="-unfollow"] 或 userFollowIndicator 变了，需微调。
 *   - 导出的 JSON 是你的个人隐私数据，请本地妥善保管，不要外传。
 *   - 进阶：若需粉丝数/关注数/蓝标等深度数据（用于更准地判断账号价值），
 *     见 x_deepscan.js（Tampermonkey 用户脚本，逐个 profile 抓取后由 x_score.py 合并）。
 */
(() => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const seen = new Map(); // handle -> record

  function extractOnce() {
    const articles = Array.from(document.querySelectorAll('article'));
    let added = 0;
    for (const art of articles) {
      const btn = art.querySelector('[data-testid$="-unfollow"]');
      if (!btn) continue;

      // 提取 handle：优先从按钮 aria-label 的 @xxx，其次从 profile 链接
      let handle = null;
      const m = (btn.getAttribute('aria-label') || '').match(/@([A-Za-z0-9_]{1,15})/);
      if (m) handle = m[1].toLowerCase();
      if (!handle) {
        const link = art.querySelector('a[href^="/"]');
        if (link) {
          const parts = link.getAttribute('href').split('?')[0].split('/').filter(Boolean);
          const cand = (parts[parts.length - 1] || '').replace(/^@/, '');
          if (/^[A-Za-z0-9_]{1,15}$/.test(cand)) handle = cand.toLowerCase();
        }
      }
      if (!handle || seen.has(handle)) continue;

      const followsYou = !!art.querySelector('[data-testid="userFollowIndicator"]');

      // 显示名：profile 链接文本里 "@" 之前的部分
      let name = '';
      const link = art.querySelector('a[href^="/"]');
      if (link) {
        const txt = (link.getAttribute('aria-label') || link.textContent || '').trim();
        const mm = txt.match(/^(.*?)\s*@/);
        name = mm ? mm[1].trim() : txt;
      }

      // 简介：following 列表通常不含 bio；尽力抓取较长的一段文本
      let bio = '';
      const spans = art.querySelectorAll('span');
      for (const s of spans) {
        const t = s.textContent.trim();
        if (t && t !== name && t !== '@' + handle && !/follow/i.test(t) && t.length > 8) {
          bio = t;
          break;
        }
      }

      seen.set(handle, { handle, name, follows_you: followsYou, bio });
      added++;
    }
    return added;
  }

  async function run() {
    let noNew = 0;
    let rounds = 0;
    const MAX_ROUNDS = 2000;
    while (noNew < 4 && rounds < MAX_ROUNDS) {
      const added = extractOnce();
      window.scrollTo(0, document.body.scrollHeight);
      await sleep(900);
      if (added === 0) noNew++;
      else noNew = 0;
      rounds++;
      if (rounds % 20 === 0) console.log(`已扫描，当前累计 ${seen.size} 个关注...`);
    }

    const data = Array.from(seen.values());
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'following_audit.json';
    a.click();

    const back = data.filter((d) => !d.follows_you).length;
    console.log(`\n✅ 审计完成：共 ${data.length} 个关注，已下载 following_audit.json`);
    console.log(`   其中未回关你的：${back} 个（占比 ${(back / data.length * 100).toFixed(1)}%）`);
    console.log(`   把 following_audit.json 给工具（x_score.py）跑评分即可。`);
    window.__auditData = data; // 控制台里可直接访问
  }

  console.log('🔍 开始审计，自动滚动中（不要切走标签页）...');
  run();
})();
