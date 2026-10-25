// 网页版算法自检：从 index.html 中提取内联 JS，在 Node 中运行纯函数部分。
// 校验：Dijkstra 与 A* 结果一致；BFS 站数 <= Dijkstra 站数；连通性正常。
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('未找到内联 script'); process.exit(1); }

const api = new Function(m[1] + '\n;return {buildGraph, dijkstra, bfs, astar, euclidean, MinHeap, DATASETS};')();

function assert(cond, msg) {
  if (!cond) { console.error('FAIL: ' + msg); process.exit(1); }
  console.log('  ok - ' + msg);
}

let failures = 0;
function check(name, g, a, b) {
  const d = api.dijkstra(g, a, b);
  const s = api.astar(g, a, b);
  const f = api.bfs(g, a, b);
  assert(d.ok && s.ok && f.ok, `${name} ${a}->${b} 均可达`);
  assert(Math.abs(d.totalWeight - s.totalWeight) < 1e-6,
    `${name} Dijkstra(${d.totalWeight.toFixed(2)}) === A*(${s.totalWeight.toFixed(2)})`);
  assert(f.path.length <= d.path.length,
    `${name} BFS 站数(${f.path.length}) <= Dijkstra 站数(${d.path.length})`);
  assert(d.path[0] === a && d.path[d.path.length - 1] === b, `${name} 路径端点正确`);
}

for (const key of ['zhengzhou', 'beijing', 'sample']) {
  const data = api.DATASETS[key];
  const g = api.buildGraph(data);
  const ids = Object.keys(g.stations);
  console.log(`\n[${key}] ${data.name} — ${ids.length} 站`);
  assert(ids.length > 0, '站点已加载');

  // 随机抽样若干对起终点（用固定种子保证可复现）
  let seed = 42;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const pairs = new Set();
  for (let i = 0; i < 30; i++) {
    const a = ids[Math.floor(rnd() * ids.length)];
    const b = ids[Math.floor(rnd() * ids.length)];
    if (a !== b) pairs.add(a + '|' + b);
  }
  let n = 0;
  for (const p of pairs) { const [a, b] = p.split('|'); check(key, g, a, b); n++; }
  console.log(`  共校验 ${n} 组起终点`);
}

console.log('\n全部通过 ✅');
