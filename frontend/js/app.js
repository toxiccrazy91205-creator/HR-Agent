/* ==========================================
   Antigravity HR Front-End Controller
   Vanilla JS Client-Side Logic
   ========================================== */

// Set this to your absolute backend URL in production (e.g. 'https://hr-backend.onrender.com')
// If left empty, it defaults to the relative path '/api' (same domain)
const BACKEND_URL = ''; 
const API_BASE = BACKEND_URL ? `${BACKEND_URL}/api` : '/api';
let activeSessionId = 'session_' + Math.floor(Math.random() * 1000000);
let pollingInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    // Initialize UI Component hooks
    initApp();
});

function initApp() {
    // Fetch initial Dashboard State
    fetchJobRoles();
    fetchCandidates();
    fetchInterviews();

    // Set up form submission handlers
    setupChatForm();
    setupJobModal();
    setupDropzone();
    setupRefreshButtons();
    setupQuickTags();
}

// ==========================================
// API FETCH OPERATIONS
// ==========================================

async function fetchJobRoles() {
    try {
        const response = await fetch(`${API_BASE}/job-roles/`);
        if (response.ok) {
            const jobs = await response.json();
            renderJobRoles(jobs);
            populateJobSelect(jobs);
        }
    } catch (e) {
        console.error("Error fetching job roles:", e);
    }
}

async function fetchCandidates() {
    try {
        const response = await fetch(`${API_BASE}/candidates/`);
        if (response.ok) {
            const candidates = await response.json();
            renderCandidates(candidates);
            
            // Auto pool if any candidate is still parsing (score is null)
            const hasUnfinished = candidates.some(c => c.score === null);
            if (hasUnfinished && !pollingInterval) {
                startCandidatePolling();
            } else if (!hasUnfinished && pollingInterval) {
                stopCandidatePolling();
            }
        }
    } catch (e) {
        console.error("Error fetching candidates:", e);
    }
}

async function fetchInterviews() {
    try {
        const response = await fetch(`${API_BASE}/interviews/`);
        if (response.ok) {
            const interviews = await response.json();
            renderInterviews(interviews);
        }
    } catch (e) {
        console.error("Error fetching interviews:", e);
    }
}

// Polling mechanism for parsing candidates
function startCandidatePolling() {
    console.log("Start polling for unfinished candidate parsing...");
    pollingInterval = setInterval(() => {
        fetchCandidates();
        fetchInterviews();
    }, 4000);
}

function stopCandidatePolling() {
    console.log("Stopping candidate polling.");
    clearInterval(pollingInterval);
    pollingInterval = null;
}

// ==========================================
// RENDER METHODS
// ==========================================

