/* ============================================================
   Library AI Agent — Frontend Application
   Handles: views, chat, search, book details, profile, themes
   ============================================================ */

"use strict";

// ── State ──────────────────────────────────────────────────────
const State = {
  currentView:    "dashboard",
  isLoading:      false,
  reservations:   new Set(),        // book IDs reserved in this session
  profile:        {},
  lastSearchQuery: "",
  authStatus:     { authenticated: false, user: null },
  notifications:  [],
  notifPollInterval: null,
};

/* ═══════════════════════════════════════════════════════════════
   INITIALISATION
═══════════════════════════════════════════════════════════════ */
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  checkAuthStatus();
  loadProfile();
  loadStats();
  loadDashboardData();
  loadCourseOptions();
  showView("dashboard");
  renderGreeting();
  startNotificationPolling();
  loadReservations();
  loadBorrowHistory();
});

// Click outside to close notification panel
document.addEventListener("click", (e) => {
  const panel = document.getElementById("notifPanel");
  const bell  = document.getElementById("notifBell");
  if (panel && !panel.contains(e.target) && !bell.contains(e.target)) {
    panel.classList.add("d-none");
  }
});


/* ═══════════════════════════════════════════════════════════════
   VIEW MANAGEMENT
═══════════════════════════════════════════════════════════════ */
function showView(name) {
  // Hide all
  document.querySelectorAll(".view-section").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));

  // Show target
  const target  = document.getElementById(`view${cap(name)}`);
  const navBtn  = document.getElementById(`nav${cap(name)}`);
  if (target)  target.classList.add("active");
  if (navBtn)  navBtn.classList.add("active");

  State.currentView = name;

  // Chat view: scroll to bottom
  if (name === "chat") scrollChatBottom();

  // Chat view: set special body class so height 100vh works
  if (name === "chat") {
    document.body.classList.add("chat-view-active");
  } else {
    document.body.classList.remove("chat-view-active");
  }
}

function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }


/* ═══════════════════════════════════════════════════════════════
   DARK / LIGHT THEME
═══════════════════════════════════════════════════════════════ */
function initTheme() {
  const saved = localStorage.getItem("library-theme") || "light";
  applyTheme(saved);
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const icon = document.getElementById("themeIcon");
  if (icon) icon.className = theme === "dark" ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
  localStorage.setItem("library-theme", theme);
}

document.getElementById("themeToggle")?.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(current === "dark" ? "light" : "dark");
});


/* ═══════════════════════════════════════════════════════════════
   STATS
═══════════════════════════════════════════════════════════════ */
async function loadStats() {
  try {
    const data = await api("/api/stats");
    setText("statTitles",   data.total_titles);
    setText("statAvail",    data.available_copies);
    setText("statJournals", data.total_journals);
  } catch (_) {}
}


/* ═══════════════════════════════════════════════════════════════
   DASHBOARD
═══════════════════════════════════════════════════════════════ */
async function loadDashboardData() {
  await Promise.all([loadLibraryInfo(), loadFeaturedBooks(), loadJournals()]);
}

async function loadLibraryInfo() {
  const panel = document.getElementById("libraryInfoPanel");
  if (!panel) return;
  try {
    const info = await api("/api/library-info");
    const t  = info.timings;
    const f  = info.fines;
    const br = info.borrowing_rules;
    panel.innerHTML = `
      <div class="info-row">
        <i class="bi bi-clock info-icon"></i>
        <div>
          <div class="info-label">Library Hours</div>
          <div class="info-val">${t.weekdays} (Weekdays)</div>
          <div class="info-val">${t.saturday} (Sat) · ${t.sunday} (Sun)</div>
        </div>
      </div>
      <div class="info-row">
        <i class="bi bi-person-badge info-icon"></i>
        <div>
          <div class="info-label">Borrowing Limit</div>
          <div class="info-val">UG: ${br.undergraduate.books} books / ${br.undergraduate.duration_days} days</div>
          <div class="info-val">PG: ${br.postgraduate.books} books / ${br.postgraduate.duration_days} days</div>
        </div>
      </div>
      <div class="info-row">
        <i class="bi bi-currency-rupee info-icon"></i>
        <div>
          <div class="info-label">Overdue Fine</div>
          <div class="info-val">Rs. ${f.per_day_inr}/day per book</div>
        </div>
      </div>
      <div class="info-row">
        <i class="bi bi-envelope info-icon"></i>
        <div>
          <div class="info-label">Contact</div>
          <div class="info-val">${info.contact.email}</div>
          <div class="info-val">${info.contact.phone}</div>
        </div>
      </div>`;
  } catch (_) {
    panel.innerHTML = `<p class="text-muted small">Could not load library info.</p>`;
  }
}

async function loadFeaturedBooks() {
  const grid = document.getElementById("featuredBooksGrid");
  if (!grid) return;
  try {
    const data = await api("/api/search?q=algorithms+machine+learning+programming");
    const books = data.results || [];
    if (!books.length) { grid.innerHTML = `<p class="text-muted">No books found.</p>`; return; }

    grid.innerHTML = books.slice(0, 8).map(b => `
      <div class="book-card" onclick="openBookModal('${b.id}')">
        <div class="book-card-spine">
          <i class="bi bi-book-fill"></i>
        </div>
        <div class="book-card-title">${esc(b.title)}</div>
        <div class="book-card-author">${esc(b.authors[0])}${b.authors.length > 1 ? " et al." : ""}</div>
        <div class="book-card-meta">
          <span class="avail-badge ${b.available_copies > 0 ? "available" : "unavailable"}">
            ${b.available_copies > 0 ? `✓ ${b.available_copies} left` : "✗ Unavailable"}
          </span>
          <span class="rating-badge"><i class="bi bi-star-fill"></i> ${b.rating}</span>
        </div>
      </div>`).join("");
  } catch (_) {
    grid.innerHTML = `<p class="text-muted">Could not load featured books.</p>`;
  }
}

