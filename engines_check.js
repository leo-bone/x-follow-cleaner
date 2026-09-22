#!/usr/bin/env node
/*
 * engines_check.js  ——  从 x_smart_unfollow.js 抽出评分引擎，跑 testcases.json
 * ------------------------------------------------------------------
 * 为什么需要：Python（x_score.py）和浏览器（x_smart_unfollow.js）各有一份引擎，
 * 二者必须行为完全一致，否则「按报告决策」和「浏览器实时判定」会自相矛盾。
 * 本脚本用正则从单文件浏览器脚本里切出引擎代码并在 Node 中执行，
 * 把每个用例的分数以 JSON 输出到 stdout，供 verify_sync.py 比对。
 *
 * 用法：node engines_check.js
 */
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, 'x_smart_unfollow.js'), 'utf8');
const start = src.indexOf('const WEIGHTS = {');
const endMark = 'return { score: s, reasons };';
const end = src.indexOf(endMark);
if (start < 0 || end < 0) {
  console.error('无法从 x_smart_unfollow.js 中定位引擎代码段');
  process.exit(1);
}
const code = src.slice(start, src.indexOf('  }', end) + 3);

// 浏览器环境 stub + 范围外依赖
const pre = `
const localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
const WHITELIST = [];
let EXTRA_DATA = {};
`;

let calcScore;
try {
  const factory = new Function(pre + code + '\nreturn { calcScore };');
  calcScore = factory().calcScore;
} catch (e) {
  console.error('引擎抽取执行失败：', e.message);
  process.exit(1);
}

const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'testcases.json'), 'utf8')).cases;
const out = {};
for (const c of cases) {
  const r = calcScore(c);
  out[c.handle] = r.score;
}
console.log(JSON.stringify(out));