function renderJobRoles(jobs) {
    const list = document.getElementById('job-list');
    if (!jobs || jobs.length === 0) {
        list.innerHTML = '<div class="empty-state">No job roles defined yet.</div>';
        return;
    }

    list.innerHTML = jobs.map((job, idx) => `
        <div class="job-item ${idx === 0 ? 'active' : ''}" data-id="${job.id}">
            <h4>${escapeHTML(job.title)}</h4>
            <p>${escapeHTML(job.description)}</p>
        </div>
    `).join('');
    
    // Add click listeners to job items
    document.querySelectorAll('.job-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.job-item').forEach(j => j.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function populateJobSelect(jobs) {
    const select = document.getElementById('upload-job-select');
    select.innerHTML = '<option value="">Select a role...</option>' + 
        jobs.map(job => `<option value="${job.id}">${escapeHTML(job.title)}</option>`).join('');
}

function renderCandidates(candidates) {
    const list = document.getElementById('candidate-list');
    if (!candidates || candidates.length === 0) {
        list.innerHTML = '<div class="empty-state">No candidates uploaded yet.</div>';
        return;
    }

    list.innerHTML = candidates.map(cand => {
        const score = cand.score !== null ? cand.score : "...";
        const scoreClass = cand.score === null ? "" : (cand.score >= 75 ? "high" : (cand.score < 50 ? "low" : ""));
        const skills = cand.extracted_skills || [];
        const skillsMarkup = skills.slice(0, 4).map(s => `<span class="skill-tag">${escapeHTML(s)}</span>`).join('');
        const statusClass = cand.status.toLowerCase().replace(' ', '_');

        return `
            <div class="cand-card" data-id="${cand.id}">
                <div class="cand-header">
                    <div class="cand-name-title">
                        <h4>${escapeHTML(cand.name || "Parsing...")}</h4>
                        <span>${escapeHTML(cand.email || "Processing info")}</span>
                    </div>
                    <div class="score-pill ${scoreClass}">${score}</div>
                </div>
                <div class="cand-skills">
                    ${skillsMarkup || '<span style="font-size:9px;color:#888;">No skills extracted</span>'}
                </div>
                <div class="cand-footer">
                    <span class="status-badge ${statusClass}">${escapeHTML(cand.status)}</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderInterviews(interviews) {
    const list = document.getElementById('interview-list');
    if (!interviews || interviews.length === 0) {
        list.innerHTML = '<div class="empty-state">No interviews scheduled yet.</div>';
        return;
    }

    list.innerHTML = interviews.map(inter => {
        const dateStr = new Date(inter.scheduled_time).toLocaleString([], {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
        const meetLink = inter.meeting_link ? `<a href="${inter.meeting_link}" target="_blank" class="meet-link-btn"><i class="fa-solid fa-video"></i> Google Meet</a>` : '';

        return `
            <div class="interview-item">
                <h4>${escapeHTML(inter.candidate_name)}</h4>
                <p><i class="fa-regular fa-clock"></i> ${dateStr} - Status: <strong>${escapeHTML(inter.status)}</strong></p>
                ${meetLink}
            </div>
        `;
    }).join('');
}

// ==========================================
// RESUME INGESTION UPLOAD FLOW
// ==========================================

function setupDropzone() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const jobSelect = document.getElementById('upload-job-select');

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFilesUpload(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFilesUpload(fileInput.files);
        }
    });
}

async function handleFilesUpload(files) {
    const jobSelect = document.getElementById('upload-job-select');
    const jobRoleId = jobSelect.value;

    if (!jobRoleId) {
        alert("Please select a target position before uploading resumes.");
        return;
    }

    const formData = new FormData();
    formData.append('job_role_id', jobRoleId);
    
    let validCount = 0;
    for (let i = 0; i < files.length; i++) {
        if (files[i].name.toLowerCase().endsWith('.pdf')) {
            formData.append('resumes', files[i]);
            validCount++;
        }
    }

    if (validCount === 0) {
        alert("Please select valid PDF documents only.");
        return;
    }

    // Show upload progress simulation
    const statusBox = document.getElementById('upload-status');
    const progressFill = document.getElementById('upload-progress');
    const statusText = document.getElementById('upload-text');

    statusBox.style.display = 'flex';
    progressFill.style.width = '20%';
    statusText.innerText = `Ingesting ${validCount} files...`;

    try {
        const response = await fetch(`${API_BASE}/upload-resume/`, {
            method: 'POST',
            body: formData
        });
        
        progressFill.style.width = '80%';

        if (response.ok) {
            const data = await response.json();
            progressFill.style.width = '100%';
            statusText.innerText = "Upload complete! Processing...";
            
            // Reload side panel DB
            fetchCandidates();
            
            setTimeout(() => {
                statusBox.style.display = 'none';
            }, 3000);
        } else {
            const err = await response.json();
            statusText.innerText = `Upload Failed: ${err.error || 'Server error'}`;
        }
    } catch (e) {
        console.error("Error uploading files:", e);
        statusText.innerText = "Connection error. Failed.";
    }
}

// ==========================================
// CHAT AGENT FORM FLOW
// ==========================================

function setupChatForm() {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;

        sendMessage(text);
        input.value = '';
    });
}

async function sendMessage(text) {
    const chatMessages = document.getElementById('chat-messages');
    
    // 1. Render User Message
    const userMsgDiv = document.createElement('div');
    userMsgDiv.className = 'message user-message';
    userMsgDiv.innerHTML = `<div class="message-content"><p>${escapeHTML(text)}</p></div>`;
    chatMessages.appendChild(userMsgDiv);
    scrollChat();

    // 2. Show Typing / Thinking Status Panel
    const logBox = document.getElementById('agent-logs');
    const logActionText = document.getElementById('log-current-action');
    const logSteps = document.getElementById('log-steps');

    logBox.style.display = 'block';
    logActionText.innerText = "Orchestrator deciding intent...";
    logSteps.innerHTML = '<div><i class="fa-solid fa-microchip"></i> Analyzing prompt criteria...</div>';
    scrollChat();

    try {
        const response = await fetch(`${API_BASE}/chat/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, session_id: activeSessionId })
        });

        if (response.ok) {
            const data = await response.json();
            
            // Render logs step-by-step
            if (data.logs && data.logs.length > 0) {
                logSteps.innerHTML = '';
                for (let i = 0; i < data.logs.length; i++) {
                    await delay(500); // add a micro-delay for realistic system feedback!
                    logActionText.innerText = data.logs[i];
                    logSteps.innerHTML += `<div><i class="fa-solid fa-check text-success"></i> ${escapeHTML(data.logs[i])}</div>`;
                }
            }

            await delay(400);
            logBox.style.display = 'none';

            // 3. Render Assistant Response Bubble
            const assistantMsgDiv = document.createElement('div');
            assistantMsgDiv.className = 'message assistant-message';
            assistantMsgDiv.innerHTML = `<div class="message-content">${parseMarkdown(data.response)}</div>`;
            chatMessages.appendChild(assistantMsgDiv);
            
            // Refresh dashboard states as they may have updated during actions
            fetchCandidates();
            fetchInterviews();
        } else {
            logBox.style.display = 'none';
            const assistantMsgDiv = document.createElement('div');
            assistantMsgDiv.className = 'message assistant-message';
            assistantMsgDiv.innerHTML = `<div class="message-content"><p style="color:#ff5252;">Failed to get response from AI. Please check server logs.</p></div>`;
            chatMessages.appendChild(assistantMsgDiv);
        }
    } catch (e) {
        console.error("Chat error:", e);
        logBox.style.display = 'none';
        const assistantMsgDiv = document.createElement('div');
        assistantMsgDiv.className = 'message assistant-message';
        assistantMsgDiv.innerHTML = `<div class="message-content"><p style="color:#ff5252;">Network error connecting to orchestrator.</p></div>`;
        chatMessages.appendChild(assistantMsgDiv);
    }
    
    scrollChat();
}