async function loadJournals() {
  const grid = document.getElementById("journalsGrid");
  if (!grid) return;
  try {
    const data = await api("/api/courses");
    const journals = data.journals || [];
    if (!journals.length) { grid.innerHTML = `<p class="text-muted">No journals found.</p>`; return; }

    const isOpen = (access) => /open access/i.test(access);
    const actionLabel = (j) => isOpen(j.access) ? "Read Online" : "Visit Publisher";
    const btnClass   = (j) => isOpen(j.access) ? "btn-journal-action open" : "btn-journal-action";
    const icon       = (j) => isOpen(j.access) ? "bi-journal-text" : "bi-box-arrow-up-right";

    grid.innerHTML = `<div class="journals-grid">` + journals.map(j => `
      <div class="journal-card" onclick="window.open('${esc(j.url)}','_blank','noopener noreferrer')">
        <div class="journal-title">${esc(j.title)}</div>
        <div class="journal-pub"><i class="bi bi-building me-1"></i>${esc(j.publisher)}</div>
        <div><span class="journal-access${isOpen(j.access) ? ' open-access' : ''}">${esc(j.access)}</span></div>
        <div class="journal-subjects">
          ${j.subjects.map(s => `<span class="src-tag">${esc(s)}</span>`).join("")}
        </div>
        <div class="journal-actions">
          <a href="${esc(j.url)}" target="_blank" rel="noopener noreferrer"
             class="${btnClass(j)}" onclick="event.stopPropagation()">
            <i class="bi ${icon(j)}"></i>${actionLabel(j)}
          </a>
        </div>
      </div>`).join("") + `</div>`;
  } catch (_) {
    grid.innerHTML = `<p class="text-muted">Could not load journals.</p>`;
  }
}

async function loadCourseOptions() {
  try {
    const data = await api("/api/courses");
    const courses = data.courses || [];
    const sel = document.getElementById("courseFilter");
    if (sel) {
      courses.forEach(c => {
        const opt = new Option(c, c);
        sel.appendChild(opt);
      });
    }
  } catch (_) {}
}


/* ═══════════════════════════════════════════════════════════════
   QUICK ASK (dashboard)
═══════════════════════════════════════════════════════════════ */
async function quickAsk() {
  const inp = document.getElementById("quickAskInput");
  const res = document.getElementById("quickAskResult");
  if (!inp || !res) return;
  const q = inp.value.trim();
  if (!q) return;

  res.innerHTML = `<div class="d-flex align-items-center gap-2 text-muted">
    <div class="spinner-border spinner-border-sm text-accent"></div>Thinking…</div>`;

  try {
    const data = await apiPost("/api/chat", { message: q });
    res.innerHTML = `
      <div style="background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:12px 14px;margin-top:4px">
        <div class="rendered-text" style="font-size:13.5px">${mdToHtml(data.reply)}</div>
        ${data.book_cards?.length ? renderMiniCards(data.book_cards) : ""}
      </div>`;
  } catch (e) {
    res.innerHTML = `<p class="text-muted small">Could not get a response. Please try again.</p>`;
  }
}


/* ═══════════════════════════════════════════════════════════════
   CHAT
═══════════════════════════════════════════════════════════════ */
function renderGreeting() {
  const container = document.getElementById("chatMessages");
  if (!container) return;

  const greeting = `Hello! 👋 I'm **Lexis**, your AI Library Assistant. I can help you:\n• 📚 Find books, journals & research papers\n• 🎓 Get course-wise & subject-specific recommendations\n• 🔍 Check real-time book availability\n• 📖 Reserve books & manage your borrowing\n• ℹ️ Answer library rules, timings & service queries\n\nWhat would you like to explore today?`;

  appendMessage("assistant", greeting, null, "Just now");
}

function handleChatKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

