const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const elements = {
  sidebar: $(".sidebar"),
  overlay: $("#overlay"),
  pageTitle: $("#page-title"),
  pageKicker: $("#page-kicker"),
  messages: $("#messages"),
  chatForm: $("#chat-form"),
  messageInput: $("#message"),
  sendButton: $("#send-button"),
  threadInput: $("#thread-id"),
  approval: $("#approval"),
  approvalDetail: $("#approval-detail"),
  runStatus: $("#run-status"),
  trips: $("#trips"),
  recentTrips: $("#recent-trips"),
  createDialog: $("#create-trip-dialog"),
  createForm: $("#create-trip-form"),
  drawer: $("#trip-drawer"),
  drawerContent: $("#drawer-content"),
  toastRegion: $("#toast-region"),
  authDialog: $("#auth-dialog"),
  authForm: $("#auth-form"),
  authButton: $("#auth-button"),
  knowledgeForm: $("#knowledge-upload-form"),
  knowledgeDocuments: $("#knowledge-documents"),
  knowledgeSearchForm: $("#knowledge-search-form"),
  knowledgeResults: $("#knowledge-search-results"),
};

const pageMeta = {
  dashboard: ["旅行控制台", greeting()],
  assistant: ["AI TRAVEL CONCIERGE", "和 TravelMind 一起规划"],
  trips: ["JOURNEY COLLECTION", "我的全部行程"],
  knowledge: ["TRAVEL KNOWLEDGE", "我的旅行知识库"],
};

const state = {
  view: "dashboard",
  trips: [],
  currentTrip: null,
  items: [],
  pendingApprovals: [],
  chatBusy: false,
  threadId: localStorage.getItem("travelmind.thread") || createThreadId(),
  history: [],
  token: localStorage.getItem("travelmind.token") || "",
  user: null,
  eventAbort: null,
  knowledge: [],
};

function greeting() {
  const hour = new Date().getHours();
  return `${hour < 11 ? "早上好" : hour < 14 ? "中午好" : hour < 18 ? "下午好" : "晚上好"}，准备好出发了吗？`;
}

function createThreadId() {
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = String(text);
  return item;
}

function formatDate(value, withTime = false) {
  if (!value) return "待确定";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "待确定";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "待确定";
  return `¥${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
}

function statusText(status) {
  return ({ draft: "规划中", archived: "已归档", active: "进行中", completed: "已完成" })[status] || status || "未知";
}

async function request(path, options = {}) {
  let response;
  try {
    const headers = { ...authHeaders(), ...(options.headers || {}) };
    if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
    response = await fetch(path, {
      ...options,
      headers,
    });
  } catch {
    throw new Error("无法连接 TravelMind 服务，请确认后端已经启动");
  }
  const raw = await response.text();
  let data = null;
  if (raw) {
    try { data = JSON.parse(raw); } catch { data = raw; }
  }
  if (!response.ok) {
    const detail = data && typeof data === "object" ? data.detail : data;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || "参数不正确").join("；")
      : detail || `请求失败（HTTP ${response.status}）`;
    throw new Error(String(message));
  }
  return data;
}

function authHeaders() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

async function loadAuth() {
  try {
    state.user = await request("/auth/me");
    elements.authButton.textContent = state.user.authenticated ? `${state.user.username} · 退出` : "登录";
  } catch {
    state.token = "";
    state.user = null;
    localStorage.removeItem("travelmind.token");
    elements.authButton.textContent = "登录";
  }
}

function openAuthDialog() {
  elements.authForm.reset();
  elements.authDialog.showModal();
  setTimeout(() => elements.authForm.elements.username.focus(), 50);
}

async function authenticate(mode) {
  const data = new FormData(elements.authForm);
  const button = mode === "register" ? $("#register-button") : $("#login-button");
  setButtonBusy(button, true, mode === "register" ? "注册中…" : "登录中…");
  try {
    const result = await request(`/auth/${mode}`, {
      method: "POST",
      body: JSON.stringify({ username: data.get("username"), password: data.get("password") }),
    });
    state.token = result.access_token;
    localStorage.setItem("travelmind.token", state.token);
    elements.authDialog.close();
    await loadAuth();
    changeThread(createThreadId());
    await loadTrips();
    toast(mode === "register" ? "注册成功" : "登录成功", result.username);
  } catch (error) {
    toast(mode === "register" ? "注册失败" : "登录失败", error.message, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

function toggleAuth() {
  if (!state.user?.authenticated) return openAuthDialog();
  state.token = "";
  state.user = null;
  localStorage.removeItem("travelmind.token");
  elements.authButton.textContent = "登录";
  changeThread(createThreadId());
  loadTrips();
  toast("已经退出登录");
}

function toast(title, message = "", type = "success") {
  const item = node("div", `toast${type === "error" ? " is-error" : ""}`);
  item.append(node("i", "", type === "error" ? "!" : "✓"));
  const copy = node("div");
  copy.append(node("strong", "", title));
  if (message) copy.append(node("span", "", message));
  item.append(copy);
  elements.toastRegion.append(item);
  setTimeout(() => item.remove(), 4200);
}

function setButtonBusy(button, busy, busyText = "处理中…") {
  if (!button) return;
  if (busy) {
    button.dataset.label = button.textContent;
    button.disabled = true;
    button.textContent = busyText;
  } else {
    button.disabled = false;
    if (button.dataset.label) button.textContent = button.dataset.label;
  }
}

function navigate(view, updateHash = true) {
  if (!pageMeta[view]) view = "dashboard";
  state.view = view;
  $$(".view").forEach((item) => {
    const active = item.id === `view-${view}`;
    item.hidden = !active;
    item.classList.toggle("is-active", active);
  });
  $$('[data-nav]').forEach((item) => {
    const active = item.dataset.nav === view;
    item.classList.toggle("is-active", active);
    if (item.classList.contains("nav-item")) {
      active ? item.setAttribute("aria-current", "page") : item.removeAttribute("aria-current");
    }
  });
  elements.pageKicker.textContent = pageMeta[view][0];
  elements.pageTitle.textContent = pageMeta[view][1];
  if (updateHash) history.replaceState(null, "", `#${view}`);
  closeMobileMenu();
  if (view === "trips") renderTrips();
  if (view === "knowledge") loadKnowledge();
  if (view === "assistant") setTimeout(() => elements.messageInput.focus(), 100);
}

