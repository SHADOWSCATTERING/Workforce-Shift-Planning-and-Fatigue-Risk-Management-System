document.addEventListener('DOMContentLoaded', () => {
    // Mobile Navigation Toggle
    const mobileToggle = document.querySelector('.mobile-toggle');
    const navLinks = document.querySelector('.nav-links');

    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            
            // Animate hamburger to X
            const spans = mobileToggle.querySelectorAll('span');
            if (navLinks.classList.contains('active')) {
                spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
                spans[1].style.opacity = '0';
                spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
            } else {
                spans[0].style.transform = 'none';
                spans[1].style.opacity = '1';
                spans[2].style.transform = 'none';
            }
        });
    }

    // Smooth Scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            
            // Close mobile menu if open
            if (navLinks && navLinks.classList.contains('active')) {
                mobileToggle.click();
            }

            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Intersection Observer for fade-in animations on scroll
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Apply basic fade up to sections
    document.querySelectorAll('section:not(.hero) .container').forEach(section => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(30px)';
        section.style.transition = 'opacity 0.8s ease-out, transform 0.8s ease-out';
        observer.observe(section);
    });

    // Interactive Risk Assessment Card Simulation
    const riskCard = document.getElementById('dynamic-risk-card');
    const statusText = riskCard.querySelector('.status-indicator');
    
    let isDanger = false;
    
    riskCard.addEventListener('mouseenter', () => {
        if (!isDanger) {
            riskCard.classList.add('danger');
            statusText.textContent = 'Violations Detected!';
            statusText.style.color = 'var(--accent-red)';
            isDanger = true;
        } else {
            riskCard.classList.remove('danger');
            statusText.textContent = 'Shift Compliant';
            statusText.style.color = 'var(--accent-green)';
            isDanger = false;
        }
    });

    // ---------------------------------------------------------
    // Interactive Dashboard API Integration
    // ---------------------------------------------------------

    // 1. Detect API endpoint base
    const API_BASE = window.location.protocol === 'file:' 
        ? 'http://localhost:5000' 
        : '';

    // 2. Global State
    let employeesData = [];
    let selectedEmpId = null;

    // 3. Select DOM Elements
    const dbStatusDot = document.getElementById('db-status-dot');
    const dbStatusText = document.getElementById('db-status-text');
    const aiStatusDot = document.getElementById('ai-status-dot');
    const aiStatusText = document.getElementById('ai-status-text');
    const btnSeedDb = document.getElementById('btn-seed-db');

    const employeeSearchInput = document.getElementById('employee-search');
    const employeeListContainer = document.getElementById('employee-list-container');

    const panelEmptyState = document.getElementById('panel-empty-state');
    const panelDetailsContent = document.getElementById('panel-details-content');

    const detailEmpName = document.getElementById('detail-emp-name');
    const detailEmpMeta = document.getElementById('detail-emp-meta');
    const detailEmpRiskBadge = document.getElementById('detail-emp-risk-badge');
    const detailEmpScore = document.getElementById('detail-emp-score');
    const detailEmpScoreBar = document.getElementById('detail-emp-score-bar');

    const detailEmpContractHours = document.getElementById('detail-emp-contract-hours');
    const detailEmpMaxHours = document.getElementById('detail-emp-max-hours');
    const detailEmpRest = document.getElementById('detail-emp-rest');

    const violationsContainer = document.getElementById('violations-container');
    const detailViolationsList = document.getElementById('detail-violations-list');

    const detailAiSource = document.getElementById('detail-ai-source');
    const detailAiExplanation = document.getElementById('detail-ai-explanation');
    const detailAiUrgent = document.getElementById('detail-ai-urgent');
    const detailAiRecommendation = document.getElementById('detail-ai-recommendation');
    const groupAiUrgent = document.getElementById('group-ai-urgent');
    const groupAiRec = document.getElementById('group-ai-rec');

    const detailRosterBody = document.getElementById('detail-roster-body');

    const shiftAssignmentForm = document.getElementById('shift-assignment-form');
    const btnValidateShift = document.getElementById('btn-validate-shift');
    const btnAssignShift = document.getElementById('btn-assign-shift');

    const valResultsBox = document.getElementById('validation-results-box');
    const valRiskBadge = document.getElementById('val-risk-badge');
    const valSummaryText = document.getElementById('val-summary-text');
    const valViolationsBox = document.getElementById('val-violations-box');
    const valViolationsList = document.getElementById('val-violations-list');
    const valAiSource = document.getElementById('val-ai-source');
    const valAiExplanation = document.getElementById('val-ai-explanation');
    const valAiAlternativesGroup = document.getElementById('val-ai-alternatives-group');
    const valAiAlternatives = document.getElementById('val-ai-alternatives');

    // Tab buttons handling
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const targetTab = btn.getAttribute('data-tab');
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.add('hidden');
            });
            document.getElementById(targetTab).classList.remove('hidden');
        });
    });

    // 4. API Core Functions
    async function checkHealth() {
        try {
            const res = await fetch(`${API_BASE}/api/health`);
            if (!res.ok) throw new Error("API unhealthy");
            const data = await res.json();
            
            // Render Database status
            if (data.database_initialized) {
                dbStatusDot.className = 'status-dot active';
                dbStatusText.textContent = 'Initialized (Seeded)';
                btnSeedDb.textContent = 'Reset & Reseed';
                btnSeedDb.className = 'btn btn-secondary btn-sm';
            } else {
                dbStatusDot.className = 'status-dot inactive';
                dbStatusText.textContent = 'Missing Database';
                btnSeedDb.textContent = 'Setup Database';
                btnSeedDb.className = 'btn btn-primary btn-sm';
            }

            // Render AI status
            if (data.ai_configured) {
                aiStatusDot.className = 'status-dot active';
                aiStatusText.textContent = 'Claude AI Connected';
            } else {
                aiStatusDot.className = 'status-dot warning';
                aiStatusText.textContent = 'Template Fallback (No Key)';
            }
            return data.database_initialized;
        } catch (err) {
            console.error(err);
            dbStatusDot.className = 'status-dot inactive';
            dbStatusText.textContent = 'Offline (Failed to connect)';
            aiStatusDot.className = 'status-dot inactive';
            aiStatusText.textContent = 'Offline';
            return false;
        }
    }

    async function loadEmployees() {
        try {
            const res = await fetch(`${API_BASE}/api/employees`);
            if (!res.ok) throw new Error("Could not load employees");
            employeesData = await res.json();
            
            // Get dashboard stats if database is initialized
            const dashboardRes = await fetch(`${API_BASE}/api/dashboard/risk-summary`);
            let riskSummary = {};
            if (dashboardRes.ok) {
                riskSummary = await dashboardRes.json();
            }

            renderEmployeeList(riskSummary.employee_risks || []);
        } catch (err) {
            console.error(err);
            employeeListContainer.innerHTML = `
                <div style="text-align: center; color: var(--accent-red); padding: 2rem 0;">
                    <p>Failed to load employees.</p>
                    <button class="btn btn-secondary btn-sm" id="btn-retry-employees" style="margin-top: 10px; padding: 0.4rem 1rem;">Retry</button>
                </div>
            `;
            const btnRetry = document.getElementById('btn-retry-employees');
            if (btnRetry) btnRetry.addEventListener('click', () => {
                checkHealth().then(initialized => {
                    if (initialized) loadEmployees();
                });
            });
        }
    }

    function renderEmployeeList(riskList = []) {
        // Map risk details by employee_id for quick search
        const riskMap = {};
        riskList.forEach(item => {
            riskMap[item.employee_id] = item;
        });

        // Filter text
        const query = employeeSearchInput.value.toLowerCase().trim();

        const filtered = employeesData.filter(emp => {
            return emp.name.toLowerCase().includes(query) || 
                   (emp.role && emp.role.toLowerCase().includes(query)) ||
                   emp.employee_id.toLowerCase().includes(query);
        });

        if (filtered.length === 0) {
            employeeListContainer.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 2rem 0;">No employees found.</div>`;
            return;
        }

        employeeListContainer.innerHTML = '';
        filtered.forEach(emp => {
            const item = document.createElement('div');
            item.className = `employee-item ${emp.employee_id === selectedEmpId ? 'selected' : ''}`;
            
            const riskInfo = riskMap[emp.employee_id] || { risk_level: 'Low', fatigue_score: 0 };
            const riskClass = riskInfo.risk_level.toLowerCase();

            item.innerHTML = `
                <div class="emp-info">
                    <h4>${emp.name}</h4>
                    <p>${emp.role || 'Employee'} | ${emp.department || 'Staff'}</p>
                </div>
                <span class="risk-badge ${riskClass}">${riskInfo.risk_level} (${Math.round(riskInfo.fatigue_score)})</span>
            `;

            item.addEventListener('click', () => {
                document.querySelectorAll('.employee-item').forEach(el => el.classList.remove('selected'));
                item.classList.add('selected');
                selectEmployee(emp.employee_id);
            });

            employeeListContainer.appendChild(item);
        });
    }

    async function selectEmployee(empId) {
        selectedEmpId = empId;
        
        // Show loading state
        panelEmptyState.classList.add('hidden');
        panelDetailsContent.classList.add('hidden');
        
        // Create or find a loader
        let loader = document.getElementById('details-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'details-loader';
            loader.style.textAlign = 'center';
            loader.style.padding = '5rem 0';
            loader.innerHTML = `<div class="loading-spinner">Analyzing fatigue risk profile...</div>`;
            panelDetailsContent.parentNode.appendChild(loader);
        }
        loader.classList.remove('hidden');

        try {
            // Fetch fatigue risk detail
            const riskRes = await fetch(`${API_BASE}/api/employees/${empId}/fatigue-risk`);
            if (!riskRes.ok) throw new Error("Failed to load fatigue risk");
            const riskData = await riskRes.json();

            // Fetch schedule
            const scheduleRes = await fetch(`${API_BASE}/api/employees/${empId}/schedule`);
            if (!scheduleRes.ok) throw new Error("Failed to load employee schedule");
            const scheduleData = await scheduleRes.json();

            loader.classList.add('hidden');
            panelDetailsContent.classList.remove('hidden');

            renderEmployeeDetails(riskData, scheduleData);
        } catch (err) {
            console.error(err);
            loader.classList.add('hidden');
            panelEmptyState.classList.remove('hidden');
            alert("Error loading employee fatigue data. Please try again.");
        }
    }

    function renderEmployeeDetails(riskData, scheduleData) {
        const emp = scheduleData.employee;
        const shifts = scheduleData.shifts;

        // Render header
        detailEmpName.textContent = emp.name;
        detailEmpMeta.textContent = `${emp.role || 'Employee'} | ${emp.department || 'Staff'}`;
        
        const riskLevel = riskData.risk_level;
        const riskClass = riskLevel.toLowerCase();
        detailEmpRiskBadge.textContent = `${riskLevel} Risk`;
        detailEmpRiskBadge.className = `risk-badge ${riskClass}`;

        // Render fatigue score meter
        const score = Math.round(riskData.fatigue_score);
        detailEmpScore.textContent = `${score} / 100`;
        detailEmpScoreBar.className = `score-bar ${riskClass}`;
        detailEmpScoreBar.style.width = `${score}%`;

        // Render contract stats
        detailEmpContractHours.textContent = `${emp.contracted_hours}h`;
        detailEmpMaxHours.textContent = `${emp.max_weekly_hours}h`;
        detailEmpRest.textContent = `${emp.min_rest_hours_required}h`;

        // Render violations
        const violations = riskData.violations || [];
        if (violations.length === 0) {
            violationsContainer.classList.add('hidden');
            detailViolationsList.innerHTML = '';
        } else {
            violationsContainer.classList.remove('hidden');
            detailViolationsList.innerHTML = '';
            violations.forEach(v => {
                const card = document.createElement('div');
                card.className = `violation-item ${v.severity.toLowerCase()}`;
                card.innerHTML = `
                    <div>
                        <span class="violation-lbl">${v.rule_name}</span>
                        <div class="violation-desc">${v.detail}</div>
                    </div>
                    <span class="risk-badge ${v.severity.toLowerCase()}">${v.severity}</span>
                `;
                detailViolationsList.appendChild(card);
            });
        }

        // Render AI explanation box
        const ai = riskData.ai_explanation || {};
        if (ai.source === 'ai') {
            detailAiSource.textContent = 'Anthropic Claude';
            detailAiSource.className = 'ai-source-badge ai';
        } else {
            detailAiSource.textContent = 'Rule Explainer (Fallback)';
            detailAiSource.className = 'ai-source-badge';
        }

        detailAiExplanation.textContent = ai.explanation || 'No explanation available.';
        
        if (ai.most_urgent_issue && ai.most_urgent_issue !== 'None detected.') {
            groupAiUrgent.classList.remove('hidden');
            detailAiUrgent.textContent = ai.most_urgent_issue;
        } else {
            groupAiUrgent.classList.add('hidden');
        }

        if (ai.recommendation) {
            groupAiRec.classList.remove('hidden');
            detailAiRecommendation.textContent = ai.recommendation;
        } else {
            groupAiRec.classList.add('hidden');
        }

        // Render Roster table
        if (shifts.length === 0) {
            detailRosterBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-secondary);">No shifts scheduled in this window.</td></tr>`;
        } else {
            detailRosterBody.innerHTML = '';
            // Sort shifts chronologically
            shifts.forEach(s => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>${s.shift_date}</strong></td>
                    <td><span class="risk-badge ${s.shift_type.toLowerCase() === 'night' ? 'critical' : 'medium'}" style="text-transform: capitalize;">${s.shift_type}</span></td>
                    <td>${s.start_time} - ${s.end_time}</td>
                    <td>${s.location || '—'} <span style="color: var(--text-secondary); font-size: 0.8rem; display: block;">${s.department || ''}</span></td>
                `;
                detailRosterBody.appendChild(row);
            });
        }

        // Reset forms and result views
        shiftAssignmentForm.reset();
        valResultsBox.classList.add('hidden');
    }

    // 5. Shift Validation & Assignment Actions
    async function validateShift(e) {
        if (!selectedEmpId) return;
        
        const dateVal = document.getElementById('shift-date').value;
        const typeVal = document.getElementById('shift-type').value;
        const startVal = document.getElementById('start-time').value;
        const endVal = document.getElementById('end-time').value;
        const locVal = document.getElementById('location').value;
        const deptVal = document.getElementById('department').value;

        if (!dateVal || !typeVal || !startVal || !endVal) {
            alert("Please fill out Shift Date, Shift Type, Start Time, and End Time.");
            return;
        }

        btnValidateShift.disabled = true;
        btnValidateShift.textContent = 'Checking...';

        try {
            const res = await fetch(`${API_BASE}/api/shifts/validate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    employee_id: selectedEmpId,
                    shift_date: dateVal,
                    shift_type: typeVal,
                    start_time: startVal,
                    end_time: endVal,
                    location: locVal,
                    department: deptVal
                })
            });

            const data = await res.json();
            btnValidateShift.disabled = false;
            btnValidateShift.textContent = 'Dry-Run Check';

            if (!res.ok) {
                alert(`Validation failed: ${data.error || 'Unknown error'}`);
                return;
            }

            // Render validation results box
            valResultsBox.classList.remove('hidden');
            
            const projectedRisk = data.projected_risk_level;
            const projectedClass = projectedRisk.toLowerCase();
            valRiskBadge.textContent = `${projectedRisk} Projected`;
            valRiskBadge.className = `risk-badge ${projectedClass}`;

            if (data.safe_to_assign) {
                valSummaryText.innerHTML = `🟢 This shift is <strong style="color: var(--accent-green);">safe to assign</strong>. It does not introduce any fatigue risk violations.`;
                valViolationsBox.classList.add('hidden');
            } else {
                valSummaryText.innerHTML = `⚠️ This shift is <strong style="color: var(--accent-red);">not recommended</strong>. It introduces new safety violations.`;
                valViolationsBox.classList.remove('hidden');
                
                valViolationsList.innerHTML = '';
                const newViolations = data.would_introduce_violations || [];
                newViolations.forEach(v => {
                    const li = document.createElement('li');
                    li.innerHTML = `<strong>${v.rule_name}</strong>: ${v.detail}`;
                    valViolationsList.appendChild(li);
                });
            }

            // AI explanation of projected risk
            const ai = data.ai_explanation || {};
            if (ai.source === 'ai') {
                valAiSource.textContent = 'Anthropic Claude';
                valAiSource.className = 'ai-source-badge ai';
            } else {
                valAiSource.textContent = 'Rule Explainer (Fallback)';
                valAiSource.className = 'ai-source-badge';
            }
            valAiExplanation.textContent = ai.explanation || 'No explanation available.';

            // Render Alternatives
            const alts = data.safer_alternatives || [];
            if (alts.length === 0) {
                valAiAlternativesGroup.classList.add('hidden');
            } else {
                valAiAlternativesGroup.classList.remove('hidden');
                valAiAlternatives.innerHTML = '';
                alts.forEach(alt => {
                    const card = document.createElement('div');
                    card.className = 'alt-card';
                    card.innerHTML = `
                        <div class="alt-header">
                            <span>💡 ${alt.option}</span>
                            <span class="risk-badge ${alt.projected_risk_level.toLowerCase()}" style="font-size: 0.65rem; padding: 0.1rem 0.5rem;">${alt.projected_risk_level} Risk</span>
                        </div>
                        <div class="alt-desc">
                            Shift: ${alt.shift_date} ${alt.start_time}-${alt.end_time} (${alt.shift_type}). Reason: ${alt.reason}
                        </div>
                    `;
                    valAiAlternatives.appendChild(card);
                });
            }

            // Scroll results box into view
            valResultsBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        } catch (err) {
            console.error(err);
            btnValidateShift.disabled = false;
            btnValidateShift.textContent = 'Dry-Run Check';
            alert("Connection error occurred. Could not validate shift.");
        }
    }

    async function assignShift(e) {
        e.preventDefault();
        if (!selectedEmpId) return;

        const dateVal = document.getElementById('shift-date').value;
        const typeVal = document.getElementById('shift-type').value;
        const startVal = document.getElementById('start-time').value;
        const endVal = document.getElementById('end-time').value;
        const locVal = document.getElementById('location').value;
        const deptVal = document.getElementById('department').value;

        // Generate unique shift id (random string for capstone purposes)
        const shiftId = 'S' + Math.floor(Math.random() * 1000000);

        btnAssignShift.disabled = true;
        btnAssignShift.textContent = 'Assigning...';

        try {
            const res = await fetch(`${API_BASE}/api/shifts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    shift_id: shiftId,
                    employee_id: selectedEmpId,
                    shift_date: dateVal,
                    shift_type: typeVal,
                    start_time: startVal,
                    end_time: endVal,
                    location: locVal,
                    department: deptVal
                })
            });

            const data = await res.json();
            btnAssignShift.disabled = false;
            btnAssignShift.textContent = 'Assign Shift';

            if (res.status === 409) {
                // Hard conflict overlap
                const confirmForce = confirm(
                    `⚠️ Assignment Blocked: This shift overlaps with another shift for this employee.\n\n` +
                    `AI Explanation:\n"${data.ai_explanation?.explanation || data.error}"\n\n` +
                    `Do you want to override and assign anyway? (Not recommended)`
                );
                
                if (confirmForce) {
                    // Re-send with force: true
                    await forceAssignShift(shiftId, dateVal, typeVal, startVal, endVal, locVal, deptVal);
                }
                return;
            }

            if (!res.ok) {
                alert(`Failed to assign shift: ${data.error || 'Unknown error'}`);
                return;
            }

            // Success
            let successMsg = `🟢 Shift assigned successfully!`;
            if (data.fatigue_warnings && data.fatigue_warnings.length > 0) {
                successMsg += `\n⚠️ Note: This introduces Soft Fatigue warnings (Projected: ${data.projected_risk_level} Risk).`;
            }
            alert(successMsg);

            // Reload employee list & details
            const initialized = await checkHealth();
            if (initialized) {
                await loadEmployees();
                await selectEmployee(selectedEmpId);
            }

        } catch (err) {
            console.error(err);
            btnAssignShift.disabled = false;
            btnAssignShift.textContent = 'Assign Shift';
            alert("Connection error occurred. Could not assign shift.");
        }
    }

    async function forceAssignShift(shiftId, dateVal, typeVal, startVal, endVal, locVal, deptVal) {
        btnAssignShift.disabled = true;
        btnAssignShift.textContent = 'Overriding...';

        try {
            const res = await fetch(`${API_BASE}/api/shifts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    shift_id: shiftId,
                    employee_id: selectedEmpId,
                    shift_date: dateVal,
                    shift_type: typeVal,
                    start_time: startVal,
                    end_time: endVal,
                    location: locVal,
                    department: deptVal,
                    force: true
                })
            });

            const data = await res.json();
            btnAssignShift.disabled = false;
            btnAssignShift.textContent = 'Assign Shift';

            if (!res.ok) {
                alert(`Force assignment failed: ${data.error || 'Unknown error'}`);
                return;
            }

            alert(`🟢 Shift assigned successfully via override!`);

            // Reload employee list & details
            const initialized = await checkHealth();
            if (initialized) {
                await loadEmployees();
                await selectEmployee(selectedEmpId);
            }
        } catch (err) {
            console.error(err);
            btnAssignShift.disabled = false;
            btnAssignShift.textContent = 'Assign Shift';
            alert("Connection error occurred during override.");
        }
    }

    // 6. DB Administration Actions (Seed/Reset)
    async function seedDatabase() {
        const confirmMsg = dbStatusText.textContent.includes('Missing')
            ? "This will initialize the database schema and load starter rosters. Proceed?"
            : "⚠️ Warning: This will delete all current schedules and restore the database to its starter seeding state. Proceed?";
        
        if (!confirm(confirmMsg)) return;

        btnSeedDb.disabled = true;
        btnSeedDb.textContent = 'Seeding...';

        try {
            const res = await fetch(`${API_BASE}/api/admin/seed`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reset: true })
            });

            const data = await res.json();
            btnSeedDb.disabled = false;

            if (!res.ok) {
                alert(`Failed to seed database: ${data.error || 'Unknown error'}`);
                return;
            }

            alert("🟢 Database initialized and seeded successfully!");
            
            // Reload app state
            const initialized = await checkHealth();
            if (initialized) {
                await loadEmployees();
                // Deselect current employee since roster reset
                selectedEmpId = null;
                panelDetailsContent.classList.add('hidden');
                panelEmptyState.classList.remove('hidden');
            }

        } catch (err) {
            console.error(err);
            btnSeedDb.disabled = false;
            btnSeedDb.textContent = 'Seed/Reset Data';
            alert("Connection error occurred. Could not seed database.");
        }
    }

    // 7. Event Listeners
    employeeSearchInput.addEventListener('keyup', () => {
        renderEmployeeList();
    });

    btnSeedDb.addEventListener('click', seedDatabase);
    btnValidateShift.addEventListener('click', validateShift);
    shiftAssignmentForm.addEventListener('submit', assignShift);

    // 8. Auto Startup
    checkHealth().then(initialized => {
        if (initialized) {
            loadEmployees();
        } else {
            // DB is missing, prompt to setup database in the employee list container
            employeeListContainer.innerHTML = `
                <div style="text-align: center; color: var(--text-secondary); padding: 2rem 0;">
                    <p style="margin-bottom: 15px;">Database not initialized.</p>
                    <button class="btn btn-primary btn-sm" id="btn-init-prompt">Initialize Database</button>
                </div>
            `;
            const btnInitPrompt = document.getElementById('btn-init-prompt');
            if (btnInitPrompt) {
                btnInitPrompt.addEventListener('click', seedDatabase);
            }
        }
    });
});