async function sendMessage() {
  const input = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  if (!input) return;
  const message = input.value.trim();
  if (!message || State.isLoading) return;

  // Reset input
  input.value = "";
  input.style.height = "auto";

  // Show user message
  const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  appendMessage("user", message, null, now);
  scrollChatBottom();

  // Show typing
  setTyping(true);
  sendBtn.disabled = true;
  State.isLoading = true;

  try {
    const data = await apiPost("/api/chat", { message });
    setTyping(false);

    const replyTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    appendMessage("assistant", data.reply, data.book_cards, replyTime);
    scrollChatBottom();
  } catch (err) {
    setTyping(false);
    appendMessage("assistant", "Sorry, I encountered an error. Please try again.", null,
      new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
  } finally {
    State.isLoading = false;
    sendBtn.disabled = false;
    input.focus();
    scrollChatBottom();
  }
}

function sendQuickPrompt(text) {
  const input = document.getElementById("chatInput");
  if (input) input.value = text;
  showView("chat");
  setTimeout(() => sendMessage(), 100);
}

function appendMessage(role, text, bookCards, time) {
  const container = document.getElementById("chatMessages");
  if (!container) return;

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const isUser = role === "user";
  const avatarHtml = !isUser ? `
    <div class="agent-avatar sm"><i class="bi bi-robot"></i></div>` : "";

  let cardsHtml = "";
  if (bookCards && bookCards.length) {
    cardsHtml = `<div class="chat-book-cards">${renderMiniCards(bookCards)}</div>`;
  }

  row.innerHTML = `
    ${avatarHtml}
    <div>
      <div class="message-bubble ${role} rendered-text">${mdToHtml(esc(text))}</div>
      ${cardsHtml}
      <div class="message-meta">${time || ""}</div>
    </div>`;

  container.appendChild(row);
}

function setTyping(show) {
  const el = document.getElementById("typingIndicator");
  if (el) el.classList.toggle("d-none", !show);
}

function scrollChatBottom() {
  const c = document.getElementById("chatMessages");
  if (c) setTimeout(() => { c.scrollTop = c.scrollHeight; }, 30);
}

async function clearChat() {
  try { await apiPost("/api/clear-chat", {}); } catch (_) {}
  const container = document.getElementById("chatMessages");
  if (container) container.innerHTML = "";
  renderGreeting();
  showToast("Chat cleared", "info");
}


/* ═══════════════════════════════════════════════════════════════
   SEARCH
═══════════════════════════════════════════════════════════════ */
async function doSearch() {
  const q = (document.getElementById("searchInput")?.value || "").trim();
  if (!q) { showToast("Please enter a search term", "info"); return; }
  State.lastSearchQuery = q;
  await renderSearchResults(`/api/search?q=${encodeURIComponent(q)}`);
}

async function doCourseSearch() {
  const course = document.getElementById("courseFilter")?.value;
  if (!course) {
    document.getElementById("searchResultsContainer").innerHTML = `
      <div class="text-center text-muted py-5">
        <i class="bi bi-search display-4 opacity-25"></i>
        <p class="mt-2">Enter a search term or select a course</p>
      </div>`;
    return;
  }
  await renderSearchResults(`/api/search?course=${encodeURIComponent(course)}`);
}

async function renderSearchResults(endpoint) {
  const container = document.getElementById("searchResultsContainer");
  container.innerHTML = `
    <div class="text-center py-5">
      <div class="spinner-border text-accent"></div>
      <p class="mt-3 text-muted">Searching catalog…</p>
    </div>`;

  try {
    const data = await api(endpoint);
    const results = data.results || [];

    if (!results.length) {
      container.innerHTML = `
        <div class="text-center text-muted py-5">
          <i class="bi bi-search display-4 opacity-25"></i>
          <p class="mt-2">No results found. Try different keywords.</p>
        </div>`;
      return;
    }

    container.innerHTML = `
      <div class="mb-3" style="font-size:13px;color:var(--text-muted)">
        Found <strong>${results.length}</strong> result${results.length !== 1 ? "s" : ""}
      </div>
      <div class="search-results-grid">
        ${results.map(b => searchResultCard(b)).join("")}
      </div>`;
  } catch (_) {
    container.innerHTML = `<p class="text-muted">Search failed. Please try again.</p>`;
  }
}

function searchResultCard(b) {
  const avail = b.available_copies > 0;
  return `
    <div class="search-result-card" onclick="openBookModal('${b.id}')">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
        <div>
          <div class="src-title">${esc(b.title)}</div>
          <div class="src-author">${esc(b.authors.join(", "))}</div>
        </div>
        <span class="rating-badge" style="flex-shrink:0"><i class="bi bi-star-fill"></i> ${b.rating}</span>
      </div>
      <div style="font-size:12px;color:var(--text-muted);margin-top:4px">
        ${esc(b.edition)} · ${esc(b.publisher)} · ${b.year}
      </div>
      <div class="src-location">
        <i class="bi bi-geo-alt"></i>${esc(b.location)}
        <span class="ms-auto avail-badge ${avail ? "available" : "unavailable"}">
          ${avail ? `✓ ${b.available_copies} copies` : "✗ Unavailable"}
        </span>
      </div>
      <div class="src-tags">
        <span class="src-tag">${esc(b.category)}</span>
        <span class="src-tag">${esc(b.subcategory)}</span>
        ${(b.tags || []).slice(0, 2).map(t => `<span class="src-tag">${esc(t)}</span>`).join("")}
      </div>
    </div>`;
}


/* ═══════════════════════════════════════════════════════════════
   BOOK DETAIL MODAL
═══════════════════════════════════════════════════════════════ */
async function openBookModal(bookId) {
  const modal = new bootstrap.Modal(document.getElementById("bookModal"));
  const body  = document.getElementById("modalBookBody");
  const title = document.getElementById("modalBookTitle");

  body.innerHTML = `
    <div class="text-center py-5">
      <div class="spinner-border text-accent"></div>
      <p class="mt-3 text-muted">Loading book details…</p>
    </div>`;
  modal.show();

  try {
    const b = await api(`/api/book/${bookId}`);
    title.textContent = b.title;

    const avail = b.available_copies > 0;
    const userReserved = b.user_reserved || State.reservations.has(bookId);

    body.innerHTML = `
      <div class="row g-3">
        <div class="col-md-4 text-center">
          <div style="width:100px;height:135px;background:linear-gradient(135deg,var(--accent-light),var(--purple-light));
            border-left:5px solid var(--accent);border-radius:6px;display:inline-flex;
            align-items:center;justify-content:center;font-size:38px;color:var(--accent)">
            <i class="bi bi-book-fill"></i>
          </div>
          <div class="mt-3">
            <span class="avail-badge ${avail ? "available" : "unavailable"}" style="font-size:12.5px;padding:4px 12px">
              ${avail ? `✓ ${b.available_copies} / ${b.total_copies} Available` : `✗ All ${b.total_copies} copies borrowed`}
            </span>
          </div>
          <div class="mt-2 rating-badge justify-content-center" style="font-size:14px">
            <i class="bi bi-star-fill"></i> ${b.rating} / 5.0
          </div>
          <div class="mt-3 d-flex flex-column gap-2">
            <button class="btn btn-primary-custom w-100" onclick="reserveBook('${b.id}', this)"
              ${userReserved ? "disabled" : ""}>
              <i class="bi bi-bookmark-plus me-2"></i>${userReserved ? "Reserved ✓" : "Reserve Book"}
            </button>
            <button class="btn" style="background:var(--surface-2);border:1px solid var(--border);
              border-radius:8px;padding:8px;font-size:13px;cursor:pointer;color:var(--text)"
              onclick="loadAiSummary('${b.id}', this)">
              <i class="bi bi-cpu me-2 text-accent"></i>AI Summary
            </button>
          </div>
        </div>

        <div class="col-md-8">
          <div class="modal-detail-row"><span class="modal-detail-label">Title</span>
            <span class="modal-detail-value fw-600">${esc(b.title)}</span></div>
          <div class="modal-detail-row"><span class="modal-detail-label">Author(s)</span>
            <span class="modal-detail-value">${esc(b.authors.join("; "))}</span></div>
          <div class="modal-detail-row"><span class="modal-detail-label">Edition</span>
            <span class="modal-detail-value">${esc(b.edition)}</span></div>
          <div class="modal-detail-row"><span class="modal-detail-label">Publisher</span>
            <span class="modal-detail-value">${esc(b.publisher)} (${b.year})</span></div>
          <div class="modal-detail-row"><span class="modal-detail-label">ISBN</span>
            <span class="modal-detail-value" style="font-family:monospace">${esc(b.isbn)}</span></div>
          <div class="modal-detail-row"><span class="modal-detail-label">Category</span>
            <span class="modal-detail-value">${esc(b.category)} › ${esc(b.subcategory)}</span></div>
          <div class="modal-detail-row"><span class="modal-detail-label">Location</span>
            <span class="modal-detail-value"><i class="bi bi-geo-alt text-accent me-1"></i>${esc(b.location)}</span></div>
          <div class="modal-detail-row"><span class="modal-detail-label">Courses</span>
            <span class="modal-detail-value">${(b.courses || []).map(c => `<span class="src-tag">${esc(c)}</span>`).join(" ")}</span></div>
          <div class="modal-detail-row"><span class="modal-detail-label">Waitlist</span>
            <span class="modal-detail-value">${b.waitlist_count > 0 ? `${b.waitlist_count} student(s) waiting` : "No waitlist"}</span></div>

          <div class="mt-3 d-flex gap-2">
            ${avail ? `
              <button class="btn btn-success w-100" onclick="borrowBook('${b.id}', this)" id="borrowBtn_${b.id}">
                <i class="bi bi-book me-2"></i>Borrow Book
              </button>` : ""}
            ${!avail && !userReserved ? `
              <button class="btn btn-outline-custom w-100" onclick="reserveBook('${b.id}', this)">
                <i class="bi bi-bookmark-plus me-2"></i>Reserve Book
              </button>` : ""}
            ${userReserved ? `
              <button class="btn btn-outline-custom w-100" disabled>
                <i class="bi bi-bookmark-check me-2"></i>Reserved ✓
              </button>` : ""}
          </div>

          <div style="margin-top:14px">
            <div style="font-size:12px;font-weight:700;color:var(--text-muted);text-transform:uppercase;
              letter-spacing:.5px;margin-bottom:6px">About This Book</div>
            <p style="font-size:13.5px;color:var(--text);line-height:1.7">${esc(b.summary)}</p>
          </div>

          <div id="aiSummaryContainer_${b.id}" class="mt-2"></div>

          ${b.similar_books?.length ? `
          <div style="margin-top:16px">
            <div style="font-size:12px;font-weight:700;color:var(--text-muted);text-transform:uppercase;
              letter-spacing:.5px;margin-bottom:8px">Similar Books</div>
            <div class="similar-books-row">
              ${b.similar_books.map(s => `
                <div class="similar-book-chip" onclick="openBookModal('${s.id}')">
                  <div style="font-size:12px;font-weight:600;color:var(--text)">${esc(s.title)}</div>
                  <div style="font-size:11px;color:var(--text-muted)">${esc(s.authors[0])}</div>
                  <span class="avail-badge ${s.available ? "available" : "unavailable"}" style="margin-top:4px">
                    ${s.available ? "✓ Available" : "✗ Unavailable"}</span>
                </div>`).join("")}
            </div>
          </div>` : ""}
        </div>
      </div>`;

  } catch (_) {
    body.innerHTML = `<p class="text-muted text-center py-4">Could not load book details.</p>`;
  }
}

async function loadAiSummary(bookId, btn) {
  const container = document.getElementById(`aiSummaryContainer_${bookId}`);
  if (!container) return;
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner-border spinner-border-sm text-accent me-2"></div>Generating…`;

  try {
    const data = await api(`/api/summary/${bookId}`);
    container.innerHTML = `
      <div class="ai-summary-block">
        <div class="ai-badge"><i class="bi bi-cpu me-1"></i>IBM Granite Summary</div>
        <p style="margin:0;font-size:13.5px;line-height:1.7">${esc(data.summary)}</p>
      </div>`;
    btn.style.display = "none";
  } catch (_) {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-cpu me-2 text-accent"></i>Retry AI Summary`;
  }
}

async function borrowBook(bookId, btn) {
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner-border spinner-border-sm me-2"></div>Borrowing…`;
  try {
    const data = await apiPost(`/api/borrow/${bookId}`, {});
    showToast(data.message || "Book borrowed successfully!", "success");
    btn.innerHTML = `<i class="bi bi-check-circle me-2"></i>Borrowed ✓`;
    loadBorrowHistory();
    loadNotifications();
    setTimeout(() => {
      bootstrap.Modal.getInstance(document.getElementById("bookModal")).hide();
    }, 1200);
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-book me-2"></i>Borrow Book`;
    showToast(err.message || "Borrow failed", "error");
  }
}

async function reserveBook(bookId, btn) {
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner-border spinner-border-sm me-2"></div>Reserving…`;
  try {
    const data = await apiPost(`/api/reserve/${bookId}`, {});
    State.reservations.add(bookId);
    btn.innerHTML = `<i class="bi bi-bookmark-check me-2"></i>Reserved ✓`;
    showToast(data.message || "Book reserved successfully!", "success");
    loadReservations();
    loadNotifications();
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-bookmark-plus me-2"></i>Reserve Book`;
    showToast(err.message || "Reservation failed", "error");
  }
}


/* ═══════════════════════════════════════════════════════════════
   PROFILE
═══════════════════════════════════════════════════════════════ */
async function loadProfile() {
  try {
    const p = await api("/api/profile");
    State.profile = p;
    if (p.name)       setValue("profileName",      p.name);
    if (p.student_id) setValue("profileStudentId", p.student_id);
    if (p.email)      setValue("profileEmail",      p.email);
    if (p.course)     setValue("profileCourse",     p.course);
    if (p.semester)   setValue("profileSemester",   p.semester);
    updateSidebarProfile(p);
  } catch (_) {}
}

async function saveProfile() {
  const msgEl = document.getElementById("profileSaveMsg");
  const profile = {
    name:       val("profileName"),
    student_id: val("profileStudentId"),
    email:      val("profileEmail"),
    course:     val("profileCourse"),
    semester:   val("profileSemester"),
  };
  try {
    const data = await apiPost("/api/profile", profile);
    State.profile = data.profile;
    updateSidebarProfile(data.profile);
    if (msgEl) msgEl.innerHTML = `<span class="save-success"><i class="bi bi-check-circle me-1"></i>Profile saved successfully!</span>`;
    showToast("Profile saved! Recommendations will be personalised.", "success");
    setTimeout(() => { if (msgEl) msgEl.innerHTML = ""; }, 3000);
  } catch (_) {
    if (msgEl) msgEl.innerHTML = `<span class="save-error"><i class="bi bi-x-circle me-1"></i>Failed to save profile.</span>`;
  }
}

function updateSidebarProfile(p) {
  setText("sidebarProfileName",   p.name   || "Guest");
  setText("sidebarProfileCourse", p.course || "Set your course →");
}


/* ═══════════════════════════════════════════════════════════════
   MINI BOOK CARDS (for chat / quick-ask)
═══════════════════════════════════════════════════════════════ */
function renderMiniCards(cards) {
  return `<div class="chat-book-cards">` +
    cards.map(b => `
      <div class="mini-book-card" onclick="openBookModal('${b.id}')">
        <div class="mini-book-title">${esc(b.title)}</div>
        <div class="mini-book-author">${esc(b.authors[0])}${b.authors.length > 1 ? " et al." : ""}</div>
        <div class="mini-book-meta">
          <span class="avail-badge ${b.available ? "available" : "unavailable"}" style="font-size:10px">
            ${b.available ? "✓ Available" : "✗ Out"}
          </span>
          <span class="rating-badge" style="font-size:10.5px">
            <i class="bi bi-star-fill"></i>${b.rating}
          </span>
        </div>
      </div>`).join("") +
    `</div>`;
}


/* ═══════════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
═══════════════════════════════════════════════════════════════ */
function showToast(msg, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const icons = { success: "bi-check-circle-fill", error: "bi-x-circle-fill", info: "bi-info-circle-fill" };
  const colors = { success: "var(--green)", error: "var(--red)", info: "var(--accent)" };

  const toast = document.createElement("div");
  toast.className = `custom-toast ${type}`;
  toast.style.marginBottom = "8px";
  toast.innerHTML = `
    <i class="bi ${icons[type] || icons.info}" style="color:${colors[type]};font-size:16px;flex-shrink:0"></i>
    <span>${esc(msg)}</span>`;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "opacity .3s,transform .3s";
    setTimeout(() => toast.remove(), 350);
  }, 3500);
}


