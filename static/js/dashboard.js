document.addEventListener("DOMContentLoaded", () => {
    const studentSelect = document.getElementById("studentSelect");
    const loadingIndicator = document.getElementById("loadingIndicator");
    const errorBanner = document.getElementById("errorBanner");
    const linkedStudentBadge = document.getElementById("linkedStudentBadge");
    const topbarStatusBadge = document.getElementById("topbarStatusBadge");
    const urlParams = new URLSearchParams(window.location.search);
    let currentStudentId = urlParams.get("student_id") || "STU-0004";
    let overviewChartInstance = null;

    init();

    async function init() {
        if (studentSelect) {
            studentSelect.addEventListener("change", () => {
                if (studentSelect.value && studentSelect.value !== currentStudentId) {
                    currentStudentId = studentSelect.value;
                    updateStudentLinks();
                    window.history.pushState({}, "", `${window.location.pathname}?student_id=${encodeURIComponent(currentStudentId)}`);
                    loadStudentDashboard(currentStudentId);
                }
            });
        }
        window.addEventListener("popstate", () => {
            const sid = new URLSearchParams(window.location.search).get("student_id") || "STU-0004";
            if (sid !== currentStudentId) {
                currentStudentId = sid;
                updateStudentLinks();
                loadStudentDashboard(sid);
            }
        });
        updateStudentLinks();
        await loadStudentsList();
        await loadStudentDashboard(currentStudentId);
    }

    function updateStudentLinks() {
        document.querySelectorAll(".sidebar-nav a.nav-item, .section-nav-link").forEach(link => {
            const href = link.getAttribute("href");
            if (!href || href.startsWith("#") || href.includes("/logout") || href.includes("/login")) return;
            const url = new URL(href, window.location.origin);
            url.searchParams.set("student_id", currentStudentId);
            link.setAttribute("href", url.pathname + url.search);
        });
        if (studentSelect) studentSelect.value = currentStudentId;
        if (linkedStudentBadge) linkedStudentBadge.textContent = currentStudentId;
    }

    async function loadStudentsList() {
        try {
            const response = await fetch("/api/students");
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (studentSelect) {
                studentSelect.innerHTML = "";
                (data.students || []).forEach(sid => {
                    const option = document.createElement("option");
                    option.value = sid;
                    option.textContent = sid;
                    option.selected = sid === currentStudentId;
                    studentSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error("Failed to load students list:", error);
            showError("Could not retrieve students list from the server.");
        }
    }

    async function loadStudentDashboard(studentId) {
        showLoading(true);
        hideError();
        currentStudentId = studentId;
        updateStudentLinks();
        try {
            const response = await fetch(`/api/student/${encodeURIComponent(studentId)}`);
            if (!response.ok) {
                throw new Error(response.status === 404
                    ? `Student ID '${studentId}' was not found.`
                    : `Server returned status HTTP ${response.status}`);
            }
            renderDashboard(await response.json());
        } catch (error) {
            console.error("Dashboard load error:", error);
            showError(`Error loading student data: ${error.message}`);
        } finally {
            showLoading(false);
        }
    }

    function renderDashboard(data) {
        const profile = data.profile || {};
        const progression = profile.weekly_progression || [];
        renderAIStatus(data.prediction || {});
        renderOverviewKPIs(profile);
        renderParentProgressSummary(profile);
        renderParentSuggestions(profile, data.prediction || {});
        if (document.getElementById("overviewTrendChart")) {
            overviewChartInstance = renderProgressChart("overviewTrendChart", progression, overviewChartInstance);
        }
    }

    function renderAIStatus(prediction) {
        const level = prediction.predicted_difficulty || "Low";
        const status = statusDetails(level);
        if (topbarStatusBadge) {
            topbarStatusBadge.className = `status-tag ${status.className}`;
            topbarStatusBadge.textContent = status.label;
        }
        const card = document.getElementById("statusCard");
        if (card) {
            card.classList.remove("status-low", "status-moderate", "status-high");
            card.classList.add(status.cardClass);
        }
        const badge = document.getElementById("statusBadge");
        if (badge) {
            badge.className = `status-tag ${status.className}`;
            badge.textContent = status.label;
        }
        const description = document.getElementById("statusDesc");
        if (description) description.textContent = status.description;
    }

    function statusDetails(level) {
        if (level === "High") return { label: "Needs Support", className: "danger", cardClass: "status-high", description: "Current indicators suggest additional support may help. Consider checking in with your child and their teacher." };
        if (level === "Moderate") return { label: "Needs Attention", className: "warning", cardClass: "status-moderate", description: "Some results may need attention. Talk with your child about what feels challenging and agree on one helpful next step." };
        return { label: "On Track", className: "success", cardClass: "status-low", description: "Current indicators suggest your child is on track. Keep encouraging regular attendance and steady learning habits." };
    }

    function getMetrics(profile) {
        return {
            academic: profile.academic_metrics || {},
            engagement: profile.engagement_metrics || {}
        };
    }

    function overallScore(academic) {
        const scores = [
            Number(academic.average_quiz_score),
            Number(academic.average_assignment_score),
            Number(academic.average_internal_assessment_score)
        ];
        return scores.every(Number.isFinite)
            ? (scores.reduce((total, score) => total + score, 0) / scores.length).toFixed(1)
            : "--";
    }

    function renderOverviewKPIs(profile) {
        const { academic, engagement } = getMetrics(profile);
        setText("kpiOverallScore", formatPercentage(overallScore(academic)));
        setText("kpiAttendance", formatPercentage(engagement.average_attendance_percentage));
        setText("kpiQuiz", formatPercentage(academic.average_quiz_score));
        setText("kpiAssignment", formatPercentage(academic.average_assignment_score));
        setText("kpiIA", formatPercentage(academic.average_internal_assessment_score));
        renderAttendanceContext(engagement.average_attendance_percentage);
    }

    function formatPercentage(value) {
        if (value === null || value === undefined || value === "") return "—";
        const score = Number(value);
        return Number.isFinite(score) ? `${score.toFixed(1)}%` : "—";
    }

    function renderAttendanceContext(value) {
        const note = document.getElementById("kpiAttendanceNote");
        if (!note) return;
        const attendance = value === null || value === undefined || value === ""
            ? NaN
            : Number(value);
        if (!Number.isFinite(attendance)) {
            note.className = "parent-kpi-context";
            note.textContent = "Recorded attendance is unavailable";
            return;
        }
        if (attendance >= 90) {
            note.className = "parent-kpi-context success";
            note.textContent = "Regular attendance";
        } else if (attendance >= 75) {
            note.className = "parent-kpi-context warning";
            note.textContent = "Worth monitoring";
        } else {
            note.className = "parent-kpi-context danger";
            note.textContent = "Needs attention";
        }
    }

    function renderParentProgressSummary(profile) {
        const summary = document.getElementById("parentProgressSummary");
        if (!summary) return;
        const { academic, engagement } = getMetrics(profile);
        const overall = Number(overallScore(academic));
        const attendance = engagement.average_attendance_percentage === null
            || engagement.average_attendance_percentage === undefined
            || engagement.average_attendance_percentage === ""
            ? NaN
            : Number(engagement.average_attendance_percentage);
        const trend = getWeeklyAssessmentTrend(profile.weekly_progression || []);
        const details = [];
        if (Number.isFinite(overall)) {
            details.push(`The current overall assessment average is ${overall.toFixed(1)}%.`);
        }
        if (Number.isFinite(attendance)) {
            details.push(`Recorded overall attendance is ${attendance.toFixed(1)}%.`);
        }
        if (trend) details.unshift(trend);
        summary.textContent = details.length
            ? details.join(" ")
            : "Academic progress details will appear when student records are available.";
    }

    function getWeeklyAssessmentTrend(progression) {
        const weeklyScores = progression.map(item => {
            const scores = [item.quiz, item.assignment, item.internal_assessment].map(Number);
            return scores.every(Number.isFinite)
                ? scores.reduce((total, score) => total + score, 0) / scores.length
                : null;
        }).filter(Number.isFinite);
        if (weeklyScores.length < 2) return null;
        const change = weeklyScores[weeklyScores.length - 1] - weeklyScores[0];
        if (change > 2) return "Weekly assessment results have trended upward.";
        if (change < -2) return "Weekly assessment results have dipped; a supportive check-in may help.";
        return "Weekly assessment results have stayed broadly steady.";
    }

    function renderParentSuggestions(profile, prediction) {
        const list = document.getElementById("parentSupportSuggestions");
        if (!list) return;
        const { academic, engagement } = getMetrics(profile);
        const lowestAssessment = [
            ["quiz", Number(academic.average_quiz_score)],
            ["assignment", Number(academic.average_assignment_score)],
            ["internal assessment", Number(academic.average_internal_assessment_score)]
        ].filter(([, score]) => Number.isFinite(score)).sort((left, right) => left[1] - right[1])[0];
        const suggestions = [
            Number(engagement.average_attendance_percentage) < 90
                ? "Ask whether anything is making regular attendance difficult, and plan for upcoming classes together."
                : "Keep encouraging your child's regular attendance routine.",
            lowestAssessment
                ? lowestAssessment[0] === "quiz"
                    ? "Review a few quiz questions together and talk through any challenging answers."
                    : lowestAssessment[0] === "assignment"
                        ? "Ask about feedback on the latest assignment and help plan time for upcoming work."
                        : "Ask which internal-assessment topics feel difficult and review the feedback together."
                : "Check in about current classwork and ask where support would be useful.",
            prediction.predicted_difficulty === "High"
                ? "Consider checking in with the teacher about what additional support would help."
                : prediction.predicted_difficulty === "Moderate"
                    ? "Have a calm check-in about what feels challenging and agree on one small next step."
                    : "Notice and acknowledge the effort behind your child's progress."
        ];
        list.replaceChildren();
        suggestions.forEach((suggestion, index) => {
            const item = document.createElement("li");
            item.className = "parent-suggestion-item";
            const number = document.createElement("span");
            number.className = "suggestion-icon";
            number.setAttribute("aria-hidden", "true");
            number.textContent = String(index + 1);
            const text = document.createElement("span");
            text.className = "suggestion-text";
            text.textContent = suggestion;
            item.append(number, text);
            list.appendChild(item);
        });
    }

    function renderProgressChart(canvasId, progression, existingChart) {
        const canvas = document.getElementById(canvasId);
        const emptyState = document.getElementById("overviewTrendEmpty");
        if (!canvas) return existingChart;
        if (existingChart) existingChart.destroy();
        if (!progression.length) {
            canvas.hidden = true;
            if (emptyState) {
                emptyState.textContent = "A weekly progress chart will appear when enough weekly records are available.";
                emptyState.hidden = false;
            }
            return null;
        }
        if (!window.Chart) {
            canvas.hidden = true;
            if (emptyState) {
                emptyState.textContent = "The progress chart could not be loaded. The latest results are still shown above.";
                emptyState.hidden = false;
            }
            return null;
        }
        canvas.hidden = false;
        if (emptyState) emptyState.hidden = true;
        const labels = progression.map(item => `Week ${item.week}`);
        const average = progression.map(item => {
            const scores = [item.quiz, item.assignment, item.internal_assessment].map(chartPercentage);
            return scores.every(value => value !== null)
                ? scores.reduce((total, score) => total + score, 0) / scores.length
                : null;
        });
        const attendance = progression.map(item => chartPercentage(item.attendance));
        if (![...average, ...attendance].some(Number.isFinite)) {
            canvas.hidden = true;
            if (emptyState) {
                emptyState.textContent = "Weekly progress is unavailable because the recorded values are incomplete.";
                emptyState.hidden = false;
            }
            return null;
        }

        const colors = window.AcademicChartTheme.colors;
        return new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Assessment average",
                        data: average,
                        borderColor: colors.overall,
                        backgroundColor: "rgba(249, 115, 22, 0.1)",
                        borderWidth: 2.5,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        tension: 0.3,
                        fill: true,
                        spanGaps: false
                    },
                    {
                        label: "Recorded attendance",
                        data: attendance,
                        borderColor: colors.attendance,
                        backgroundColor: "rgba(14, 165, 233, 0.05)",
                        borderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        borderDash: [4, 4],
                        tension: 0.3,
                        spanGaps: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { position: "bottom", labels: { usePointStyle: true, padding: 16 } },
                    tooltip: {
                        callbacks: {
                            label: context => `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxRotation: 0, minRotation: 0, maxTicksLimit: 6 },
                        title: { display: true, text: "Observed week" }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        ticks: {
                            stepSize: 20,
                            callback: value => `${value}%`
                        },
                        title: { display: true, text: "Percentage" },
                        grid: { color: "rgba(148, 163, 184, 0.12)" }
                    }
                }
            }
        });
    }

    function chartPercentage(value) {
        if (value === null || value === undefined || value === "") return null;
        const percentage = Number(value);
        return Number.isFinite(percentage) && percentage >= 0 && percentage <= 100
            ? percentage
            : null;
    }

    function showLoading(loading) {
        if (loadingIndicator) loadingIndicator.style.display = loading ? "inline-flex" : "none";
    }

    function showError(message) {
        if (errorBanner) {
            errorBanner.textContent = message;
            errorBanner.style.display = "block";
        }
        document.querySelectorAll(".status-tag").forEach(element => {
            if (/loading/i.test(element.textContent)) element.textContent = "Unavailable";
        });
        document.querySelectorAll(".kpi-value").forEach(element => {
            if (element.textContent.includes("--")) element.textContent = "—";
        });
    }

    function hideError() {
        if (errorBanner) errorBanner.style.display = "none";
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

});
