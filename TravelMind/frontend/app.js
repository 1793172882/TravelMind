const messages = document.querySelector("#messages");
const chatForm = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message");
const threadInput = document.querySelector("#thread-id");
const approval = document.querySelector("#approval");
const approvalDetail = document.querySelector("#approval-detail");
const trips = document.querySelector("#trips");

function addMessage(text, role = "agent") {
  const item = document.createElement("article");
  item.className = `message ${role}`;
  item.textContent = text;
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function showAgentResult(result) {
  addMessage(result.message);
  const pending = result.pending_approvals || [];
  approval.hidden = pending.length === 0;
  approvalDetail.textContent = pending.length ? JSON.stringify(pending, null, 2) : "";
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  addMessage(text, "user");
  messageInput.value = "";
  const button = chatForm.querySelector("button");
  button.disabled = true;
  try {
    showAgentResult(await request("/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, thread_id: threadInput.value, channel: "web" }),
    }));
  } catch (error) {
    addMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
});

async function decide(decision) {
  try {
    showAgentResult(await request(`/approvals/${encodeURIComponent(threadInput.value)}`, {
      method: "POST",
      body: JSON.stringify({ decision, channel: "web" }),
    }));
    await loadTrips();
  } catch (error) {
    addMessage(error.message, "error");
  }
}

document.querySelector("#approve").addEventListener("click", () => decide("approve"));
document.querySelector("#reject").addEventListener("click", () => decide("reject"));

async function loadTrips() {
  trips.textContent = "正在读取…";
  try {
    const rows = await request("/trips");
    trips.replaceChildren();
    if (!rows.length) {
      trips.textContent = "MySQL 中还没有行程。";
      return;
    }
    for (const row of rows) {
      const item = document.createElement("article");
      item.className = "trip";
      item.textContent = `#${row.id}  ${row.origin} → ${row.destination} · ${row.status}`;
      trips.append(item);
    }
  } catch (error) {
    trips.textContent = error.message;
  }
}

document.querySelector("#refresh-trips").addEventListener("click", loadTrips);