/* ═══════════════════════════════════════════════════════════════
   MARKDOWN-LITE RENDERER
   Supports: **bold**, *italic*, - lists, # headers, `code`, \n
═══════════════════════════════════════════════════════════════ */
function mdToHtml(text) {
  if (!text) return "";
  // The text was already esc'd by the caller — unescape &amp; first if needed
  let t = text;

  // Headers
  t = t.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  t = t.replace(/^## (.+)$/gm,  "<h2>$1</h2>");
  t = t.replace(/^# (.+)$/gm,   "<h1>$1</h1>");

  // Bold / italic
  t = t.replace(/\*\*(.+?)\*\*/g,  "<strong>$1</strong>");
  t = t.replace(/\*(.+?)\*/g,      "<em>$1</em>");

  // Inline code
  t = t.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Bullet lists
  t = t.replace(/^[•\-\*] (.+)$/gm, "<li>$1</li>");
  t = t.replace(/(<li>[\s\S]*?<\/li>)/g, "<ul>$1</ul>");
  // Clean duplicate ul wraps
  t = t.replace(/<\/ul>\s*<ul>/g, "");

  // Numbered lists
  t = t.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

  // Paragraphs (double newline)
  t = t.replace(/\n{2,}/g, "</p><p>");
  // Single newlines → br
  t = t.replace(/\n/g, "<br>");

  t = "<p>" + t + "</p>";
  // Fix broken p tags
  t = t.replace(/<p>\s*<\/p>/g, "");
  t = t.replace(/<p>(<[uh][123l])/g, "$1");
  t = t.replace(/(<\/[uh][123l]>)<\/p>/g, "$1");
  t = t.replace(/<p>(<br>)+/g, "<p>");
  t = t.replace(/(<br>)+<\/p>/g, "</p>");

  return t;
}


/* ═══════════════════════════════════════════════════════════════
   UTILITIES
═══════════════════════════════════════════════════════════════ */
/** Escape HTML special chars */
function esc(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setText(id, v) {
  const el = document.getElementById(id);
  if (el) el.textContent = v;
}
function setValue(id, v) {
  const el = document.getElementById(id);
  if (el) el.value = v;
}
function val(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}


/* ═══════════════════════════════════════════════════════════════
   HTTP HELPERS
═══════════════════════════════════════════════════════════════ */
async function api(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  });
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    if (json.auth_required) {
      showToast("Please login to continue", "info");
      openAuthModal("login");
    }
    throw new Error(json.error || `HTTP ${res.status}`);
  }
  return res.json();
}

