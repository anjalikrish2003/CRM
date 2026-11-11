const chatMessages = document.getElementById('chatMessages');
const input = document.getElementById('questionInput');
const sendBtn = document.getElementById('sendBtn');
const clearBtn = document.getElementById('clearChatBtn');
const suggestionChips = document.getElementById('suggestionChips');
const dbSummary = document.getElementById('dbSummary');
const historyList = document.getElementById('historyList');
const datasetContent = document.getElementById('datasetContent');
const notebookContent = document.getElementById('notebookContent');
const viewSections = {
  history: document.getElementById('historyView'),
  dataset: document.getElementById('datasetView'),
  notebook: document.getElementById('notebookView')
};
const HISTORY_KEY = 'crm-ai-chat-history-v1';
let conversations = loadConversations();
let activeConversation = createConversation();
let chartCounter = 0;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[char]);
}

function loadConversations() {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(saved) ? saved.filter((item) => item && item.id && Array.isArray(item.messages)) : [];
  } catch (error) {
    console.error('Unable to load saved chat history:', error);
    return [];
  }
}

function saveConversations() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(conversations));
  } catch (error) {
    console.error('Unable to save chat history:', error);
    addMessage('ai', '<p>This conversation could not be saved in this browser. Check available browser storage.</p>');
  }
}

function createConversation() {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: 'New chat',
    updatedAt: new Date().toISOString(),
    messages: []
  };
}

function renderSuggestedQuestions(questions) {
  suggestionChips.innerHTML = '';
  questions.forEach((question) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip';
    btn.textContent = question;
    btn.addEventListener('click', () => sendQuestion(question));
    suggestionChips.appendChild(btn);
  });
}

function setDbSummary(data) {
  const tables = data.tables || [];
  const totalRows = tables.reduce((sum, table) => sum + (table.row_count || 0), 0);
  dbSummary.innerHTML = `
    <div class="stat-row"><span>Tables</span><strong>${tables.length}</strong></div>
    <div class="stat-row"><span>Rows</span><strong>${totalRows}</strong></div>
    <div class="stat-row"><span>Status</span><strong>Live</strong></div>
  `;
}

