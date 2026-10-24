/* Nano Dify Knowledge Lib 管理界面 */
const $ = (sel) => document.querySelector(sel);
const api = {
  async req(method, url, body, isForm = false) {
    const opt = { method };
    if (body && isForm) opt.body = body;
    else if (body) { opt.headers = { "Content-Type": "application/json" }; opt.body = JSON.stringify(body); }
    const res = await fetch(url, opt);
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `请求失败 ${res.status}`);
    return data;
  },
  get: (u) => api.req("GET", u),
  post: (u, b, f) => api.req("POST", u, b, f),
  patch: (u, b) => api.req("PATCH", u, b),
  del: (u) => api.req("DELETE", u),
};

let currentDataset = null;
let currentDocForSegments = null;

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  setTimeout(() => t.classList.add("hidden"), 2400);
}

function fmtSize(n) {
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / 1024 / 1024).toFixed(1) + " MB";
}
function fmtTime(s) { return s ? new Date(s).toLocaleString("zh-CN") : "-"; }
const STATUS_TEXT = { queuing: "排队中", indexing: "索引中", completed: "已完成", error: "失败" };

/* ---------- 知识库列表 ---------- */
async function loadDatasets(selectId = null) {
  const { data } = await api.get("/api/datasets");
  const list = $("#datasetList");
  list.innerHTML = "";
  for (const ds of data) {
    const el = document.createElement("div");
    el.className = "dataset-item" + (currentDataset?.id === ds.id ? " active" : "");
    el.innerHTML = `<div class="name">${esc(ds.name)}</div>
      <div class="meta">${ds.document_count} 文档 · ${ds.segment_count} 分段</div>`;
    el.onclick = () => selectDataset(ds.id);
    list.appendChild(el);
  }
  if (selectId) selectDataset(selectId);
}

async function selectDataset(id) {
  currentDataset = await api.get(`/api/datasets/${id}`);
  $("#emptyState").classList.add("hidden");
  $("#datasetView").classList.remove("hidden");
  $("#dsName").textContent = currentDataset.name;
  $("#dsDesc").textContent = currentDataset.description || "无描述";
  $("#setName").value = currentDataset.name;
  $("#setDesc").value = currentDataset.description || "";
  $("#setChunkSize").value = currentDataset.chunk_size;
  $("#setChunkOverlap").value = currentDataset.chunk_overlap;
  await loadDatasets();
  await loadDocuments();
}