function openMobileMenu() {
  elements.sidebar.classList.add("is-open");
  elements.overlay.hidden = false;
  $("#menu-button").setAttribute("aria-expanded", "true");
}

function closeMobileMenu() {
  elements.sidebar.classList.remove("is-open");
  if (!elements.drawer.classList.contains("is-open")) elements.overlay.hidden = true;
  $("#menu-button").setAttribute("aria-expanded", "false");
}

async function loadHealth() {
  const dot = $("#service-dot");
  const label = $("#service-label");
  try {
    await request("/health");
    dot.className = "status-dot";
    label.textContent = "服务运行正常";
    $("#capability-status").textContent = "已连接";
  } catch {
    dot.className = "status-dot is-error";
    label.textContent = "服务连接失败";
    $("#capability-status").className = "pill pill-warning";
    $("#capability-status").textContent = "离线";
  }
}

async function loadTrips({ quiet = false } = {}) {
  if (!quiet) elements.trips.replaceChildren(createSkeleton(), createSkeleton(), createSkeleton());
  try {
    state.trips = await request("/trips");
    renderStats();
    renderRecentTrips();
    renderTrips();
  } catch (error) {
    state.trips = [];
    renderStats(true);
    renderRecentError(error.message);
    renderTripsError(error.message);
    if (!quiet) toast("行程读取失败", error.message, "error");
  }
}

async function loadKnowledge() {
  elements.knowledgeDocuments.replaceChildren(createSkeleton(), createSkeleton());
  try {
    state.knowledge = await request("/knowledge/documents");
    renderKnowledge();
  } catch (error) {
    state.knowledge = [];
    elements.knowledgeDocuments.replaceChildren(
      knowledgeEmpty("知识库读取失败", error.message),
    );
    $("#knowledge-count").textContent = "读取失败";
  }
}

function knowledgeEmpty(title, copy) {
  const empty = node("div", "empty-state knowledge-empty");
  empty.append(node("span", "", "⌕"), node("h3", "", title), node("p", "", copy));
  return empty;
}

function renderKnowledge() {
  $("#knowledge-count").textContent = `${state.knowledge.length} 个文档`;
  elements.knowledgeDocuments.replaceChildren();
  if (!state.knowledge.length) {
    elements.knowledgeDocuments.append(
      knowledgeEmpty("还没有知识文档", "上传攻略、景区政策或自己的旅行笔记开始构建 RAG。"),
    );
    return;
  }
  state.knowledge.forEach((document) => {
    const card = node("article", "knowledge-document surface");
    const icon = node("span", "knowledge-file", document.filename.split(".").pop().toUpperCase());
    const copy = node("div", "knowledge-document-copy");
    copy.append(node("strong", "", document.title));
    copy.append(
      node(
        "small",
        "",
        [document.city, document.category, `${document.chunk_count} chunks`]
          .filter(Boolean)
          .join(" · "),
      ),
    );
    copy.append(node("span", "", `来源：${document.source || document.filename}`));
    const actions = node("div", "knowledge-document-actions");
    actions.append(node("time", "", formatDate(document.created_at)));
    const remove = node("button", "text-button", "删除");
    remove.type = "button";
    remove.dataset.knowledgeDelete = document.id;
    actions.append(remove);
    card.append(icon, copy, actions);
    elements.knowledgeDocuments.append(card);
  });
}