async function apiDelete(url) {
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}


/* ═══════════════════════════════════════════════════════════════
   AUTHENTICATION
═══════════════════════════════════════════════════════════════ */
async function checkAuthStatus() {
  try {
    const data = await api("/api/auth/status");
    State.authStatus = data;
    updateAuthUI();
  } catch (_) {}
}

function updateAuthUI() {
  const loginBtn      = document.getElementById("authLoginBtn");
  const userDropdown  = document.getElementById("authUserDropdown");
  const userLabel     = document.getElementById("authUserLabel");
  if (!loginBtn || !userDropdown) return;

  if (State.authStatus.authenticated && State.authStatus.user) {
    const name = State.authStatus.user.name || "User";
    userLabel.textContent = name;
    loginBtn.classList.add("d-none");
    userDropdown.classList.remove("d-none");
  } else {
    loginBtn.classList.remove("d-none");
    userDropdown.classList.add("d-none");
  }
}

function showUserMenu() {
  // Kept for any legacy callers; Bootstrap dropdown handles open/close natively
}

function openAuthModal(mode) {
  const modal = new bootstrap.Modal(document.getElementById("authModal"));
  switchAuthMode(mode);
  modal.show();
}

function switchAuthMode(mode) {
  const title      = document.getElementById("authModalTitle");
  const loginForm  = document.getElementById("loginForm");
  const regForm    = document.getElementById("registerForm");
  const loginErr   = document.getElementById("loginError");
  const regErr     = document.getElementById("regError");

  if (mode === "register") {
    title.textContent = "Create Account";
    loginForm.classList.add("d-none");
    regForm.classList.remove("d-none");
    if (regErr) regErr.classList.add("d-none");
  } else {
    title.textContent = "Login";
    regForm.classList.add("d-none");
    loginForm.classList.remove("d-none");
    if (loginErr) loginErr.classList.add("d-none");
  }
}

