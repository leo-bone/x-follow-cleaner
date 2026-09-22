/*
 * x_unfollow.js  ——  X（推特）安全取关脚本（带白名单 / 随机延迟 / 每日上限 / 预览）
 * ------------------------------------------------------------------
 * 用途：在「关注」页面，只删除你明确指定的名单里的账号，且绝不动白名单。
 *
 * 安全原则（避免被 X 判定为机器人）：
 *   - 每次操作之间随机延迟 15~40 秒（不要改成匀速秒级）。
 *   - 每批上限设 50，每天不超过 50~100，分多天做。
 *   - 先 DRY_RUN=true 预览，确认名单无误，再设 false 真正执行。
 *
 * 用法：
 *   1. 打开 https://x.com/<你的用户名>/following
 *   2. 把下面 TARGET_HANDLES / WHITELIST 填好
 *   3. F12 打开控制台，先设 DRY_RUN = true 跑一遍看预览
 *   4. 确认无误后改 DRY_RUN = false 再跑
 *
 * ⚠️ 取关不可自动撤销，删错只能手动重新关注。务必先预览、先小批量。
 */
(() => {
  // ===================== 配置区 =====================
  const DRY_RUN = true;            // true=只预览不删；false=真正取关
  const TARGET_HANDLES = [         // 要取关的 handle 列表（小写，从评分报告复制）
    // "example1",
    // "example2",
  ];
  const WHITELIST = [              // 绝不取关的 handle（小写），留空则无保护
    // "important_friend",
  ];
  const MAX_PER_RUN = 50;          // 每批最多删多少（建议 <=50）
  const MIN_DELAY = 15;            // 每次之间最小延迟（秒）
  const MAX_DELAY = 40;            // 每次之间最大延迟（秒）
  const SCROLL_PAUSE = 1200;       // 滚动后等待（毫秒）
  // ==================================================

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const rand = (a, b) => Math.floor(a + Math.random() * (b - a));
  const targetSet = new Set(TARGET_HANDLES.map((h) => h.toLowerCase()));
  const whiteSet = new Set(WHITELIST.map((h) => h.toLowerCase()));
  let done = 0;
  let skipped = 0;
  let missed = 0;

  function handleOf(btn) {
    const m = (btn.getAttribute('aria-label') || '').match(/@([A-Za-z0-9_]{1,15})/);
    if (m) return m[1].toLowerCase();
    return null;
  }

  async function handleOne(btn) {
    const handle = handleOf(btn);
    if (!handle) {
      missed++;
      return;
    }
    if (whiteSet.has(handle)) {
      skipped++;
      console.log(`⛔ 白名单跳过 @${handle}`);
      return;
    }
    if (!targetSet.has(handle)) {
      skipped++;
      return;
    }
    if (DRY_RUN) {
      done++;
      console.log(`🔍 [预览] 将取关 @${handle}`);
      return;
    }
    btn.click();
    await sleep(rand(600, 1200));
    const confirm = document.querySelector('[data-testid="confirmationSheetConfirm"]');
    if (confirm) confirm.click();
    done++;
    console.log(`✅ 已取关 @${handle}（${done}/${MAX_PER_RUN}）`);
    await sleep(rand(MIN_DELAY * 1000, MAX_DELAY * 1000));
  }

  async function run() {
    let noNew = 0;
    let rounds = 0;
    const handled = new Set();
    while (done < MAX_PER_RUN && rounds < 3000 && noNew < 5) {
      const btns = Array.from(document.querySelectorAll('[data-testid$="-unfollow"]')).filter(
        (b) => !handled.has(b)
      );
      let acted = 0;
      for (const b of btns) {
        if (done >= MAX_PER_RUN) break;
        handled.add(b);
        const h = handleOf(b);
        if (h && (targetSet.has(h) || whiteSet.has(h))) {
          await handleOne(b);
          acted++;
        }
      }
      window.scrollTo(0, document.body.scrollHeight);
      await sleep(SCROLL_PAUSE);
      if (acted === 0) noNew++;
      else noNew = 0;
      rounds++;
    }
    console.log(`\n=== 完成 ===`);
    console.log(`模式 DRY_RUN=${DRY_RUN}`);
    console.log(`命中处理：${done}，跳过(非目标/白名单)：${skipped}，未识别：${missed}`);
    if (done >= MAX_PER_RUN)
      console.log(`达到本批上限 ${MAX_PER_RUN}。如需继续，隔几小时再跑一次（建议每天 <=100）。`);
  }

  console.log(`🚀 取关脚本启动（DRY_RUN=${DRY_RUN}，目标 ${targetSet.size} 个，白名单 ${whiteSet.size} 个）`);
  run();
})();