/* ---------- 文档 ---------- */
async function loadDocuments() {
  if (!currentDataset) return;
  const { data } = await api.get(`/api/datasets/${currentDataset.id}/documents`);
  $("#docStats").textContent = `共 ${data.length} 个文档`;
  const tbody = $("#docTableBody");
  tbody.innerHTML = "";
  for (const doc of data) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${esc(doc.name)}</td>
      <td>${fmtSize(doc.size)}</td>
      <td>${doc.chunk_count}</td>
      <td><span class="status ${doc.status}" title="${esc(doc.error || "")}">${STATUS_TEXT[doc.status] || doc.status}</span></td>
      <td class="muted">${fmtTime(doc.created_at)}</td>
      <td></td>`;
    const ops = document.createElement("td");
    const btnView = mkBtn("查看", () => openDocContent(doc));
    const btnSeg = mkBtn("分段", () => openSegments(doc));
    const btnRe = mkBtn("重新索引", async () => { await api.post(`/api/datasets/${currentDataset.id}/documents/${doc.id}/reindex`); toast("已重新索引"); loadDocuments(); });
    const btnDel = mkBtn("删除", async () => {
      if (!confirm(`删除文档「${doc.name}」及其全部分段？`)) return;
      await api.del(`/api/datasets/${currentDataset.id}/documents/${doc.id}`);
      toast("已删除"); loadDocuments(); loadDatasets();
    });
    [btnView, btnSeg, btnRe, btnDel].forEach((b) => { b.classList.add("btn-sm"); ops.appendChild(b); });
    tr.appendChild(ops);
    tbody.appendChild(tr);
  }
}

function mkBtn(text, onclick) {
  const b = document.createElement("button");
  b.className = "btn"; b.textContent = text; b.onclick = onclick;
  return b;
}

/* ---------- 文档原文查看 ---------- */
async function openDocContent(doc) {
  $("#docContentTitle").textContent = `文档原文 · ${doc.name}`;
  $("#docContentMeta").textContent = `${fmtSize(doc.size)} · ${doc.chunk_count} 个分段 · 上传于 ${fmtTime(doc.created_at)}`;
  $("#docDownloadLink").href = `/api/datasets/${currentDataset.id}/documents/${doc.id}/download`;
  $("#docContentBody").textContent = "加载中…";
  $("#docContentModal").classList.remove("hidden");
  try {
    const data = await api.get(`/api/datasets/${currentDataset.id}/documents/${doc.id}/content`);
    $("#docContentBody").textContent = data.content || "（空文档）";
  } catch (err) {
    $("#docContentBody").textContent = `加载失败：${err.message}`;
  }
}

/* ---------- 分段管理 ---------- */
async function openSegments(doc) {
  currentDocForSegments = doc;
  $("#segModalTitle").textContent = `分段管理 · ${doc.name}`;
  $("#segmentModal").classList.remove("hidden");
  await loadSegments();
}

async function loadSegments() {
  const { data } = await api.get(`/api/datasets/${currentDataset.id}/documents/${currentDocForSegments.id}/segments`);
  const list = $("#segmentList");
  list.innerHTML = "";
  for (const seg of data) {
    list.appendChild(segmentCard(seg));
  }
}

function segmentCard(seg) {
  const card = document.createElement("div");
  card.className = "segment-card" + (seg.enabled ? "" : " disabled");
  const head = document.createElement("div");
  head.className = "seg-head";
  head.innerHTML = `<span class="muted">#${seg.position + 1} · ${seg.content.length} 字符 · 命中 ${seg.hit_count} 次</span>`;
  const actions = document.createElement("div");
  actions.className = "seg-actions";

  const sw = document.createElement("label");
  sw.className = "switch";
  sw.innerHTML = `<input type="checkbox" ${seg.enabled ? "checked" : ""} /><span class="slider"></span>`;
  sw.querySelector("input").onchange = async (e) => {
    await api.patch(`/api/datasets/${currentDataset.id}/documents/${currentDocForSegments.id}/segments/${seg.id}`, { enabled: e.target.checked });
    card.classList.toggle("disabled", !e.target.checked);
  };

  const btnSave = mkBtn("保存", async () => {
    const content = ta.value.trim();
    if (!content) return toast("内容不能为空");
    await api.patch(`/api/datasets/${currentDataset.id}/documents/${currentDocForSegments.id}/segments/${seg.id}`, { content });
    toast("已保存并重新向量化");
  });
  btnSave.classList.add("btn-sm");

  const btnDel = mkBtn("删除", async () => {
    await api.del(`/api/datasets/${currentDataset.id}/documents/${currentDocForSegments.id}/segments/${seg.id}`);
    card.remove(); toast("已删除");
  });
  btnDel.classList.add("btn-sm", "btn-danger");

  actions.append(sw, btnSave, btnDel);
  head.appendChild(actions);
  const ta = document.createElement("textarea");
  ta.value = seg.content;
  card.append(head, ta);
  return card;
}