async function doLogin() {
  const email    = val("loginEmail");
  const password = val("loginPassword");
  const errEl    = document.getElementById("loginError");

  if (!email || !password) {
    if (errEl) { errEl.textContent = "Email and password required"; errEl.classList.remove("d-none"); }
    return;
  }
  try {
    const data = await apiPost("/api/auth/login", { email, password });
    showToast(data.message || "Login successful", "success");
    bootstrap.Modal.getInstance(document.getElementById("authModal")).hide();
    await checkAuthStatus();
    loadProfile();
    loadReservations();
    loadBorrowHistory();
    loadNotifications();
  } catch (err) {
    if (errEl) { errEl.textContent = err.message; errEl.classList.remove("d-none"); }
  }
}

async function doRegister() {
  const name      = val("regName");
  const student_id= val("regStudentId");
  const email     = val("regEmail");
  const password  = val("regPassword");
  const course    = val("regCourse");
  const errEl     = document.getElementById("regError");

  if (!name || !email || !password) {
    if (errEl) { errEl.textContent = "Name, email and password required"; errEl.classList.remove("d-none"); }
    return;
  }
  if (password.length < 6) {
    if (errEl) { errEl.textContent = "Password must be at least 6 characters"; errEl.classList.remove("d-none"); }
    return;
  }
  try {
    const data = await apiPost("/api/auth/register", { name, student_id, email, password, course });
    showToast(data.message || "Registration successful", "success");
    bootstrap.Modal.getInstance(document.getElementById("authModal")).hide();
    await checkAuthStatus();
    loadProfile();
  } catch (err) {
    if (errEl) { errEl.textContent = err.message; errEl.classList.remove("d-none"); }
  }
}

