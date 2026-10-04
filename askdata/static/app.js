const $ = (id) => document.getElementById(id);
const ROUTE_NAME = { db: '结构化问数', kb: '知识问答', hybrid: '跨源融合' };

function setStatus(text, isError) {
  const el = $('status');
  el.textContent = text;
  el.className = 'status' + (isError ? ' err' : '');
}

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function ask() {
  const question = $('q').value.trim();
  if (!question) return;
  const btn = $('go');
  btn.disabled = true;
  $('result').classList.add('hidden');
  setStatus('正在规划任务并执行查询…', false);

  let data;
  try {
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    data = await resp.json();
    if (!resp.ok) throw new Error(data.error || ('HTTP ' + resp.status));
  } catch (err) {
    setStatus('请求失败：' + err.message, true);
    btn.disabled = false;
    return;
  }

  $('status').className = 'status hidden';
  render(data);
  btn.disabled = false;
}

function render(data) {
  $('result').classList.remove('hidden');
  $('route-badge').textContent = ROUTE_NAME[data.route] || data.route;
  $('time-badge').textContent = data.elapsed + 's';
  $('answer').innerHTML = esc(data.answer || data.error || '（无答案）')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  const clarify = $('clarify');
  if (data.missing) {
    clarify.classList.remove('hidden');
    clarify.textContent = '该问题可能缺少关键信息：' + data.missing + '　请补充后重新提问，系统不会在信息不足时给出猜测结果。';
  } else {
    clarify.classList.add('hidden');
  }

  $('steps').innerHTML = (data.steps || [])
    .map(s => `<li>${esc(s.name)}<span>${esc(s.detail)}</span></li>`).join('');

  const sqlBox = $('sql-box');
  const srcBox = $('src-box');
  let hasEvidence = false;

  if (data.sql && data.sql.text) {
    hasEvidence = true;
    sqlBox.classList.remove('hidden');
    $('sql').textContent = data.sql.text;
    $('sql-stat').textContent = data.sql.ok
      ? `${data.sql.rows.length} 行 · ${data.sql.attempts} 次尝试`
      : '执行失败';
    $('sql-stat').className = data.sql.ok ? 'ok-text' : 'err-text';
    const rows = data.sql.rows || [];
    if (rows.length && data.sql.columns.length) {
      const head = data.sql.columns.map(c => `<th>${esc(c)}</th>`).join('');
      const body = rows.slice(0, 12)
        .map(r => '<tr>' + r.map(v => `<td>${esc(v)}</td>`).join('') + '</tr>').join('');
      $('rows').innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    } else {
      $('rows').innerHTML = '';
    }
  } else {
    sqlBox.classList.add('hidden');
  }

  if (data.sources && data.sources.length) {
    hasEvidence = true;
    srcBox.classList.remove('hidden');
    $('src-count').textContent = data.sources.length + ' 个片段';
    $('sources').innerHTML = data.sources.map(s => `
      <div class="src-item">
        <div class="src-head"><span>${esc(s.title)}</span><span>相关度 ${s.score}</span></div>
        <div class="snip">${esc(s.snippet)}…</div>
        <div class="hits">识别关键词：${esc((s.hits || []).join('、'))}　·　来源：${esc(s.doc)} 第 ${s.chunk} 段</div>
      </div>`).join('');
  } else {
    srcBox.classList.add('hidden');
  }

  $('no-evidence').classList.toggle('hidden', hasEvidence);
}

$('go').addEventListener('click', ask);
$('q').addEventListener('keydown', e => { if (e.key === 'Enter') ask(); });
document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => {
  $('q').value = c.dataset.q;
  ask();
}));