/* ---------- 召回测试 ---------- */
async function runHitTest() {
  const query = $("#hitQuery").value.trim();
  if (!query) return toast("请输入测试问题");
  const body = {
    query,
    top_k: parseInt($("#hitTopK").value || "4"),
    score_threshold: parseFloat($("#hitThreshold").value || "0"),
    rerank: $("#hitRerank").checked,
  };
  const resp = await api.post(`/api/datasets/${currentDataset.id}/hit-testing`, body);
  const records = resp.records;
  const box = $("#hitResults");
  box.innerHTML = "";
  if (resp.rerank) {
    const tag = document.createElement("p");
    tag.className = "muted";
    tag.textContent = `Rerank 提供方：${resp.rerank_provider}（粗排 ${Math.min(records.length, body.top_k * 3)}+ 候选 → 精排 Top${body.top_k}）`;
    box.appendChild(tag);
  }
  if (!records.length) box.innerHTML += `<p class="muted">无命中结果</p>`;
  for (const r of records) {
    const el = document.createElement("div");
    el.className = "hit-card";
    const vscore = r.vector_score != null ? `<span class="vscore">向量分 ${r.vector_score.toFixed(4)}</span>` : "";
    el.innerHTML = `<div class="hit-head">
        <span class="muted">${esc(r.document_name)} · 分段 #${r.position + 1}</span>
        <span><span class="score">${r.score.toFixed(4)}</span>${vscore}</span>
      </div><div class="content">${esc(r.content)}</div>`;
    box.appendChild(el);
  }
}

/* ---------- 事件绑定 ---------- */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    for (const p of ["docs", "hit", "settings"]) {
      $(`#panel-${p}`).classList.toggle("hidden", p !== tab.dataset.tab);
    }
  };
});

$("#btnNewDataset").onclick = () => $("#datasetModal").classList.remove("hidden");
$("#btnCloseDsModal").onclick = () => $("#datasetModal").classList.add("hidden");
$("#btnCreateDataset").onclick = async () => {
  const name = $("#newDsName").value.trim();
  if (!name) return toast("请填写名称");
  const ds = await api.post("/api/datasets", {
    name,
    description: $("#newDsDesc").value.trim(),
    chunk_size: parseInt($("#newDsChunkSize").value || "500"),
    chunk_overlap: parseInt($("#newDsChunkOverlap").value || "50"),
  });
  $("#datasetModal").classList.add("hidden");
  toast("已创建");
  await loadDatasets(ds.id);
};

$("#btnUpload").onclick = () => $("#fileInput").click();
$("#fileInput").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file || !currentDataset) return;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const doc = await api.post(`/api/datasets/${currentDataset.id}/documents/upload`, fd, true);
    toast(doc.status === "completed" ? `已索引 ${doc.chunk_count} 个分段` : `索引失败: ${doc.error}`);
  } catch (err) { toast(err.message); }
  e.target.value = "";
  loadDocuments(); loadDatasets();
};

$("#btnHitTest").onclick = runHitTest;
$("#hitQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") runHitTest(); });

$("#btnCloseSegModal").onclick = () => $("#segmentModal").classList.add("hidden");
$("#btnCloseDocModal").onclick = () => $("#docContentModal").classList.add("hidden");
$("#btnAddSegment").onclick = async () => {
  const content = prompt("输入新分段内容：");
  if (!content?.trim()) return;
  await api.post(`/api/datasets/${currentDataset.id}/documents/${currentDocForSegments.id}/segments`, { content: content.trim() });
  await loadSegments(); loadDocuments();
  toast("已新增并向量化");
};

$("#btnSaveSettings").onclick = async () => {
  await api.patch(`/api/datasets/${currentDataset.id}`, {
    name: $("#setName").value.trim() || currentDataset.name,
    description: $("#setDesc").value.trim(),
    chunk_size: parseInt($("#setChunkSize").value || "500"),
    chunk_overlap: parseInt($("#setChunkOverlap").value || "50"),
  });
  toast("已保存");
  await selectDataset(currentDataset.id);
};

$("#btnDeleteDataset").onclick = async () => {
  if (!confirm(`删除知识库「${currentDataset.name}」？将同时删除所有文档与分段，不可恢复。`)) return;
  await api.del(`/api/datasets/${currentDataset.id}`);
  currentDataset = null;
  $("#datasetView").classList.add("hidden");
  $("#emptyState").classList.remove("hidden");
  toast("已删除");
  loadDatasets();
};

loadDatasets();

/* 侧边栏底部展示当前 Embedding / Rerank 提供方 */
api.get("/api/health").then((h) => {
  $("#providerInfo").innerHTML =
    `Embedding：${esc(h.embedding_provider)}<br>Rerank：${esc(h.rerank_provider)}`;
});