async function doLogout() {
  try {
    await apiPost("/api/auth/logout", {});
    showToast("Logged out successfully", "info");
    State.authStatus = { authenticated: false, user: null };
    updateAuthUI();
    loadProfile();
    loadReservations();
    loadBorrowHistory();
    State.notifications = [];
    renderNotifications();
  } catch (_) {}
}


/* ═══════════════════════════════════════════════════════════════
   NOTIFICATIONS  (localStorage-backed demo system)
═══════════════════════════════════════════════════════════════ */

const NOTIF_STORAGE_KEY = "lib_ai_notifications";

const DEMO_NOTIFICATIONS = [
  {
    id: 1,
    type: "welcome",
    title: "Welcome back to University Central Library",
    message: "Explore thousands of books, journals, and AI-powered recommendations.",
    time: "Just now",
    is_read: false,
  },
  {
    id: 2,
    type: "recommendation",
    title: "AI recommendations generated successfully",
    message: "Based on your reading history, 8 new titles have been curated for you.",
    time: "2 minutes ago",
    is_read: false,
  },
  {
    id: 3,
    type: "reservation",
    title: "Book reserved successfully",
    message: "\"Introduction to Algorithms\" has been reserved. Pick up within 48 hours.",
    time: "1 hour ago",
    is_read: false,
  },
  {
    id: 4,
    type: "profile",
    title: "Profile updated successfully",
    message: "Your academic profile and course preferences have been saved.",
    time: "Yesterday",
    is_read: false,
  },
  {
    id: 5,
    type: "new_arrival",
    title: "New AI & Machine Learning books added",
    message: "12 new titles including \"Deep Learning\" and \"AI Engineering\" are now available.",
    time: "2 days ago",
    is_read: false,
  },
];

function _notifIconFor(type) {
  const map = {
    welcome:        "bi-house-heart",
    recommendation: "bi-stars",
    reservation:    "bi-bookmark-check-fill",
    profile:        "bi-person-check-fill",
    new_arrival:    "bi-book-fill",
    due_date:       "bi-clock-fill",
    fine:           "bi-exclamation-triangle-fill",
  };
  return map[type] || "bi-bell-fill";
}