async function uploadKnowledge(event) {
  event.preventDefault();
  const button = $("#knowledge-upload-button");
  const form = new FormData(elements.knowledgeForm);
  setButtonBusy(button, true, "正在解析和向量化…");
  try {
    const document = await request("/knowledge/documents", { method: "POST", body: form });
    elements.knowledgeForm.reset();
    await loadKnowledge();
    toast("知识文档已建立索引", `${document.chunk_count} 个文本片段`);
  } catch (error) {
    toast("知识文档上传失败", error.message, "error");
  } finally {
    setButtonBusy(button, false);
  }
}

async function deleteKnowledge(documentId) {
  if (!window.confirm("确认删除这个文档及其全部向量片段吗？")) return;
  try {
    await request(`/knowledge/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
    await loadKnowledge();
    toast("知识文档已删除");
  } catch (error) {
    toast("删除失败", error.message, "error");
  }
}

async function previewKnowledgeSearch(event) {
  event.preventDefault();
  const button = $("#knowledge-search-button");
  const data = new FormData(elements.knowledgeSearchForm);
  setButtonBusy(button, true, "检索中…");
  elements.knowledgeResults.replaceChildren(createSkeleton());
  try {
    const hits = await request("/knowledge/search", {
      method: "POST",
      body: JSON.stringify({ query: data.get("query"), top_k: 4 }),
    });
    elements.knowledgeResults.replaceChildren();
    if (!hits.length) {
      elements.knowledgeResults.append(
        node("div", "knowledge-placeholder", "没有找到相关内容，请调整问题或先上传资料。"),
      );
      return;
    }
    hits.forEach((hit) => {
      const item = node("article", "knowledge-hit");
      const title = node("strong", "", hit.title || hit.filename);
      const source = node(
        "small",
        "",
        `${hit.source || hit.filename}${hit.page ? ` · 第 ${hit.page} 页` : ""}`,
      );
      item.append(title, source, node("p", "", hit.text));
      elements.knowledgeResults.append(item);
    });
  } catch (error) {
    elements.knowledgeResults.replaceChildren(
      node("div", "knowledge-placeholder is-error", error.message),
    );
  } finally {
    setButtonBusy(button, false);
  }
}

function createSkeleton() {
  return node("div", "skeleton-row");
}

function renderStats(failed = false) {
  const total = failed ? "—" : state.trips.length;
  const drafts = failed ? "—" : state.trips.filter((trip) => trip.status === "draft").length;
  const archived = failed ? "—" : state.trips.filter((trip) => trip.status === "archived").length;
  $("#stat-total").textContent = total;
  $("#stat-draft").textContent = drafts;
  $("#stat-archived").textContent = archived;
}

function renderRecentTrips() {
  elements.recentTrips.replaceChildren();
  const rows = state.trips.slice(0, 4);
  if (!rows.length) {
    const empty = node("div", "timeline-empty", "还没有行程，创建第一段旅程吧。");
    elements.recentTrips.append(empty);
    return;
  }
  rows.forEach((trip) => {
    const item = node("button", "recent-trip");
    item.type = "button";
    item.dataset.tripId = trip.id;
    item.append(node("span", "trip-symbol", "⌖"));
    const copy = node("span");
    copy.append(node("strong", "", `${trip.origin} → ${trip.destination}`));
    copy.append(node("small", "", `${statusText(trip.status)} · ${formatMoney(trip.budget)}`));
    item.append(copy, node("time", "", formatDate(trip.start_at || trip.created_at)), node("b", "", "›"));
    elements.recentTrips.append(item);
  });
}

function renderRecentError(message) {
  elements.recentTrips.replaceChildren(node("div", "timeline-empty", message));
}

function filteredTrips() {
  const query = ($("#trip-search").value || "").trim().toLowerCase();
  const status = $("#trip-status-filter").value;
  return state.trips.filter((trip) => {
    const matchesQuery = !query || `${trip.origin} ${trip.destination}`.toLowerCase().includes(query);
    return matchesQuery && (status === "all" || trip.status === status);
  });
}

function renderTrips() {
  if (!elements.trips) return;
  const rows = filteredTrips();
  $("#trip-count").textContent = `${rows.length} 个行程`;
  elements.trips.replaceChildren();
  if (!rows.length) {
    const empty = $("#empty-template").content.cloneNode(true);
    if (state.trips.length) {
      $("h3", empty).textContent = "没有匹配的行程";
      $("p", empty).textContent = "试试更换关键词或状态筛选。";
      $("button", empty).remove();
    }
    elements.trips.append(empty);
    return;
  }
  rows.forEach((trip) => elements.trips.append(createTripCard(trip)));
}

function renderTripsError(message) {
  elements.trips.replaceChildren();
  const empty = node("div", "empty-state");
  empty.append(node("span", "", "!"), node("h3", "", "无法读取行程"), node("p", "", message));
  const retry = node("button", "button button-primary", "重新加载");
  retry.type = "button";
  retry.addEventListener("click", () => loadTrips());
  empty.append(retry);
  elements.trips.append(empty);
}

function createTripCard(trip) {
  const card = node("article", "trip-card");
  const cover = node("div", "trip-card-cover");
  cover.append(node("span", "pill", statusText(trip.status)));
  const route = node("div", "trip-card-route");
  route.append(node("span", "", trip.origin), node("i"), node("span", "", trip.destination));
  cover.append(route);
  const body = node("div", "trip-card-body");
  const meta = node("div", "trip-meta");
  const date = node("span");
  date.append("◷ 出发时间：", node("b", "", formatDate(trip.start_at)));
  const budget = node("span");
  budget.append("◇ 行程预算：", node("b", "", formatMoney(trip.budget)));
  meta.append(date, budget);
  const actions = node("div", "trip-card-actions");
  actions.append(node("small", "", `创建于 ${formatDate(trip.created_at)}`));
  const button = node("button", "", "查看详情 →");
  button.type = "button";
  button.dataset.tripId = trip.id;
  actions.append(button);
  body.append(meta, actions);
  card.append(cover, body);
  return card;
}

function openCreateDialog() {
  elements.createForm.reset();
  elements.createDialog.showModal();
  setTimeout(() => elements.createForm.elements.origin.focus(), 50);
}

function closeCreateDialog() {
  elements.createDialog.close();
}

async function createTrip(event) {
  event.preventDefault();
  const data = new FormData(elements.createForm);
  const payload = {
    origin: data.get("origin").trim(),
    destination: data.get("destination").trim(),
    thread_id: state.threadId,
  };
  for (const key of ["start_at", "end_at"]) if (data.get(key)) payload[key] = data.get(key);
  if (data.get("budget")) payload.budget = Number(data.get("budget"));
  const submit = $("#create-trip-submit");
  setButtonBusy(submit, true, "正在创建…");
  try {
    const trip = await request("/trips", { method: "POST", body: JSON.stringify(payload) });
    closeCreateDialog();
    toast("行程创建成功", `${trip.origin} → ${trip.destination}`);
    await loadTrips({ quiet: true });
    navigate("trips");
    openTripDrawer(trip.id);
  } catch (error) {
    toast("创建失败", error.message, "error");
  } finally {
    setButtonBusy(submit, false);
  }
}

async function openTripDrawer(tripId) {
  elements.drawer.classList.add("is-open");
  elements.drawer.setAttribute("aria-hidden", "false");
  elements.overlay.hidden = false;
  elements.drawerContent.replaceChildren(createSkeleton(), createSkeleton(), createSkeleton());
  try {
    const [trip, items] = await Promise.all([request(`/trips/${tripId}`), request(`/trips/${tripId}/items`)]);
    state.currentTrip = trip;
    state.items = items;
    renderTripDetail();
  } catch (error) {
    elements.drawerContent.replaceChildren(node("div", "timeline-empty", error.message));
    toast("详情读取失败", error.message, "error");
  }
}

function closeTripDrawer() {
  elements.drawer.classList.remove("is-open");
  elements.drawer.setAttribute("aria-hidden", "true");
  elements.overlay.hidden = true;
  state.currentTrip = null;
  state.items = [];
}

function renderTripDetail() {
  const trip = state.currentTrip;
  if (!trip) return;
  $("#drawer-title").textContent = `${trip.origin}到${trip.destination}`;
  elements.drawerContent.replaceChildren();
  const hero = node("section", "detail-hero");
  hero.append(node("span", "pill", statusText(trip.status)), node("h3", "", `${trip.origin} → ${trip.destination}`), node("p", "", `行程编号 #${trip.id} · 创建于 ${formatDate(trip.created_at, true)}`));
  const stats = node("section", "detail-stats");
  [["出发", formatDate(trip.start_at)], ["返程", formatDate(trip.end_at)], ["预算", formatMoney(trip.budget)]].forEach(([label, value]) => {
    const item = node("div"); item.append(node("small", "", label), node("strong", "", value)); stats.append(item);
  });
  const heading = node("div", "detail-section-heading");
  heading.append(node("h3", "", "行程日程"));
  const addToggle = node("button", "text-button", "＋ 添加日程");
  addToggle.type = "button";
  heading.append(addToggle);
  const timeline = node("div", "timeline");
  const map = node("img", "trip-map");
  map.alt = `${trip.origin}到${trip.destination}的地点分布图`;
  loadTripMap(map, trip.id);
  if (!state.items.length) {
    timeline.append(node("div", "timeline-empty", "还没有详细日程，添加第一项安排吧。"));
  } else {
    state.items.forEach((item) => timeline.append(createTimelineItem(item)));
  }
  const form = createItemForm(trip.id);
  addToggle.addEventListener("click", () => {
    form.hidden = !form.hidden;
    addToggle.textContent = form.hidden ? "＋ 添加日程" : "收起表单";
    if (!form.hidden) $("input[name=title]", form).focus();
  });
  const actions = node("div", "drawer-actions");
  const edit = node("button", "button button-secondary", "编辑行程");
  edit.type = "button";
  edit.addEventListener("click", () => editTrip(edit));
  actions.append(edit);
  if (trip.status !== "archived") {
    const archive = node("button", "button button-danger", "归档此行程");
    archive.type = "button";
    archive.addEventListener("click", () => archiveTrip(archive));
    actions.append(archive);
  } else {
    actions.append(node("span", "pill", "此行程已归档"));
  }
  const remove = node("button", "button button-danger", "删除行程");
  remove.type = "button";
  remove.addEventListener("click", () => deleteTrip(remove));
  actions.append(remove);
  elements.drawerContent.append(hero, stats, map, heading, timeline, form, actions);
}

async function loadTripMap(image, tripId) {
  try {
    const response = await fetch(`/trips/${tripId}/map`, { headers: authHeaders() });
    if (!response.ok) throw new Error();
    const url = URL.createObjectURL(await response.blob());
    image.addEventListener("load", () => URL.revokeObjectURL(url), { once: true });
    image.src = url;
  } catch {
    image.replaceWith(node("div", "timeline-empty", "地图暂时不可用"));
  }
}

function createTimelineItem(item) {
  const row = node("article", "timeline-item");
  row.append(node("span", "timeline-day", `D${item.day_number}`));
  const card = node("div", "timeline-card");
  card.append(node("strong", "", item.title), node("p", "", `⌖ ${item.location}`));
  const details = [item.start_at ? formatDate(item.start_at, true) : null, formatMoney(item.estimated_cost), item.source].filter(Boolean).join(" · ");
  card.append(node("small", "", details));
  const actions = node("div", "timeline-card-actions");
  const edit = node("button", "", "编辑");
  edit.type = "button";
  edit.addEventListener("click", () => editItineraryItem(item));
  const remove = node("button", "", "删除");
  remove.type = "button";
  remove.addEventListener("click", () => deleteItineraryItem(item));
  actions.append(edit, remove);
  card.append(actions);
  row.append(card);
  return row;
}

async function editTrip(button) {
  const trip = state.currentTrip;
  if (!trip) return;
  const origin = window.prompt("出发地", trip.origin);
  if (origin === null) return;
  const destination = window.prompt("目的地", trip.destination);
  if (destination === null) return;
  const budget = window.prompt("预算（留空表示不修改）", trip.budget ?? "");
  const payload = { origin: origin.trim(), destination: destination.trim() };
  if (budget !== "") payload.budget = Number(budget);
  setButtonBusy(button, true, "保存中…");
  try {
    state.currentTrip = await request(`/trips/${trip.id}`, { method: "PATCH", body: JSON.stringify(payload) });
    await loadTrips({ quiet: true });
    renderTripDetail();
    toast("行程已更新");
  } catch (error) {
    toast("更新失败", error.message, "error");
    setButtonBusy(button, false);
  }
}

async function deleteTrip(button) {
  if (!state.currentTrip || !window.confirm("确定永久删除这个行程及全部日程吗？")) return;
  setButtonBusy(button, true, "删除中…");
  try {
    await request(`/trips/${state.currentTrip.id}`, { method: "DELETE" });
    closeTripDrawer();
    await loadTrips({ quiet: true });
    toast("行程已删除");
  } catch (error) {
    toast("删除失败", error.message, "error");
    setButtonBusy(button, false);
  }
}

async function editItineraryItem(item) {
  const title = window.prompt("日程标题", item.title);
  if (title === null) return;
  const location = window.prompt("地点", item.location);
  if (location === null) return;
  try {
    await request(`/trips/${item.trip_id}/items/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title: title.trim(), location: location.trim() }),
    });
    state.items = await request(`/trips/${item.trip_id}/items`);
    renderTripDetail();
    toast("日程已更新");
  } catch (error) { toast("更新失败", error.message, "error"); }
}

async function deleteItineraryItem(item) {
  if (!window.confirm(`确定删除“${item.title}”吗？`)) return;
  try {
    await request(`/trips/${item.trip_id}/items/${item.id}`, { method: "DELETE" });
    state.items = await request(`/trips/${item.trip_id}/items`);
    renderTripDetail();
    toast("日程已删除");
  } catch (error) { toast("删除失败", error.message, "error"); }
}

function createItemForm(tripId) {
  const form = node("form", "add-item-form");
  form.hidden = true;
  const fields = [
    ["title", "日程标题 *", "text", "例如：游览西湖", true],
    ["location", "地点 *", "text", "例如：西湖风景区", true],
    ["day_number", "第几天 *", "number", "1", true],
    ["estimated_cost", "预计花费（元）", "number", "0", false],
    ["start_at", "开始时间", "datetime-local", "", false],
    ["end_at", "结束时间", "datetime-local", "", false],
    ["source", "信息来源", "text", "例如：手动添加", false],
  ];
  fields.forEach(([name, label, type, placeholder, required]) => {
    const wrap = node("label", name === "source" ? "full" : "");
    wrap.append(node("span", "", label));
    const input = node("input");
    input.name = name; input.type = type; input.placeholder = placeholder; input.required = required;
    if (name === "day_number") { input.min = "1"; input.value = "1"; }
    if (name === "estimated_cost") { input.min = "0"; input.step = "0.01"; input.value = "0"; }
    wrap.append(input); form.append(wrap);
  });
  const submit = node("button", "button button-primary full", "保存日程");
  submit.type = "submit";
  form.append(submit);
  form.addEventListener("submit", (event) => addItineraryItem(event, tripId, submit));
  return form;
}

async function addItineraryItem(event, tripId, button) {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  const payload = {
    title: data.get("title").trim(),
    location: data.get("location").trim(),
    day_number: Number(data.get("day_number")),
    sort_order: state.items.length,
    estimated_cost: Number(data.get("estimated_cost") || 0),
  };
  for (const key of ["start_at", "end_at", "source"]) if (data.get(key)) payload[key] = data.get(key);
  setButtonBusy(button, true, "正在保存…");
  try {
    await request(`/trips/${tripId}/items`, { method: "POST", body: JSON.stringify(payload) });
    state.items = await request(`/trips/${tripId}/items`);
    renderTripDetail();
    toast("日程已添加", payload.title);
  } catch (error) {
    toast("日程添加失败", error.message, "error");
    setButtonBusy(button, false);
  }
}

async function archiveTrip(button) {
  if (!state.currentTrip || !window.confirm("归档后该行程会保留，但标记为已结束。确定归档吗？")) return;
  setButtonBusy(button, true, "正在归档…");
  try {
    state.currentTrip = await request(`/trips/${state.currentTrip.id}/archive`, { method: "POST" });
    await loadTrips({ quiet: true });
    renderTripDetail();
    toast("行程已归档");
  } catch (error) {
    toast("归档失败", error.message, "error");
    setButtonBusy(button, false);
  }
}

function historyKey() {
  return `travelmind.chat.${state.threadId}`;
}

function loadHistory() {
  try { state.history = JSON.parse(localStorage.getItem(historyKey())) || []; }
  catch { state.history = []; }
  if (!state.history.length) {
    state.history = [{ role: "agent", text: "你好，我是 TravelMind。告诉我你想去哪里、什么时候出发，以及预算和同行人，我会帮你把想法变成可执行的旅程。", time: Date.now() }];
  }
  renderMessages();
  loadServerHistory();
}

async function loadServerHistory() {
  try {
    const rows = await request(`/chat/${encodeURIComponent(state.threadId)}/history`);
    if (!rows.length) return;
    state.history = rows.map((message) => ({ ...message, time: Date.now() }));
    saveHistory();
    renderMessages();
  } catch { /* local history remains available while the backend reconnects */ }
}

function handleAgentEvent(type, data) {
  if (type === "run.started") setRunState("running");
  if (type === "tool.started") {
    setRunState("running");
    elements.runStatus.textContent = `工具：${data.tool || "执行中"}`;
  }
  if (type === "approval.required" || type === "run.paused") setRunState("approval");
  if (type === "run.completed") setRunState("done");
  if (type === "tool.failed") {
    elements.runStatus.textContent = "工具失败";
    elements.runStatus.className = "pill pill-warning";
  }
}

async function startEventStream() {
  state.eventAbort?.abort();
  const controller = new AbortController();
  state.eventAbort = controller;
  try {
    const response = await fetch(`/chat/${encodeURIComponent(state.threadId)}/events`, {
      headers: authHeaders(),
      signal: controller.signal,
    });
    if (!response.ok || !response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      frames.forEach((frame) => {
        const eventType = frame.match(/^event: (.+)$/m)?.[1];
        const raw = frame.match(/^data: (.+)$/m)?.[1];
        if (!eventType || !raw) return;
        try { handleAgentEvent(eventType, JSON.parse(raw).data || {}); } catch { /* ignore malformed frame */ }
      });
    }
  } catch (error) {
    if (error.name !== "AbortError") setTimeout(startEventStream, 2000);
  }
}

function saveHistory() {
  localStorage.setItem(historyKey(), JSON.stringify(state.history.slice(-60)));
}

function appendMessage(text, role = "agent", persist = true) {
  const message = { role, text: String(text), time: Date.now() };
  state.history.push(message);
  if (persist) saveHistory();
  elements.messages.append(createMessage(message));
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function createMessage(message) {
  const row = node("article", `message-row ${message.role}`);
  if (message.role !== "user") row.append(node("span", "message-avatar", "TM"));
  const bubble = node("div", "message-bubble");
  const meta = node("div", "message-meta");
  meta.append(node("strong", "", message.role === "user" ? "你" : "TravelMind"), node("time", "", new Date(message.time).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })));
  bubble.append(meta, node("div", "message-text", message.text));
  row.append(bubble);
  return row;
}

function renderMessages() {
  elements.messages.replaceChildren(...state.history.map(createMessage));
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function showTyping() {
  const row = node("article", "message-row agent is-typing");
  row.id = "typing-message";
  row.append(node("span", "message-avatar", "TM"));
  const dots = node("div", "message-text");
  dots.append(node("i"), node("i"), node("i"));
  row.append(dots);
  elements.messages.append(row);
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function setRunState(mode) {
  const steps = $$(".run-steps li");
  steps.forEach((step) => step.className = "");
  elements.runStatus.className = "pill";
  if (mode === "running") {
    elements.runStatus.textContent = "运行中";
    elements.runStatus.classList.add("pill-warning");
    steps[0].className = "is-ready"; steps[1].className = "is-active";
  } else if (mode === "approval") {
    elements.runStatus.textContent = "等待批准";
    elements.runStatus.classList.add("pill-warning");
    steps[0].className = "is-ready"; steps[1].className = "is-active";
  } else if (mode === "done") {
    elements.runStatus.textContent = "已完成";
    elements.runStatus.classList.add("pill-success");
    steps.forEach((step) => step.className = "is-ready");
  } else {
    elements.runStatus.textContent = "待命";
    steps[0].className = "is-ready";
  }
}

function displayAgentResult(result) {
  appendMessage(result.message || "任务已完成。", "agent");
  state.pendingApprovals = result.pending_approvals || [];
  renderApprovals();
  setRunState(state.pendingApprovals.length ? "approval" : "done");
}

function renderApprovals() {
  const hasPending = state.pendingApprovals.length > 0;
  elements.approval.hidden = !hasPending;
  $("#nav-approval-badge").hidden = !hasPending;
  elements.approvalDetail.replaceChildren();
  state.pendingApprovals.forEach((approval) => {
    elements.approvalDetail.append(node("div", "approval-item", typeof approval === "string" ? approval : JSON.stringify(approval, null, 2)));
  });
}

async function sendChat(event) {
  event.preventDefault();
  if (state.chatBusy) return;
  const text = elements.messageInput.value.trim();
  if (!text) return;
  appendMessage(text, "user");
  elements.messageInput.value = "";
  elements.messageInput.style.height = "auto";
  state.chatBusy = true;
  elements.sendButton.disabled = true;
  setRunState("running");
  showTyping();
  try {
    const result = await request("/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, thread_id: state.threadId, channel: "web" }),
    });
    $("#typing-message")?.remove();
    displayAgentResult(result);
    if (!state.pendingApprovals.length) await loadTrips({ quiet: true });
  } catch (error) {
    $("#typing-message")?.remove();
    appendMessage(error.message, "error");
    setRunState("idle");
  } finally {
    state.chatBusy = false;
    elements.sendButton.disabled = false;
    elements.messageInput.focus();
  }
}

async function loadApprovals() {
  try {
    const result = await request(`/approvals/${encodeURIComponent(state.threadId)}`);
    state.pendingApprovals = result.pending || [];
    renderApprovals();
    if (state.pendingApprovals.length) setRunState("approval");
  } catch {
    state.pendingApprovals = [];
    renderApprovals();
  }
}

async function decideApproval(decision) {
  const approve = $("#approve");
  const reject = $("#reject");
  approve.disabled = true; reject.disabled = true;
  setRunState("running");
  try {
    const result = await request(`/approvals/${encodeURIComponent(state.threadId)}`, {
      method: "POST",
      body: JSON.stringify({ decision, channel: "web" }),
    });
    displayAgentResult(result);
    await loadTrips({ quiet: true });
    toast(decision === "approve" ? "操作已批准" : "操作已拒绝");
  } catch (error) {
    appendMessage(error.message, "error");
    toast("审批失败", error.message, "error");
  } finally {
    approve.disabled = false; reject.disabled = false;
  }
}

function changeThread(threadId) {
  state.threadId = threadId.trim() || createThreadId();
  elements.threadInput.value = state.threadId;
  localStorage.setItem("travelmind.thread", state.threadId);
  loadHistory();
  loadApprovals();
  setRunState("idle");
  startEventStream();
}

function bindEvents() {
  document.addEventListener("click", (event) => {
    const nav = event.target.closest("[data-nav]");
    if (nav) navigate(nav.dataset.nav);
    if (event.target.closest("[data-open-create]")) openCreateDialog();
    const tripButton = event.target.closest("[data-trip-id]");
    if (tripButton) openTripDrawer(tripButton.dataset.tripId);
    const knowledgeDelete = event.target.closest("[data-knowledge-delete]");
    if (knowledgeDelete) deleteKnowledge(knowledgeDelete.dataset.knowledgeDelete);
  });
  $("#menu-button").addEventListener("click", openMobileMenu);
  elements.overlay.addEventListener("click", () => { closeMobileMenu(); closeTripDrawer(); });
  $$('[data-close-modal]').forEach((button) => button.addEventListener("click", closeCreateDialog));
  $("#close-drawer").addEventListener("click", closeTripDrawer);
  elements.createForm.addEventListener("submit", createTrip);
  elements.authButton.addEventListener("click", toggleAuth);
  elements.authForm.addEventListener("submit", (event) => { event.preventDefault(); authenticate("login"); });
  $("#register-button").addEventListener("click", () => authenticate("register"));
  $$('[data-close-auth]').forEach((button) => button.addEventListener("click", () => elements.authDialog.close()));
  $("#refresh-trips").addEventListener("click", () => loadTrips());
  $("#trip-search").addEventListener("input", renderTrips);
  $("#trip-status-filter").addEventListener("change", renderTrips);
  elements.chatForm.addEventListener("submit", sendChat);
  elements.knowledgeForm.addEventListener("submit", uploadKnowledge);
  elements.knowledgeSearchForm.addEventListener("submit", previewKnowledgeSearch);
  elements.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); elements.chatForm.requestSubmit(); }
  });
  elements.messageInput.addEventListener("input", () => {
    elements.messageInput.style.height = "auto";
    elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 130)}px`;
  });
  $$('[data-prompt]').forEach((button) => button.addEventListener("click", () => {
    elements.messageInput.value = button.dataset.prompt;
    elements.messageInput.focus();
  }));
  elements.threadInput.addEventListener("change", () => changeThread(elements.threadInput.value));
  $("#new-thread").addEventListener("click", () => changeThread(createThreadId()));
  $("#approve").addEventListener("click", () => decideApproval("approve"));
  $("#reject").addEventListener("click", () => decideApproval("reject"));
  window.addEventListener("hashchange", () => navigate(location.hash.slice(1), false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.drawer.classList.contains("is-open")) closeTripDrawer();
  });
}

async function init() {
  $("#today-label").textContent = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date());
  elements.threadInput.value = state.threadId;
  localStorage.setItem("travelmind.thread", state.threadId);
  await loadAuth();
  loadHistory();
  bindEvents();
  navigate(location.hash.slice(1) || "dashboard", false);
  loadHealth();
  loadTrips();
  loadApprovals();
  startEventStream();
}

init();