function addMessage(role, html, hasChart = false) {
  const row = document.createElement('div');
  row.className = `msg-row ${role}`;
  const bubble = document.createElement('div');
  bubble.className = hasChart ? 'msg-bubble wide-bubble' : 'msg-bubble';
  bubble.innerHTML = html;
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addLoading() {
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = `
    <div class="loading-indicator">
      <span>Analyzing</span>
      <span class="dot"></span>
      <span class="dot"></span>
      <span class="dot"></span>
    </div>
  `;
  row.appendChild(bubble);
  chatMessages.appendChild(row);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return row;
}

function renderTable(table) {
  if (!table || !table.columns || table.columns.length === 0) return '';

  const headers = table.columns.map((column) => `<th>${escapeHtml(column)}</th>`).join('');
  const rows = (table.rows || []).map((row) => {
    const cells = table.columns.map((column) => `<td>${escapeHtml(row[column])}</td>`).join('');
    return `<tr>${cells}</tr>`;
  }).join('');

  return `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>${headers}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderChart(chart) {
  if (!chart || !chart.type || !window.Plotly) return '';

  const id = `chart-${Date.now()}-${chartCounter++}`;
  const isHorizontal = chart.type === 'horizontalBar';
  const trace = {
    type: chart.type === 'pie' ? 'pie' : chart.type === 'line' || chart.type === 'scatter' ? 'scatter' : 'bar',
    x: isHorizontal ? (chart.y_values || []) : (chart.x_values || []),
    y: isHorizontal ? (chart.x_values || []) : (chart.y_values || []),
    mode: chart.type === 'line' ? 'lines+markers' : 'markers',
    orientation: chart.type === 'horizontalBar' ? 'h' : undefined,
    textposition: 'auto',
    marker: { color: '#7c9cff' }
  };

  if (chart.type === 'pie') {
    trace.labels = chart.x_values || [];
    trace.values = chart.y_values || [];
    trace.textinfo = 'percent+label';
    delete trace.x;
    delete trace.y;
  }

  const layout = {
    title: chart.title || 'Data overview',
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e7ecff' },
    margin: { l: 70, r: 24, t: 60, b: 90 },
    xaxis: {
      title: isHorizontal ? (chart.y_key || '') : (chart.x_key || ''),
      automargin: true,
      tickangle: chart.type === 'bar' ? -20 : 0
    },
    yaxis: { title: isHorizontal ? (chart.x_key || '') : (chart.y_key || ''), automargin: true }
  };

  setTimeout(() => {
    const chartElement = document.getElementById(id);
    if (chartElement) {
      Plotly.newPlot(id, [trace], layout, { responsive: true, displayModeBar: false });
    }
  }, 0);
  const height = isHorizontal
    ? Math.min(760, Math.max(400, 280 + (chart.x_values || []).length * 20))
    : 400;
  return `<div id="${id}" class="chart-box" style="height:${height}px; min-height:${height}px; width:100%;"></div>`;
}

function renderAssistantResult(result) {
  if (!result.success) {
    addMessage('ai', `<p>${escapeHtml(result.message || result.answer || 'Unable to process your question.')}</p>`);
    return;
  }
  const chartHtml = renderChart(result.chart);
  const tableHtml = renderTable(result.table);
  addMessage('ai', `
    <div>
      <h3>Answer</h3>
      <p>${escapeHtml(result.answer || '').replace(/\n/g, '<br>')}</p>
      ${chartHtml}
      ${tableHtml}
    </div>
  `, Boolean(result.chart));
}

function renderConversation(conversation) {
  chatMessages.innerHTML = '';
  if (!conversation || conversation.messages.length === 0) {
    addMessage('ai', '<p>Hi! Ask me about customers, products, orders, leads, or employee performance.</p>');
    return;
  }

  conversation.messages.forEach((message) => {
    if (message.role === 'user') {
      addMessage('user', `<p>${escapeHtml(message.text)}</p>`);
    } else if (message.role === 'assistant') {
      renderAssistantResult(message.result);
    }
  });
}

function persistActiveConversation() {
  if (!activeConversation.messages.length) return;
  activeConversation.updatedAt = new Date().toISOString();
  const index = conversations.findIndex((conversation) => conversation.id === activeConversation.id);
  if (index >= 0) {
    conversations[index] = activeConversation;
  } else {
    conversations.push(activeConversation);
  }
  conversations.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
  saveConversations();
  renderHistory();
}

function renderHistory() {
  if (!conversations.length) {
    historyList.innerHTML = '<div class="empty-state">No saved chats yet. Ask a question to create your first conversation.</div>';
    return;
  }

  historyList.innerHTML = '';
  conversations.forEach((conversation) => {
    const item = document.createElement('article');
    item.className = 'history-item';
    const openButton = document.createElement('button');
    openButton.type = 'button';
    openButton.className = 'history-open';
    const date = new Date(conversation.updatedAt);
    openButton.innerHTML = `
      <strong>${escapeHtml(conversation.title || 'CRM question')}</strong>
      <span>${conversation.messages.length} question(s) · ${escapeHtml(date.toLocaleString())}</span>
    `;
    openButton.addEventListener('click', () => {
      activeConversation = conversation;
      renderConversation(activeConversation);
      showView('chat');
    });

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'delete-history-btn';
    deleteButton.textContent = 'Delete';
    deleteButton.setAttribute('aria-label', `Delete chat: ${conversation.title}`);
    deleteButton.addEventListener('click', () => {
      conversations = conversations.filter((saved) => saved.id !== conversation.id);
      if (activeConversation.id === conversation.id) activeConversation = createConversation();
      saveConversations();
      renderHistory();
    });
    item.append(openButton, deleteButton);
    historyList.appendChild(item);
  });
}

function showView(viewName) {
  document.querySelectorAll('.nav-btn[data-view]').forEach((button) => {
    button.classList.toggle('active', button.dataset.view === viewName);
  });
  document.querySelector('.welcome-card').hidden = viewName !== 'chat';
  document.querySelector('.chat-panel').hidden = viewName !== 'chat';
  Object.entries(viewSections).forEach(([name, section]) => {
    section.hidden = name !== viewName;
  });

  const titles = {
    chat: 'CRM AI Analytics',
    history: 'Chat History',
    dataset: 'Dataset Information',
    notebook: 'Notebook Insights'
  };
  document.querySelector('.topbar h1').textContent = titles[viewName] || titles.chat;
  if (viewName === 'history') renderHistory();
  if (viewName === 'dataset') loadDatasetInfo();
  if (viewName === 'notebook') loadNotebookInsights();
}

function startNewChat() {
  activeConversation = createConversation();
  renderConversation(activeConversation);
  input.value = '';
  showView('chat');
  input.focus();
}

async function loadDatasetInfo() {
  const container = datasetContent;
  container.innerHTML = '<p class="muted">Loading database tables and columns…</p>';
  try {
    const response = await fetch('/api/dataset');
    if (!response.ok) throw new Error(`Dataset request failed (${response.status}).`);
    const data = await response.json();
    document.getElementById('datasetName').textContent = `${data.database_name} · ${data.summary.total_tables} tables`;
    const cards = (data.tables || []).map((table) => {
      const columns = table.columns.map((column) => `
        <tr>
          <td>${escapeHtml(column.name)}</td>
          <td>${escapeHtml(column.type)}</td>
          <td>${column.nullable ? 'Yes' : 'No'}</td>
          <td>${column.null_count}</td>
        </tr>
      `).join('');
      return `
        <article class="dataset-table-card">
          <div class="dataset-table-heading">
            <h3>${escapeHtml(table.table_name)}</h3>
            <span>${table.row_count} records</span>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Column</th><th>Type</th><th>Nullable</th><th>Missing</th></tr></thead>
              <tbody>${columns}</tbody>
            </table>
          </div>
        </article>
      `;
    }).join('');
    const relations = (data.relationships || []).map((relation) => `
      <li><code>${escapeHtml(relation.from_table)}.${escapeHtml(relation.from_column)}</code>
      → <code>${escapeHtml(relation.to_table)}.${escapeHtml(relation.to_column)}</code></li>
    `).join('');
    container.innerHTML = `
      <div class="dataset-summary">
        <div class="dataset-stat"><span>Tables</span><strong>${data.summary.total_tables}</strong></div>
        <div class="dataset-stat"><span>Total records across tables</span><strong>${data.summary.total_rows}</strong></div>
        <div class="dataset-stat"><span>Database</span><strong>${escapeHtml(data.database_name)}</strong></div>
      </div>
      <div class="dataset-grid">${cards}</div>
      <article class="dataset-table-card relationship-card">
        <h3>Table relationships</h3>
        ${relations ? `<ul>${relations}</ul>` : '<p class="muted">No foreign-key relationships found.</p>'}
      </article>
    `;
  } catch (error) {
    container.innerHTML = `<div class="empty-state error-state">${escapeHtml(error.message)}</div>`;
  }
}

async function loadNotebookInsights() {
  notebookContent.innerHTML = '<p class="muted">Loading notebook analysis…</p>';
  try {
    const response = await fetch('/api/notebook-insights');
    if (!response.ok) throw new Error(`Notebook insights request failed (${response.status}).`);
    const data = await response.json();
    const workflow = data.workflow.map((step, index) => `
      <li><span class="step-number">${index + 1}</span><span>${escapeHtml(step)}</span></li>
    `).join('');
    const areas = data.analysis_areas.map((area) => `
      <article class="insight-card">
        <h3>${escapeHtml(area.title)}</h3>
        <p>${escapeHtml(area.detail)}</p>
      </article>
    `).join('');
    const limitations = data.limitations.map((limitation) => `<li>${escapeHtml(limitation)}</li>`).join('');
    notebookContent.innerHTML = `
      <article class="notebook-intro">
        <h3>${escapeHtml(data.notebook_name)}</h3>
        <p>${escapeHtml(data.purpose)}</p>
      </article>
      <section class="notebook-section">
        <h3>Notebook workflow</h3>
        <ol class="workflow-list">${workflow}</ol>
      </section>
      <section class="notebook-section">
        <h3>Implemented analysis examples</h3>
        <div class="insight-grid">${areas}</div>
      </section>
      <section class="notebook-section">
        <h3>What to keep in mind</h3>
        <ul class="limitation-list">${limitations}</ul>
      </section>
    `;
  } catch (error) {
    notebookContent.innerHTML = `<div class="empty-state error-state">${escapeHtml(error.message)}</div>`;
  }
}

async function sendQuestion(questionOverride) {
  const question = (questionOverride || input.value || '').trim();
  if (!question) return;

  const userMessage = { role: 'user', text: question };
  activeConversation.messages.push(userMessage);
  if (activeConversation.messages.filter((message) => message.role === 'user').length === 1) {
    activeConversation.title = question;
  }
  addMessage('user', `<p>${escapeHtml(question)}</p>`);
  input.value = '';
  const loading = addLoading();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    const data = await response.json();
    loading.remove();
    const result = response.ok
      ? data
      : { success: false, message: data.detail || `The request failed (${response.status}).` };
    activeConversation.messages.push({ role: 'assistant', result });
    renderAssistantResult(result);
    persistActiveConversation();
  } catch (error) {
    loading.remove();
    const result = { success: false, message: 'Something went wrong while fetching the answer. Please try again.' };
    activeConversation.messages.push({ role: 'assistant', result });
    renderAssistantResult(result);
    persistActiveConversation();
  }
}

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendQuestion();
  }
});

sendBtn.addEventListener('click', () => sendQuestion());
clearBtn.addEventListener('click', startNewChat);
document.getElementById('newChatBtn').addEventListener('click', startNewChat);
document.querySelectorAll('.nav-btn[data-view]').forEach((button) => {
  button.addEventListener('click', () => {
    if (button.dataset.view === 'chat') {
      if (activeConversation.messages.length) startNewChat();
      else showView('chat');
      return;
    }
    showView(button.dataset.view);
  });
});

fetch('/api/sample-questions')
  .then((response) => {
    if (!response.ok) throw new Error(`Suggested questions request failed (${response.status}).`);
    return response.json();
  })
  .then((data) => renderSuggestedQuestions(data.questions || []))
  .catch((error) => console.error('Unable to load suggested questions:', error));

fetch('/api/dataset')
  .then((response) => {
    if (!response.ok) throw new Error(`Dataset request failed (${response.status}).`);
    return response.json();
  })
  .then(setDbSummary)
  .catch((error) => {
    console.error('Unable to load database summary:', error);
    dbSummary.innerHTML = '<div class="stat-row"><span>Status</span><strong>Unavailable</strong></div>';
  });

renderConversation(activeConversation);