function _loadNotifStorage() {
  try {
    const raw = localStorage.getItem(NOTIF_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  // First visit: seed with demo notifications
  localStorage.setItem(NOTIF_STORAGE_KEY, JSON.stringify(DEMO_NOTIFICATIONS));
  return DEMO_NOTIFICATIONS;
}

function _saveNotifStorage(notifications) {
  try {
    localStorage.setItem(NOTIF_STORAGE_KEY, JSON.stringify(notifications));
  } catch (_) {}
}

function startNotificationPolling() {
  loadNotifications();
}

function loadNotifications() {
  State.notifications = _loadNotifStorage();
  const unread = State.notifications.filter(n => !n.is_read).length;
  const badge = document.getElementById("notifBadge");
  if (badge) {
    if (unread > 0) {
      badge.textContent = unread;
      badge.classList.remove("d-none");
    } else {
      badge.classList.add("d-none");
    }
  }
  renderNotifications();
}

function renderNotifications() {
  const list = document.getElementById("notifList");
  if (!list) return;
  if (!State.notifications.length) {
    list.innerHTML = `
      <div class="notif-empty">
        <i class="bi bi-bell-slash notif-empty-icon"></i>
        <div class="notif-empty-text">No notifications</div>
      </div>`;
    return;
  }
  const unreadCount = State.notifications.filter(n => !n.is_read).length;
  const labelEl = document.getElementById("notifUnreadLabel");
  if (labelEl) {
    labelEl.textContent = unreadCount > 0 ? `${unreadCount} unread` : "All read";
    labelEl.className = "notif-unread-label" + (unreadCount > 0 ? " has-unread" : " all-read");
  }
  list.innerHTML = State.notifications.map(n => `
    <div class="notif-item ${n.is_read ? "read" : "unread"}" onclick="markNotifRead(${n.id})">
      <div class="notif-icon ${n.type}">
        <i class="bi ${_notifIconFor(n.type)}"></i>
      </div>
      <div class="notif-content">
        <div class="notif-title">${esc(n.title)}${!n.is_read ? '<span class="notif-dot"></span>' : ''}</div>
        <div class="notif-message">${esc(n.message)}</div>
        <div class="notif-time"><i class="bi bi-clock me-1" style="font-size:9px"></i>${esc(n.time)}</div>
      </div>
    </div>`).join("");
}

function toggleNotifPanel() {
  const panel = document.getElementById("notifPanel");
  if (!panel) return;
  const isHidden = panel.classList.contains("d-none");
  panel.classList.toggle("d-none");
  if (isHidden) {
    // Mark all as read when panel is opened
    const notifications = _loadNotifStorage();
    const hadUnread = notifications.some(n => !n.is_read);
    if (hadUnread) {
      notifications.forEach(n => { n.is_read = true; });
      _saveNotifStorage(notifications);
      State.notifications = notifications;
      // Hide badge immediately
      const badge = document.getElementById("notifBadge");
      if (badge) badge.classList.add("d-none");
      // Re-render to remove unread highlights (slight delay for visual feedback)
      setTimeout(renderNotifications, 300);
    }
  }
}

function markNotifRead(notifId) {
  const notifications = _loadNotifStorage();
  const notif = notifications.find(n => n.id === notifId);
  if (notif) {
    notif.is_read = true;
    _saveNotifStorage(notifications);
    State.notifications = notifications;
    loadNotifications();
  }
}

function clearAllNotifications() {
  _saveNotifStorage([]);
  State.notifications = [];
  loadNotifications();
  showToast("All notifications cleared", "info");
}

// Legacy stubs — kept so any server-side callers don't break
async function markAllNotifRead() {
  const notifications = _loadNotifStorage();
  notifications.forEach(n => { n.is_read = true; });
  _saveNotifStorage(notifications);
  State.notifications = notifications;
  loadNotifications();
  showToast("All notifications marked as read", "info");
}


/* ═══════════════════════════════════════════════════════════════
   RESERVATIONS
═══════════════════════════════════════════════════════════════ */
async function loadReservations() {
  const panel = document.getElementById("reservationsPanel");
  if (!panel) return;
  try {
    const data = await api("/api/reservations");
    const recs = data.reservations || [];
    if (!recs.length) {
      panel.innerHTML = `
        <div class="text-muted text-center py-3">
          <i class="bi bi-bookmark display-6 opacity-25"></i>
          <p class="mt-2 mb-0 small">No active reservations</p>
        </div>`;
      return;
    }
    panel.innerHTML = recs.map(r => `
      <div class="history-item">
        <div class="history-title">${esc(r.title)}</div>
        <div class="history-meta">
          <span>Reserved: ${r.reserved_at}</span>
          <span>Position: ${r.position}</span>
          <span class="status-badge status-${r.status}">${r.status}</span>
        </div>
        <button class="btn-link-custom mt-2" onclick="cancelReservation(${r.id})" style="color:var(--red)">
          <i class="bi bi-x-circle me-1"></i>Cancel
        </button>
      </div>`).join("");
  } catch (_) {}
}

async function cancelReservation(resId) {
  if (!confirm("Cancel this reservation?")) return;
  try {
    await apiDelete(`/api/reservations/${resId}`);
    showToast("Reservation cancelled", "info");
    loadReservations();
  } catch (_) {
    showToast("Failed to cancel reservation", "error");
  }
}


/* ═══════════════════════════════════════════════════════════════
   BORROWING HISTORY
═══════════════════════════════════════════════════════════════ */
async function loadBorrowHistory() {
  const panel = document.getElementById("historyPanel");
  if (!panel) return;
  try {
    const data = await api("/api/history");
    const recs = data.history || [];
    const totalFine = data.total_fine_due || 0;

    if (!recs.length) {
      panel.innerHTML = `
        <div class="text-muted text-center py-3">
          <i class="bi bi-clock-history display-6 opacity-25"></i>
          <p class="mt-2 mb-0 small">No borrowing history yet</p>
        </div>`;
      return;
    }

    let html = "";
    if (totalFine > 0) {
      html += `<div style="background:var(--red-light);border:1px solid var(--red);border-radius:8px;padding:10px;margin-bottom:12px;font-size:13px">
        <strong>⚠️ Total Fine Due: Rs. ${totalFine}</strong>
      </div>`;
    }

    html += recs.map(r => `
      <div class="history-item">
        <div class="history-title">${esc(r.title)}</div>
        <div class="history-meta">
          <span>Borrowed: ${r.borrow_date}</span>
          <span>Due: ${r.due_date}</span>
          ${r.return_date ? `<span>Returned: ${r.return_date}</span>` : ""}
          <span class="status-badge status-${r.status}">${r.status}</span>
        </div>
        ${r.fine_amount > 0 ? `
          <div class="mt-2" style="color:var(--red);font-size:12px">
            Fine: Rs. ${r.fine_amount.toFixed(0)}
            ${!r.fine_paid ? `<button class="btn-link-custom ms-2" onclick="payFine(${r.id})" style="color:var(--accent)">
              Pay Now</button>` : " (Paid ✓)"}
          </div>` : ""}
        ${r.status === "borrowed" || r.status === "overdue" ? `
          <button class="btn-link-custom mt-2" onclick="returnBookFromHistory('${r.book_id}')" style="color:var(--accent)">
            <i class="bi bi-arrow-return-left me-1"></i>Return Book
          </button>
          <button class="btn-link-custom mt-2 ms-2" onclick="renewBook('${r.book_id}')" style="color:var(--green)">
            <i class="bi bi-arrow-repeat me-1"></i>Renew
          </button>` : ""}
      </div>`).join("");

    panel.innerHTML = html;
  } catch (_) {}
}

async function payFine(borrowId) {
  if (!confirm("Mark this fine as paid? (Requires actual payment verification)")) return;
  try {
    const data = await apiPost(`/api/fines/${borrowId}/pay`, {});
    showToast(data.message || "Fine paid", "success");
    loadBorrowHistory();
  } catch (_) {
    showToast("Failed to pay fine", "error");
  }
}

async function returnBookFromHistory(bookId) {
  if (!confirm("Confirm book return?")) return;
  try {
    const data = await apiPost(`/api/return/${bookId}`, {});
    showToast(data.message || "Book returned", "success");
    loadBorrowHistory();
    loadReservations();
  } catch (err) {
    showToast(err.message || "Failed to return", "error");
  }
}

async function renewBook(bookId) {
  try {
    const data = await apiPost(`/api/books/${bookId}/renew`, {});
    showToast(data.message || "Book renewed", "success");
    loadBorrowHistory();
  } catch (err) {
    showToast(err.message || "Renewal failed", "error");
  }
}


/* ═══════════════════════════════════════════════════════════════
   BOOK MODAL — updated with borrow/return buttons
═══════════════════════════════════════════════════════════════ */