function scrollChat() {
    const area = document.getElementById('chat-messages');
    area.scrollTop = area.scrollHeight;
}

// Helper delay
const delay = ms => new Promise(res => setTimeout(res, ms));

// ==========================================
// JOB ROLE MODAL LOGIC
// ==========================================

function setupJobModal() {
    const addBtn = document.getElementById('add-job-btn');
    const modal = document.getElementById('job-modal');
    const closeBtn = document.getElementById('close-modal-btn');
    const cancelBtn = document.getElementById('cancel-job-btn');
    const form = document.getElementById('job-form');

    const showModal = () => modal.style.display = 'flex';
    const hideModal = () => {
        modal.style.display = 'none';
        form.reset();
    };

    addBtn.addEventListener('click', showModal);
    closeBtn.addEventListener('click', hideModal);
    cancelBtn.addEventListener('click', hideModal);

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = document.getElementById('job-title').value;
        const description = document.getElementById('job-desc').value;
        const skillsString = document.getElementById('job-skills').value;
        
        // Convert comma-separated string to list
        const required_skills = skillsString.split(',').map(s => s.trim()).filter(s => s.length > 0);

        try {
            const response = await fetch(`${API_BASE}/job-roles/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, description, required_skills })
            });

            if (response.ok) {
                hideModal();
                fetchJobRoles();
            } else {
                alert("Failed to save job role.");
            }
        } catch (e) {
            console.error("Error saving job role:", e);
        }
    });
}

// ==========================================
// SYSTEM REFRESH & TRIGGERS
// ==========================================

function setupRefreshButtons() {
    document.getElementById('refresh-candidates-btn').addEventListener('click', () => {
        fetchCandidates();
    });

    document.getElementById('clear-chat-btn').addEventListener('click', () => {
        if (confirm("Are you sure you want to clear the conversational panel log?")) {
            document.getElementById('chat-messages').innerHTML = `
                <div class="message assistant-message welcome-msg">
                    <div class="message-content">
                        <h3>Welcome to Antigravity HR! ⚡</h3>
                        <p>Conversation history has been cleared. Let me know how I can assist you now.</p>
                    </div>
                </div>
            `;
            activeSessionId = 'session_' + Math.floor(Math.random() * 1000000);
        }
    });
}

function setupQuickTags() {
    document.querySelectorAll('.tag-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const query = btn.getAttribute('data-query');
            sendMessage(query);
        });
    });
}

// ==========================================
// UTILITY HELPERS
// ==========================================

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}

function parseMarkdown(text) {
    if (!text) return '';
    
    // Escape HTML first to prevent injection inside Markdown parse
    let html = escapeHTML(text);

    // Header 3
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    // Header 4
    html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    // Code blocks / pills
    html = html.replace(/`(.*?)`/gim, '<code style="background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;font-family:monospace;font-size:12px;">$1</code>');
    
    // Bullet points (matches lines starting with '-' or '*')
    html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li>$1</li>');
    
    // Group bullet elements in unordered lists
    // This is a simple regex grouping replace
    html = html.replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>');
    // Clean up duplicate overlapping ul tags
    html = html.replace(/<\/ul>\s*<ul>/gim, '');

    // Convert newlines to paragraphs/breaks where appropriate
    html = html.split('\n\n').map(p => {
        if (p.trim().startsWith('<h') || p.trim().startsWith('<ul') || p.trim().startsWith('<li')) {
            return p;
        }
        return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return html;
}
