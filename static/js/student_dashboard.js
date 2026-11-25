document.addEventListener("DOMContentLoaded", () => {
    const studentSelect = document.getElementById("studentSelect");
    const loadingIndicator = document.getElementById("loadingIndicator");
    const errorBanner = document.getElementById("errorBanner");
    const linkedStudentBadge = document.getElementById("linkedStudentBadge");
    const topbarStatusBadge = document.getElementById("topbarStatusBadge");
    const urlParams = new URLSearchParams(window.location.search);
    let currentStudentId = urlParams.get("student_id") || "STU-0004";
    let detailedChartInstance = null;
    let subjectChartInstance = null;
    let studyPlanState = {
        studentId: null,
        tasks: [],
        completions: {},
        weekStart: null
    };
    const ASSESSMENT_WEAKNESS_GAP = 3;
    const ASSESSMENT_IMPROVEMENT_THRESHOLD = 70;
    const LOW_ASSESSMENT_THRESHOLD = 65;

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
            link.setAttribute("href", url.pathname + url.search + url.hash);
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
            console.error("Student dashboard load error:", error);
            showError(`Error loading student data: ${error.message}`);
        } finally {
            showLoading(false);
        }
    }

    function renderDashboard(data) {
        const profile = data.profile || {};
        const progression = profile.weekly_progression || [];
        const subjects = data.subject_performance || [];
        renderAIStatus(data.prediction || {});
        renderPerformanceKPIs(profile);
        renderStudentSummary(profile);
        if (document.getElementById("studentAcademicSummaryText")) {
            renderPersonalAcademicSummary(profile, subjects);
        }
        if (document.getElementById("subjectAttendanceList")) {
            renderSubjectAttendance(subjects);
        }
        if (document.getElementById("subjectFocusList")) {
            renderSubjectFocus(subjects);
        }
        if (document.getElementById("assessmentWeaknessList")) {
            renderAssessmentWeaknesses(subjects);
        }
        if (document.getElementById("studentStudyTipsList")) {
            if (document.getElementById("recommendationWeeklyStudyPlan")) {
                initializeRecommendations(
                    currentStudentId,
                    profile,
                    subjects,
                    data.recommendations || {}
                );
            } else {
                renderStudySuggestions(profile, subjects);
            }
        }
        if (document.getElementById("studentDetailedChart")) {
            detailedChartInstance = renderProgressChart("studentDetailedChart", progression, detailedChartInstance);
        }
        if (document.getElementById("studentSubjectChart")) {
            subjectChartInstance = renderSubjectPerformance(
                subjects,
                subjectChartInstance
            );
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
        const confidence = document.getElementById("confidenceValue");
        const confidenceValue = Number(prediction.confidence_percentage);
        const confidenceText = Number.isFinite(confidenceValue)
            ? `${confidenceValue.toFixed(1)}%`
            : "--%";
        if (confidence) confidence.textContent = confidenceText;
        const insightBadge = document.getElementById("studentInsightsStatusBadge");
        if (insightBadge) {
            insightBadge.className = `status-tag ${status.className}`;
            insightBadge.textContent = status.label;
        }
        const insightMeaning = document.getElementById("studentInsightsMeaning");
        if (insightMeaning) insightMeaning.textContent = status.description;
        const insightConfidence = document.getElementById("studentInsightsConfidence");
        if (insightConfidence) insightConfidence.textContent = confidenceText;
        const probabilities = prediction.probabilities || {};
        setProbability("Low", probabilities.Low);
        setProbability("Moderate", probabilities.Moderate);
        setProbability("High", probabilities.High);
    }

    function statusDetails(level) {
        if (level === "High") return { label: "At Risk", className: "danger", cardClass: "status-high", description: "Your recent indicators suggest it may help to get timely academic support. This is a signal to check your results, not a judgment about your ability." };
        if (level === "Moderate") return { label: "Needs Attention", className: "warning", cardClass: "status-moderate", description: "Your results show a few areas worth keeping an eye on. Small, steady changes can help you stay on track." };
        return { label: "On Track", className: "success", cardClass: "status-low", description: "Your current indicators are on track. Keep up your steady effort and review feedback as you go." };
    }

    function setProbability(level, value) {
        const probability = Number(value);
        const percent = Number.isFinite(probability)
            ? Math.max(0, Math.min(100, probability * 100))
            : 0;
        const bar = document.getElementById(`prob${level}`)
            || document.getElementById(`bar${level}`);
        const label = document.getElementById(`prob${level}Text`)
            || document.getElementById(`val${level}`);
        if (bar) bar.style.width = `${percent}%`;
        if (bar) bar.setAttribute("aria-valuenow", percent.toFixed(1));
        if (label) label.textContent = `${percent.toFixed(1)}%`;
    }

    function getMetrics(profile) {
        return {
            academic: profile.academic_metrics || {},
            engagement: profile.engagement_metrics || {}
        };
    }

    function overallScore(academic) {
        const scores = [
            toNumericScore(academic.average_quiz_score),
            toNumericScore(academic.average_assignment_score),
            toNumericScore(academic.average_internal_assessment_score)
        ];
        return scores.every(Number.isFinite)
            ? (scores.reduce((total, score) => total + score, 0) / scores.length).toFixed(1)
            : "--";
    }

    function renderPerformanceKPIs(profile) {
        const { academic, engagement } = getMetrics(profile);
        setText("perfOverallScore", overallScore(academic));
        setText("perfAttendance", `${engagement.average_attendance_percentage ?? "--"}%`);
        setText("perfQuiz", academic.average_quiz_score ?? "--");
        setText("perfAssignment", academic.average_assignment_score ?? "--");
        setText("perfIA", academic.average_internal_assessment_score ?? "--");
    }

    function renderPersonalAcademicSummary(profile, subjects) {
        const summary = document.getElementById("studentAcademicSummaryText");
        const signals = document.getElementById("academicSummarySignals");
        if (!summary || !signals) return;
        signals.replaceChildren();

        const { academic, engagement } = getMetrics(profile);
        const overall = Number(overallScore(academic));
        const validSubjects = subjects.filter(subject =>
            Number.isFinite(toNumericScore(subject.average_score))
        );
        const overviewMessage = document.getElementById("studentOverviewMessage");
        if (!Number.isFinite(overall) || validSubjects.length === 0) {
            summary.textContent = "Your personalized academic summary will appear when overall and subject results are available.";
            if (overviewMessage) {
                overviewMessage.textContent = "Your academic highlights will appear when your results are available.";
            }
            return;
        }

        const overallStatus = subjectPerformanceStatus(overall);
        const strongest = validSubjects.reduce((best, subject) =>
            Number(subject.average_score) > Number(best.average_score) ? subject : best
        );
        const focusSubject = findMostAttentionSubject(validSubjects);
        const attendance = toNumericScore(engagement.average_attendance_percentage);
        const trend = getWeeklyAssessmentTrend(profile.weekly_progression || []);
        const summaryParts = [
            `Your overall performance is ${overallStatus.label.toLowerCase()} at ${overall.toFixed(1)}%.`,
            `Your strongest subject is ${strongest.subject} (${formatScore(strongest.average_score)}).`
        ];

        if (focusSubject) {
            summaryParts.push(
                `${focusSubject.subject} needs the most attention because ${getSubjectFocusReason(focusSubject)}.`
            );
        } else {
            summaryParts.push("No subject currently meets the dashboard's focus thresholds.");
        }

        if (Number.isFinite(attendance)) {
            const attendanceMessage = attendance >= 90
                ? `Your recorded overall attendance is strong at ${formatScore(attendance)}.`
                : attendance >= 75
                    ? `Your recorded overall attendance is ${formatScore(attendance)}; keep it consistent.`
                    : `Your recorded overall attendance is ${formatScore(attendance)}, below the 75% guide; prioritize attending upcoming classes.`;
            summaryParts.push(attendanceMessage);
        }
        if (trend) summaryParts.push(trend.summary);
        if (overviewMessage) {
            const overviewParts = [
                `Your overall performance is ${overall.toFixed(1)}% (${overallStatus.label.toLowerCase()}).`,
                `${strongest.subject} is currently your strongest subject at ${formatScore(strongest.average_score)}.`
            ];
            if (focusSubject) {
                overviewParts.push(`${focusSubject.subject} is the best place to focus next.`);
            }
            summary.textContent = overviewParts.join(" ");
            if (trend?.label === "Improving") {
                overviewMessage.textContent = "Your recent assessment results are moving up—keep using the study habits that are working.";
            } else if (trend?.label === "Declining") {
                overviewMessage.textContent = "A recent change in your weekly results is a chance to use feedback and choose one small area to practise.";
            } else if (focusSubject) {
                overviewMessage.textContent = `Small, regular practice in ${focusSubject.subject} can help you build confidence over time.`;
            } else {
                overviewMessage.textContent = "Keep building steady learning habits and use feedback to guide your next step.";
            }
        } else {
            summary.textContent = summaryParts.join(" ");
        }

        addSummarySignal(signals, "Overall", `${overallStatus.label} · ${overall.toFixed(1)}%`, overallStatus.className);
        addSummarySignal(signals, "Strongest", strongest.subject, "status-strong");
        if (focusSubject) {
            addSummarySignal(signals, "Focus", focusSubject.subject, "status-needs-improvement");
        }
        if (Number.isFinite(attendance)) {
            const attendanceClass = attendance >= 90
                ? "status-strong"
                : attendance >= 75 ? "status-good" : "status-needs-improvement";
            addSummarySignal(signals, "Overall attendance", formatScore(attendance), attendanceClass);
        }
        if (trend) addSummarySignal(signals, "Weekly trend", trend.label, trend.className);
    }

    function addSummarySignal(container, label, value, statusClass) {
        const signal = document.createElement("div");
        signal.className = "academic-summary-signal";
        const signalLabel = document.createElement("span");
        signalLabel.textContent = label;
        const signalValue = document.createElement("strong");
        signalValue.className = statusClass;
        signalValue.textContent = value;
        signal.append(signalLabel, signalValue);
        container.appendChild(signal);
    }

    function getWeeklyAssessmentTrend(progression) {
        const weeklyScores = progression.map(item => {
            const scores = [
                toNumericScore(item.quiz),
                toNumericScore(item.assignment),
                toNumericScore(item.internal_assessment)
            ];
            return scores.every(Number.isFinite)
                ? scores.reduce((total, score) => total + score, 0) / scores.length
                : null;
        }).filter(Number.isFinite);
        if (weeklyScores.length < 4) return null;

        const midpoint = Math.floor(weeklyScores.length / 2);
        const earlier = weeklyScores.slice(0, midpoint);
        const recent = weeklyScores.slice(midpoint);
        const average = values => values.reduce((total, value) => total + value, 0) / values.length;
        const difference = average(recent) - average(earlier);
        if (difference > 2) {
            return {
                label: "Improving",
                className: "status-strong",
                summary: `Your recent weekly assessment average is up ${difference.toFixed(1)} percentage points compared with the earlier observed weeks.`
            };
        }
        if (difference < -2) {
            return {
                label: "Declining",
                className: "status-needs-improvement",
                summary: `Your recent weekly assessment average is down ${Math.abs(difference).toFixed(1)} percentage points compared with the earlier observed weeks.`
            };
        }
        return {
            label: "Steady",
            className: "status-good",
            summary: "Your weekly assessment averages have remained broadly steady across the observed weeks."
        };
    }

    function findMostAttentionSubject(subjects) {
        return subjects
            .filter(isSubjectToFocus)
            .sort((left, right) => subjectFocusPriority(right) - subjectFocusPriority(left))[0] || null;
    }

    function subjectFocusPriority(subject) {
        const score = toNumericScore(subject.average_score);
        const attendance = toNumericScore(subject.attendance_percentage);
        const assessmentScores = [
            toNumericScore(subject.quiz_average),
            toNumericScore(subject.assignment_average),
            toNumericScore(subject.internal_assessment_average)
        ];
        return (Number.isFinite(score) ? Math.max(0, 70 - score) : 0)
            + (Number.isFinite(attendance) ? Math.max(0, 75 - attendance) : 0)
            + assessmentScores.reduce((total, value) =>
                total + (Number.isFinite(value) ? Math.max(0, LOW_ASSESSMENT_THRESHOLD - value) : 0), 0
            );
    }

    function getSubjectFocusReason(subject) {
        const reasons = [];
        const score = toNumericScore(subject.average_score);
        const attendance = toNumericScore(subject.attendance_percentage);
        if (Number.isFinite(score) && score < 70) {
            reasons.push({ gap: 70 - score, text: `its overall score is ${formatScore(score)}` });
        }
        if (Number.isFinite(attendance) && attendance < 75) {
            reasons.push({ gap: 75 - attendance, text: `its synthetic subject attendance is ${formatScore(attendance)}` });
        }
        [
            ["quiz", toNumericScore(subject.quiz_average)],
            ["assignment", toNumericScore(subject.assignment_average)],
            ["internal assessment", toNumericScore(subject.internal_assessment_average)]
        ].forEach(([label, value]) => {
            if (Number.isFinite(value) && value < LOW_ASSESSMENT_THRESHOLD) {
                reasons.push({ gap: LOW_ASSESSMENT_THRESHOLD - value, text: `its ${label} average is ${formatScore(value)}` });
            }
        });
        reasons.sort((left, right) => right.gap - left.gap);
        return reasons[0]?.text || `its current score is ${formatScore(subject.average_score)}`;
    }

    function renderStudentSummary(profile) {
        const { academic, engagement } = getMetrics(profile);
        const score = Number(overallScore(academic));
        const scoreText = Number.isFinite(score) ? score.toFixed(1) : "—";
        setText("studentOverallScore", `${scoreText}%`);
        setText("studentProgressText", Number.isFinite(score)
            ? `Your average across quizzes, assignments, and internal assessments is ${scoreText}%.`
            : "Your assessment progress is not available yet.");
        const progressTrack = document.getElementById("studentProgressTrack");
        const progressBar = document.getElementById("studentProgressBar");
        if (progressTrack) {
            const progressValue = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
            progressTrack.setAttribute("aria-valuenow", String(progressValue));
            if (progressBar) progressBar.style.width = `${progressValue}%`;
        }

        setText("studentWeeksObserved", profile.early_weeks_observed ?? profile.weekly_progression?.length ?? "—");
        setText("studentTotalLogins", engagement.total_lms_login_count ?? "—");
        setText("studentTotalResources", engagement.total_lms_resource_views ?? "—");
        setText("studentTotalPractice", engagement.total_practice_sessions ?? "—");

    }

    function renderStudySuggestions(profile, subjects) {
        const list = document.getElementById("studentStudyTipsList");
        if (!list) return;
        const { academic, engagement } = getMetrics(profile);
        const tips = [];
        const quiz = toNumericScore(academic.average_quiz_score);
        const assignment = toNumericScore(academic.average_assignment_score);
        const internalAssessment = toNumericScore(academic.average_internal_assessment_score);
        const attendance = toNumericScore(engagement.average_attendance_percentage);
        if (Number.isFinite(quiz) && quiz < 75) {
            tips.push(`Your quiz average is ${formatScore(quiz)}. Practise a short question set regularly and review the reasoning behind missed answers.`);
        }
        if (Number.isFinite(assignment) && assignment < 75) {
            tips.push(`Your assignment average is ${formatScore(assignment)}. Review feedback and divide the next assignment into smaller steps.`);
        }
        if (Number.isFinite(internalAssessment) && internalAssessment < 75) {
            tips.push(`Your internal assessment average is ${formatScore(internalAssessment)}. Revise class concepts and practise writing answers under a short time limit.`);
        }
        if (Number.isFinite(attendance) && attendance < 90) {
            tips.push(`Your overall attendance is ${formatScore(attendance)}. Prioritise attending upcoming classes and review materials from any sessions you missed.`);
        }
        const weakestSubject = subjects
            .filter(subject => Number.isFinite(toNumericScore(subject.average_score)))
            .sort((left, right) => toNumericScore(left.average_score) - toNumericScore(right.average_score))[0];
        if (weakestSubject && toNumericScore(weakestSubject.average_score) < 75) {
            tips.push(`${weakestSubject.subject} is currently your lowest-scoring subject at ${formatScore(weakestSubject.average_score)}. Schedule two short review sessions and practise questions from this subject.`);
        }
        if (tips.length === 0) {
            tips.push("Your current assessment scores and overall attendance do not indicate an urgent focus area. Keep a regular review routine and check feedback after each assessment.");
        }
        list.replaceChildren();
        tips.forEach(tip => {
            const item = document.createElement("li");
            item.textContent = tip;
            list.appendChild(item);
        });
        const emptyState = document.getElementById("smartTipsEmpty");
        if (emptyState) emptyState.hidden = tips.length > 0;
    }

    function renderProgressChart(canvasId, progression, existingChart) {
        const canvas = document.getElementById(canvasId);
        const emptyState = document.getElementById("studentProgressEmpty");
        if (!canvas) return existingChart;
        if (existingChart) existingChart.destroy();

        const showEmptyState = message => {
            canvas.hidden = true;
            if (emptyState) {
                emptyState.textContent = message;
                emptyState.hidden = false;
            }
        };
        if (!progression.length) {
            showEmptyState("Weekly progress will appear when recorded weekly assessment or attendance data is available.");
            return null;
        }
        if (!window.Chart) {
            showEmptyState("The weekly progress chart could not be loaded. Your other results remain available.");
            return null;
        }

        const labels = progression.map(item => `Week ${item.week}`);
        const average = progression.map(item => {
            const scores = [item.quiz, item.assignment, item.internal_assessment].map(chartPercentage);
            return scores.every(value => value !== null)
                ? scores.reduce((total, score) => total + score, 0) / scores.length
                : null;
        });
        const attendance = progression.map(item => chartPercentage(item.attendance));
        if (![...average, ...attendance].some(Number.isFinite)) {
            showEmptyState("Weekly progress is unavailable because the recorded values are incomplete.");
            return null;
        }

        canvas.hidden = false;
        if (emptyState) emptyState.hidden = true;
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
                    legend: { position: "bottom" },
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

    function renderSubjectPerformance(subjects, existingChart) {
        const canvas = document.getElementById("studentSubjectChart");
        const tableBody = document.getElementById("studentSubjectTableBody");
        const emptyState = document.getElementById("studentSubjectEmpty");
        const cards = document.getElementById("subjectPerformanceCards");
        const cardsEmptyState = document.getElementById("subjectPerformanceEmpty");
        const strongestCard = document.getElementById("strongestSubjectCard");
        const strongestEmptyState = document.getElementById("strongestSubjectEmpty");
        if (!canvas || !tableBody || !emptyState || !cards || !strongestCard) return existingChart;

        tableBody.replaceChildren();
        cards.replaceChildren();
        strongestCard.replaceChildren();
        if (existingChart) existingChart.destroy();

        if (subjects.length === 0) {
            canvas.hidden = true;
            tableBody.closest(".performance-section").hidden = true;
            emptyState.hidden = false;
            if (cardsEmptyState) cardsEmptyState.hidden = false;
            if (strongestEmptyState) strongestEmptyState.hidden = false;
            return null;
        }

        canvas.hidden = false;
        tableBody.closest(".performance-section").hidden = false;
        emptyState.hidden = true;
        if (cardsEmptyState) cardsEmptyState.hidden = true;
        if (strongestEmptyState) strongestEmptyState.hidden = true;

        subjects.forEach(subject => {
            const score = toNumericScore(subject.average_score);
            const attendance = toNumericScore(subject.attendance_percentage);
            const status = subjectPerformanceStatus(score);
            cards.appendChild(createSubjectPerformanceCard(subject, status, score, attendance));

            const row = document.createElement("tr");
            [
                subject.subject,
                subject.average_score,
                subject.attendance_percentage,
                subject.quiz_average,
                subject.assignment_average,
                subject.internal_assessment_average
            ].forEach((value, index) => {
                const cell = document.createElement("td");
                cell.textContent = index === 0 ? value : formatScore(value);
                if (index === 0) cell.className = "performance-table-subject";
                row.appendChild(cell);
            });
            tableBody.appendChild(row);
        });

        const strongest = subjects.reduce((best, subject) =>
            Number(subject.average_score) > Number(best.average_score) ? subject : best
        );
        if (strongestEmptyState) strongestEmptyState.hidden = true;
        strongestCard.appendChild(createStrongestSubjectCard(strongest));

        if (!window.Chart) {
            canvas.hidden = true;
            emptyState.textContent = "The subject comparison chart could not be loaded. Subject scores remain available in the summary and table.";
            emptyState.hidden = false;
            return null;
        }
        const colors = window.AcademicChartTheme.colors;
        const chartSubjects = [...subjects].sort((left, right) => {
            const leftScore = chartPercentage(left.average_score);
            const rightScore = chartPercentage(right.average_score);
            if (leftScore === null) return 1;
            if (rightScore === null) return -1;
            return leftScore - rightScore;
        });
        return new Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: chartSubjects.map(subject => wrapSubjectLabel(subject.subject)),
                datasets: [
                    {
                        label: "Overall score",
                        data: chartSubjects.map(subject => chartPercentage(subject.average_score)),
                        backgroundColor: colors.overall,
                        borderRadius: 3,
                        maxBarThickness: 13
                    },
                    {
                        label: "Quiz average",
                        data: chartSubjects.map(subject => chartPercentage(subject.quiz_average)),
                        backgroundColor: colors.quiz,
                        borderRadius: 3,
                        maxBarThickness: 13
                    },
                    {
                        label: "Assignment average",
                        data: chartSubjects.map(subject => chartPercentage(subject.assignment_average)),
                        backgroundColor: colors.assignment,
                        borderRadius: 3,
                        maxBarThickness: 13
                    },
                    {
                        label: "Internal assessment",
                        data: chartSubjects.map(subject => chartPercentage(subject.internal_assessment_average)),
                        backgroundColor: colors.internalAssessment,
                        borderRadius: 3,
                        maxBarThickness: 13
                    },
                    {
                        label: "Synthetic attendance*",
                        data: chartSubjects.map(subject => chartPercentage(subject.attendance_percentage)),
                        backgroundColor: colors.attendance,
                        borderRadius: 3,
                        maxBarThickness: 13
                    }
                ]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { usePointStyle: true, padding: 18 }
                    },
                    tooltip: {
                        callbacks: {
                            label: context => `${context.dataset.label}: ${Number(context.raw).toFixed(2)}%`
                        }
                    }
                },
                scales: {
                    x: {
                        min: 0,
                        max: 100,
                        title: { display: true, text: "Percentage" },
                        ticks: {
                            stepSize: 20,
                            callback: value => `${value}%`
                        },
                        grid: { color: "rgba(148, 163, 184, 0.12)" }
                    },
                    y: {
                        ticks: { autoSkip: false, padding: 8 },
                        grid: { display: false }
                    }
                }
            }
        });
    }

    function renderSubjectFocus(subjects) {
        const container = document.getElementById("subjectFocusList");
        const emptyState = document.getElementById("subjectFocusEmpty");
        if (!container || !emptyState) return;
        container.replaceChildren();

        const focusSubjects = subjects.filter(isSubjectToFocus);
        emptyState.hidden = focusSubjects.length > 0;
        if (focusSubjects.length === 0) {
            emptyState.textContent = subjects.length
                ? "No subjects currently meet the focus rules. Keep building on your steady progress."
                : "Subjects to focus on will appear when subject scores are available.";
            return;
        }
        focusSubjects.forEach(subject => container.appendChild(createSubjectFocusCard(subject)));
    }

    function subjectPerformanceStatus(score) {
        if (!Number.isFinite(score)) return { label: "Unavailable", className: "status-unavailable" };
        if (score >= 85) return { label: "Strong", className: "status-strong" };
        if (score >= 70) return { label: "Good", className: "status-good" };
        return { label: "Needs Improvement", className: "status-needs-improvement" };
    }

    function formatScore(value) {
        const score = toNumericScore(value);
        return Number.isFinite(score) ? `${score.toFixed(2)}%` : "—";
    }

    function renderSubjectAttendance(subjects) {
        const container = document.getElementById("subjectAttendanceList");
        const emptyState = document.getElementById("subjectAttendanceEmpty");
        if (!container || !emptyState) return;
        container.replaceChildren();
        const available = subjects.filter(subject =>
            Number.isFinite(toNumericScore(subject.attendance_percentage))
        );
        if (available.length === 0) {
            emptyState.hidden = false;
            return;
        }
        emptyState.hidden = true;
        available.forEach(subject => {
            const attendance = toNumericScore(subject.attendance_percentage);
            const card = document.createElement("article");
            card.className = "subject-attendance-card";
            const heading = document.createElement("div");
            heading.className = "subject-attendance-heading";
            const name = document.createElement("h4");
            name.textContent = subject.subject;
            const value = document.createElement("strong");
            value.textContent = formatScore(attendance);
            heading.append(name, value);

            const track = document.createElement("div");
            track.className = "subject-attendance-track";
            track.setAttribute("role", "progressbar");
            track.setAttribute("aria-label", `${subject.subject} synthetic attendance`);
            track.setAttribute("aria-valuemin", "0");
            track.setAttribute("aria-valuemax", "100");
            track.setAttribute("aria-valuenow", String(attendance));
            const fill = document.createElement("span");
            const attendanceStatus = attendance >= 90
                ? "attendance-strong"
                : attendance >= 75 ? "attendance-moderate" : "attendance-low";
            fill.className = `subject-attendance-fill ${attendanceStatus}`;
            fill.style.width = `${Math.max(0, Math.min(100, attendance))}%`;
            track.appendChild(fill);

            const status = document.createElement("span");
            status.className = `attendance-status ${attendanceStatus}`;
            status.textContent = attendance >= 90
                ? "Strong demo value"
                : attendance >= 75 ? "Monitor demo value" : "Low demo value";
            card.append(heading, track, status);
            container.appendChild(card);
        });
    }

    function getSubjectAssessmentAnalysis(subject) {
        const assessments = [
            {
                key: "quiz_average",
                label: "Quiz",
                advice: "Practise short quiz sets and revisit concepts behind missed questions."
            },
            {
                key: "assignment_average",
                label: "Assignment",
                advice: "Break the next assignment into smaller steps and use the rubric or feedback to check your work."
            },
            {
                key: "internal_assessment_average",
                label: "Internal assessment",
                advice: "Review assessment feedback and practise the question formats that were challenging."
            }
        ].map(assessment => ({
            ...assessment,
            score: toNumericScore(subject[assessment.key])
        }));

        if (assessments.some(assessment =>
            !Number.isFinite(assessment.score) || assessment.score < 0 || assessment.score > 100
        )) {
            return { subject, hasEnoughData: false, assessments: [], weakAreas: [] };
        }

        const weakAreas = assessments.filter(assessment => {
            const otherScores = assessments
                .filter(candidate => candidate !== assessment)
                .map(candidate => candidate.score);
            const otherAverage = otherScores.reduce((total, score) => total + score, 0) / otherScores.length;
            assessment.otherAverage = otherAverage;
            assessment.relativeGap = otherAverage - assessment.score;
            return assessment.score < ASSESSMENT_IMPROVEMENT_THRESHOLD
                || assessment.relativeGap >= ASSESSMENT_WEAKNESS_GAP;
        });
        return { subject, hasEnoughData: true, assessments, weakAreas };
    }

    function toNumericScore(value) {
        if (value === null || value === undefined || value === "") return NaN;
        return Number(value);
    }

    function chartPercentage(value) {
        const score = toNumericScore(value);
        return Number.isFinite(score) && score >= 0 && score <= 100 ? score : null;
    }

    function renderAssessmentWeaknesses(subjects) {
        const container = document.getElementById("assessmentWeaknessList");
        const emptyState = document.getElementById("assessmentWeaknessEmpty");
        if (!container || !emptyState) return;
        container.replaceChildren();
        const analyses = subjects.map(getSubjectAssessmentAnalysis)
            .filter(analysis => analysis.hasEnoughData);
        if (analyses.length === 0) {
            emptyState.hidden = false;
            emptyState.textContent = "Assessment comparisons need quiz, assignment, and internal assessment scores for a subject. No recommendations are generated when any of those scores are missing.";
            return;
        }

        emptyState.hidden = true;
        analyses.forEach(analysis => {
            container.appendChild(createAssessmentWeaknessCard(analysis));
        });
        const omittedSubjects = subjects.length - analyses.length;
        if (omittedSubjects > 0) {
            emptyState.hidden = false;
            emptyState.textContent = `${omittedSubjects} subject${omittedSubjects === 1 ? " was" : "s were"} omitted because all three assessment scores are not available; no recommendation is generated for incomplete comparisons.`;
        }
    }

    function createAssessmentWeaknessCard(analysis) {
        const card = document.createElement("article");
        card.className = "assessment-weakness-card";
        const heading = document.createElement("div");
        heading.className = "assessment-weakness-heading";
        const title = document.createElement("h4");
        title.textContent = analysis.subject.subject;
        const focusBadge = document.createElement("span");
        focusBadge.className = analysis.weakAreas.length
            ? "assessment-focus-count has-focus"
            : "assessment-focus-count";
        focusBadge.textContent = analysis.weakAreas.length
            ? `${analysis.weakAreas.length} focus ${analysis.weakAreas.length === 1 ? "area" : "areas"}`
            : "Balanced";
        heading.append(title, focusBadge);

        const scoreList = document.createElement("div");
        scoreList.className = "assessment-score-list";
        analysis.assessments.forEach(assessment => {
            const row = document.createElement("div");
            row.className = "assessment-score-item";
            const rowHeading = document.createElement("div");
            rowHeading.className = "assessment-score-heading";
            const label = document.createElement("span");
            label.textContent = assessment.label;
            const value = document.createElement("strong");
            value.textContent = formatScore(assessment.score);
            rowHeading.append(label, value);

            const track = document.createElement("div");
            track.className = "assessment-score-track";
            track.setAttribute("role", "progressbar");
            track.setAttribute("aria-label", `${analysis.subject.subject} ${assessment.label} score`);
            track.setAttribute("aria-valuemin", "0");
            track.setAttribute("aria-valuemax", "100");
            track.setAttribute("aria-valuenow", String(assessment.score));
            const fill = document.createElement("span");
            const status = subjectPerformanceStatus(assessment.score);
            fill.className = `assessment-score-fill ${status.className}`;
            fill.style.width = `${assessment.score}%`;
            track.appendChild(fill);

            const detail = document.createElement("div");
            detail.className = "assessment-score-detail";
            const statusLabel = document.createElement("span");
            statusLabel.className = `assessment-status ${status.className}`;
            statusLabel.textContent = status.label;
            detail.appendChild(statusLabel);
            if (analysis.weakAreas.includes(assessment)) {
                const reason = document.createElement("span");
                reason.className = "assessment-relative-gap";
                reason.textContent = assessment.score < ASSESSMENT_IMPROVEMENT_THRESHOLD
                    ? `Below ${ASSESSMENT_IMPROVEMENT_THRESHOLD}%`
                    : `${assessment.relativeGap.toFixed(1)} pp below other assessments`;
                detail.appendChild(reason);
            }
            row.append(rowHeading, track, detail);
            scoreList.appendChild(row);
        });

        const insight = document.createElement("div");
        insight.className = "assessment-weakness-insight";
        if (analysis.weakAreas.length) {
            const insightTitle = document.createElement("strong");
            insightTitle.textContent = "Practical next steps";
            const suggestions = document.createElement("ul");
            analysis.weakAreas.forEach(assessment => {
                const item = document.createElement("li");
                const comparison = assessment.score < ASSESSMENT_IMPROVEMENT_THRESHOLD
                    ? `${assessment.label} is ${formatScore(assessment.score)}, below the ${ASSESSMENT_IMPROVEMENT_THRESHOLD}% improvement threshold.`
                    : `${assessment.label} is ${formatScore(assessment.score)}, ${assessment.relativeGap.toFixed(1)} percentage points below the average of the other two assessment categories.`;
                item.textContent = `${comparison} ${assessment.advice}`;
                suggestions.appendChild(item);
            });
            insight.append(insightTitle, suggestions);
        } else {
            const balanced = document.createElement("p");
            balanced.textContent = "No assessment-specific weakness is flagged by the current comparison rules.";
            insight.appendChild(balanced);
        }

        card.append(heading, scoreList, insight);
        return card;
    }

    function initializeRecommendations(studentId, profile, subjects, recommendationData) {
        const areas = buildSubjectRecommendationAreas(subjects, recommendationData);
        renderImprovementSummary(areas);
        renderPriorityRecommendations(areas);
        renderStudySuggestions(profile, subjects);

        const tasks = buildPersonalizedStudyPlan(areas);
        studyPlanState = {
            studentId,
            tasks,
            completions: {},
            weekStart: null
        };
        renderWeeklyStudySchedule();
        renderTodayStudyTasks();
        renderWeeklyTaskProgress();
        loadStudyTaskCompletions(studentId);
    }

    function buildSubjectRecommendationAreas(subjects, recommendationData) {
        const engineFlags = new Map();
        (recommendationData.topics_needing_attention || []).forEach(item => {
            if (!item || typeof item.subject !== "string") return;
            const priority = String(item.priority || "");
            const existing = engineFlags.get(item.subject);
            if (priority === "High") {
                engineFlags.set(item.subject, priority);
            } else if (priority === "Medium" && existing !== "High") {
                engineFlags.set(item.subject, priority);
            } else if (priority === "Support" && !existing) {
                engineFlags.set(item.subject, priority);
            }
        });

        return subjects
            .filter(subject => typeof subject.subject === "string")
            .map(subject => {
                const overall = toNumericScore(subject.average_score);
                const attendance = toNumericScore(subject.attendance_percentage);
                const assessments = [
                    { label: "Quiz", score: toNumericScore(subject.quiz_average) },
                    { label: "Assignment", score: toNumericScore(subject.assignment_average) },
                    { label: "Internal assessment", score: toNumericScore(subject.internal_assessment_average) }
                ].filter(item => Number.isFinite(item.score));
                const validScores = [overall, ...assessments.map(item => item.score)]
                    .filter(Number.isFinite);
                const lowestAssessment = [...assessments]
                    .sort((left, right) => left.score - right.score)[0] || null;
                const enginePriority = engineFlags.get(subject.subject) || null;
                const reasons = [];
                let high = enginePriority === "High";
                let medium = enginePriority === "Medium";

                if (Number.isFinite(overall) && overall < 65) {
                    high = true;
                    reasons.push(`Overall subject score is ${formatScore(overall)}, below 65%.`);
                } else if (Number.isFinite(overall) && overall < 75) {
                    medium = true;
                    reasons.push(`Overall subject score is ${formatScore(overall)}, below the 75% guide.`);
                }

                assessments.forEach(item => {
                    if (item.score < 60) {
                        high = true;
                        reasons.push(`${item.label} average is ${formatScore(item.score)}, below 60%.`);
                    } else if (item.score < 70) {
                        medium = true;
                        reasons.push(`${item.label} average is ${formatScore(item.score)}, below the 70% guide.`);
                    }
                });

                if (Number.isFinite(attendance) && attendance < 75) {
                    high = true;
                    reasons.push(`Synthetic subject attendance is ${formatScore(attendance)}, below 75%.`);
                } else if (Number.isFinite(attendance) && attendance < 85) {
                    medium = true;
                    reasons.push(`Synthetic subject attendance is ${formatScore(attendance)}, below the 85% guide.`);
                }
                if (enginePriority && reasons.length === 0) {
                    reasons.push("The existing academic recommendation engine flagged this subject for follow-up.");
                }

                const priority = high ? "High" : medium ? "Medium" : "Maintain";
                const reason = priority === "Maintain"
                    ? "Your recorded subject results meet the current score and attendance guides."
                    : reasons.join(" ");
                return {
                    subject: subject.subject,
                    overall,
                    attendance,
                    assessments,
                    lowestAssessment,
                    currentPerformance: [
                        Number.isFinite(overall) ? `Overall ${formatScore(overall)}` : null,
                        lowestAssessment ? `Lowest assessment: ${lowestAssessment.label} ${formatScore(lowestAssessment.score)}` : null,
                        Number.isFinite(attendance) ? `Synthetic attendance ${formatScore(attendance)}` : null
                    ].filter(Boolean).join(" · "),
                    priority,
                    enginePriority,
                    reasons,
                    reason,
                    suggestion: getSubjectImprovementSuggestion(
                        subject,
                        lowestAssessment,
                        attendance,
                        priority
                    ),
                    severity: validScores.length
                        ? Math.max(...validScores.map(value => Math.max(0, 75 - value)))
                            + (Number.isFinite(attendance) ? Math.max(0, 85 - attendance) : 0)
                            + (enginePriority === "High" ? 20 : enginePriority === "Medium" ? 8 : 0)
                        : 0
                };
            })
            .sort((left, right) =>
                ({ High: 0, Medium: 1, Maintain: 2 }[left.priority]
                    - { High: 0, Medium: 1, Maintain: 2 }[right.priority])
                || right.severity - left.severity
                || left.subject.localeCompare(right.subject)
            );
    }

    function getSubjectImprovementSuggestion(subject, weakestAssessment, attendance, priority) {
        const suggestions = [];
        if (weakestAssessment && weakestAssessment.score < 70) {
            const assessmentActions = {
                Quiz: "Practise short question sets and review the reasoning behind missed answers.",
                Assignment: "Review assignment feedback and use it to improve one part of your next submission.",
                "Internal assessment": "Revise class concepts and practise writing a similar response."
            };
            suggestions.push(assessmentActions[weakestAssessment.label]);
        }
        if (Number.isFinite(attendance) && attendance < 85) {
            suggestions.push("Keep a regular attendance routine; this subject attendance figure is synthetic demonstration data.");
        }
        if (Number.isFinite(toNumericScore(subject.average_score)) && toNumericScore(subject.average_score) < 75) {
            suggestions.push(`Schedule two short review sessions for ${subject.subject} concepts and practice questions.`);
        }
        if (suggestions.length === 0) {
            return priority === "Maintain"
                ? "Maintain your steady attendance and review feedback after each assessment."
                : "Review recent class feedback and choose one small, achievable practice activity.";
        }
        return suggestions.slice(0, 2).join(" ");
    }

    function renderImprovementSummary(areas) {
        const summary = document.getElementById("improvementSummary");
        if (!summary) return;
        const high = areas.filter(area => area.priority === "High");
        const medium = areas.filter(area => area.priority === "Medium");
        const maintain = areas.filter(area => area.priority === "Maintain");
        const parts = [];
        if (high.length) {
            parts.push(`Focus first on ${high.slice(0, 2).map(area => area.subject).join(" and ")} (${high.length} high-priority area${high.length === 1 ? "" : "s"}).`);
        }
        if (medium.length) {
            parts.push(`${medium.slice(0, 2).map(area => area.subject).join(" and ")} need regular practice.`);
        }
        if (maintain.length) {
            parts.push(`Maintain progress in ${maintain.slice(0, 2).map(area => area.subject).join(" and ")}.`);
        }
        summary.textContent = parts.length
            ? parts.join(" ")
            : "Subject performance data is not available yet, so no improvement areas have been selected.";
    }

    function renderPriorityRecommendations(areas) {
        const groups = [
            { priority: "High", containerId: "highPriorityRecommendations", emptyId: "highPriorityEmpty" },
            { priority: "Medium", containerId: "mediumPriorityRecommendations", emptyId: "mediumPriorityEmpty" },
            { priority: "Maintain", containerId: "maintainRecommendations", emptyId: "maintainEmpty" }
        ];
        groups.forEach(group => {
            const container = document.getElementById(group.containerId);
            const emptyState = document.getElementById(group.emptyId);
            if (!container || !emptyState) return;
            container.replaceChildren();
            const matches = areas.filter(area => area.priority === group.priority);
            emptyState.hidden = matches.length > 0;
            matches.forEach(area => container.appendChild(createRecommendationCard(area)));
        });
    }

    function createRecommendationCard(area) {
        const card = document.createElement("article");
        card.className = `recommendation-area-card priority-${area.priority.toLowerCase()}`;
        const header = document.createElement("div");
        header.className = "recommendation-area-header";
        const title = document.createElement("h5");
        title.textContent = area.subject;
        const badge = document.createElement("span");
        badge.className = `recommendation-priority-badge priority-${area.priority.toLowerCase()}`;
        badge.textContent = area.priority === "Maintain" ? "Maintain" : `${area.priority} priority`;
        header.append(title, badge);
        const performance = document.createElement("p");
        performance.className = "recommendation-current-performance";
        performance.textContent = area.currentPerformance || "Current performance is unavailable.";
        const reason = document.createElement("p");
        reason.className = "recommendation-reason";
        reason.textContent = area.reason;
        const suggestion = document.createElement("p");
        suggestion.className = "recommendation-suggestion";
        suggestion.textContent = area.suggestion;
        card.append(header, performance, reason, suggestion);
        return card;
    }

    function buildPersonalizedStudyPlan(areas) {
        const scoredSubjects = areas.filter(area => Number.isFinite(area.overall));
        if (scoredSubjects.length === 0) return [];
        const first = scoredSubjects[0];
        const second = scoredSubjects.find(area => area.subject !== first.subject) || first;
        const engineSubject = scoredSubjects.find(area =>
            area.enginePriority === "High"
            || area.enginePriority === "Medium"
            || area.enginePriority === "Support"
        );
        const weakestAssessment = findWeakestAssessment(areas);
        const firstWeakAssessment = first.lowestAssessment;
        const secondWeakAssessment = second.lowestAssessment;
        const specs = [
            {
                subject: first,
                activity: `Review class notes and summarise one key idea from ${first.subject}.`,
                duration: 30,
                priority: first.priority
            },
            {
                subject: first,
                activity: buildAssessmentActivity(first, firstWeakAssessment, "practice"),
                duration: 45,
                priority: first.priority
            },
            {
                subject: second,
                activity: `Revise class concepts in ${second.subject} and write a brief recap in your own words.`,
                duration: 30,
                priority: second.priority
            },
            {
                subject: second,
                activity: buildAssessmentActivity(second, secondWeakAssessment, "feedback"),
                duration: 45,
                priority: second.priority
            },
            weakestAssessment
                ? {
                    subject: weakestAssessment.area,
                    activity: buildAssessmentActivity(
                        weakestAssessment.area,
                        weakestAssessment.assessment,
                        "review"
                    ),
                    duration: 30,
                    priority: weakestAssessment.area.priority
                }
                : {
                    subject: first,
                    activity: `Review one assessment correction in ${first.subject} and note what you learned.`,
                    duration: 30,
                    priority: first.priority
                },
            {
                subject: engineSubject || second,
                    activity: engineSubject
                        ? `Use your existing study recommendations to guide one focused review session in ${engineSubject.subject}.`
                        : `Review assignment or internal-assessment feedback in ${second.subject} and choose one improvement to apply.`,
                duration: 30,
                priority: (engineSubject || second).priority
            },
            {
                subject: first,
                activity: `Review this week's study tasks and set one small next goal for ${first.subject}.`,
                duration: 30,
                priority: first.priority
            }
        ];
        const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        return specs.map((spec, index) => ({
            day: days[index],
            dayIndex: index,
            subject: spec.subject.subject,
            activity: spec.activity,
            duration: spec.duration,
            priority: spec.priority,
            taskId: `${days[index].toLowerCase()}-${slugify(spec.subject.subject)}-${slugify(spec.activity)}`.slice(0, 160)
        }));
    }

    function buildAssessmentActivity(area, assessment, mode) {
        if (!assessment) {
            return `Practise a small set of questions in ${area.subject} and review any answers that felt difficult.`;
        }
        const actions = {
            Quiz: mode === "feedback"
                ? "Review recent quiz feedback and explain the correct approach to one missed question."
                : "Practise a short quiz question set and revisit concepts behind any mistakes.",
            Assignment: mode === "feedback"
                ? "Review assignment feedback and improve one part of a previous answer."
                : "Break the next assignment into one small step and check it against feedback.",
            "Internal assessment": mode === "review"
                ? "Revise the class concepts behind a recent internal assessment and write one practice response."
                : "Review internal-assessment feedback and practise a similar written question."
        };
        return `${assessment.label} practice for ${area.subject}: ${actions[assessment.label]}`;
    }

    function findWeakestAssessment(areas) {
        const choices = [];
        areas.forEach(area => {
            area.assessments.forEach(assessment => {
                choices.push({ area, assessment });
            });
        });
        choices.sort((left, right) =>
            left.assessment.score - right.assessment.score
            || left.area.overall - right.area.overall
        );
        return choices[0] || null;
    }

    function slugify(value) {
        return String(value)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-|-$/g, "");
    }

    function renderWeeklyStudySchedule() {
        const container = document.getElementById("recommendationWeeklyStudyPlan");
        const emptyState = document.getElementById("recommendationPlanEmpty");
        if (!container || !emptyState) return;
        container.replaceChildren();
        emptyState.hidden = studyPlanState.tasks.length > 0;
        studyPlanState.tasks.forEach((task, index) => {
            const item = document.createElement("li");
            item.className = `recommendation-plan-day priority-${task.priority.toLowerCase()}`;
            const day = document.createElement("div");
            day.className = "recommendation-plan-day-heading";
            const dayTitle = document.createElement("h4");
            dayTitle.textContent = task.day;
            const badge = document.createElement("span");
            badge.className = `recommendation-priority-badge priority-${task.priority.toLowerCase()}`;
            badge.textContent = task.priority === "Maintain" ? "Maintain" : `${task.priority} priority`;
            day.append(dayTitle, badge);
            const subject = document.createElement("strong");
            subject.className = "recommendation-plan-subject";
            subject.textContent = task.subject;
            const activity = document.createElement("p");
            activity.className = "recommendation-plan-activity";
            activity.textContent = task.activity;
            const duration = document.createElement("span");
            duration.className = "recommendation-plan-duration";
            duration.textContent = `${task.duration} minutes`;
            const taskState = studyPlanState.completions[task.taskId] ? "Completed" : "Suggested";
            item.setAttribute("aria-label", `${task.day}: ${task.subject}. ${task.activity} ${task.duration} minutes. ${taskState}.`);
            item.append(day, subject, activity, duration);
            container.appendChild(item);
        });
    }

    async function loadStudyTaskCompletions(studentId) {
        const error = document.getElementById("taskSaveError");
        if (error) {
            error.hidden = true;
            error.textContent = "";
        }
        try {
            const response = await fetch(`/api/student/${encodeURIComponent(studentId)}/study-tasks`);
            if (!response.ok) throw new Error(`Could not load saved study tasks (HTTP ${response.status}).`);
            const data = await response.json();
            if (studyPlanState.studentId !== studentId) return;
            studyPlanState.completions = data.completions || {};
            studyPlanState.weekStart = data.week_start || null;
            renderWeeklyStudySchedule();
            renderTodayStudyTasks();
            renderWeeklyTaskProgress();
        } catch (requestError) {
            if (studyPlanState.studentId !== studentId) return;
            displayTaskPersistenceError(requestError.message);
        }
    }

    function renderTodayStudyTasks() {
        const container = document.getElementById("todayStudyTasks");
        if (!container) return;
        container.replaceChildren();
        const todayIndex = (new Date().getDay() + 6) % 7;
        const task = studyPlanState.tasks[todayIndex];
        const caption = document.getElementById("todayTaskCaption");
        if (caption) {
            caption.textContent = task
                ? `Today's suggested task · ${task.day}, ${task.duration} minutes`
                : "No study task is available until subject results load.";
        }
        if (!task) {
            const empty = document.createElement("p");
            empty.className = "recommendation-empty";
            empty.textContent = "Your suggested daily task will appear when subject performance data is available.";
            container.appendChild(empty);
            return;
        }

        const card = document.createElement("article");
        card.className = `today-task-card ${studyPlanState.completions[task.taskId] ? "is-complete" : ""}`;
        const label = document.createElement("label");
        label.className = "today-task-label";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = Boolean(studyPlanState.completions[task.taskId]);
        checkbox.setAttribute("aria-label", `Mark ${task.subject} task as completed`);
        checkbox.addEventListener("change", () => {
            updateStudyTaskCompletion(task, checkbox.checked, checkbox);
        });
        const checkboxMark = document.createElement("span");
        checkboxMark.className = "today-task-checkbox-mark";
        const content = document.createElement("span");
        content.className = "today-task-content";
        const subject = document.createElement("strong");
        subject.textContent = task.subject;
        const description = document.createElement("span");
        description.textContent = task.activity;
        const metadata = document.createElement("span");
        metadata.className = "today-task-metadata";
        metadata.textContent = `${task.duration} minutes · ${task.priority === "Maintain" ? "Maintain progress" : `${task.priority} priority`}`;
        content.append(subject, description, metadata);
        label.append(checkbox, checkboxMark, content);
        const state = document.createElement("span");
        state.className = "today-task-state";
        state.textContent = checkbox.checked ? "Completed" : "Pending";
        card.append(label, state);
        container.appendChild(card);
    }

    async function updateStudyTaskCompletion(task, completed, checkbox) {
        checkbox.disabled = true;
        const error = document.getElementById("taskSaveError");
        if (error) {
            error.hidden = true;
            error.textContent = "";
        }
        try {
            const response = await fetch(
                `/api/student/${encodeURIComponent(studyPlanState.studentId)}/study-tasks`,
                {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ task_id: task.taskId, completed })
                }
            );
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || `Could not save task completion (HTTP ${response.status}).`);
            studyPlanState.completions[task.taskId] = result.completed;
            studyPlanState.weekStart = result.week_start;
            renderWeeklyStudySchedule();
            renderTodayStudyTasks();
            renderWeeklyTaskProgress();
        } catch (requestError) {
            checkbox.checked = !completed;
            checkbox.disabled = false;
            displayTaskPersistenceError(requestError.message);
        }
    }

    function renderWeeklyTaskProgress() {
        const total = studyPlanState.tasks.length;
        const completed = studyPlanState.tasks.filter(task =>
            Boolean(studyPlanState.completions[task.taskId])
        ).length;
        const pending = total - completed;
        const percentage = total ? Math.round((completed / total) * 100) : 0;
        setText("weeklyTaskTotal", String(total));
        setText("weeklyTaskCompleted", String(completed));
        setText("weeklyTaskPending", String(pending));
        setText("weeklyTaskPercent", `${percentage}%`);
        const progress = document.querySelector(".task-progress-track");
        const bar = document.getElementById("weeklyTaskProgressBar");
        if (progress) progress.setAttribute("aria-valuenow", String(percentage));
        if (bar) bar.style.width = `${percentage}%`;
        const weekLabel = document.getElementById("weeklyProgressWeekLabel");
        if (weekLabel && studyPlanState.weekStart) {
            weekLabel.textContent = `Week starting ${formatISODate(studyPlanState.weekStart)}`;
        }
    }

    function formatISODate(value) {
        const parts = String(value).split("-").map(Number);
        if (parts.length !== 3 || parts.some(part => !Number.isFinite(part))) return value;
        return new Date(parts[0], parts[1] - 1, parts[2]).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric"
        });
    }

    function displayTaskPersistenceError(message) {
        const error = document.getElementById("taskSaveError");
        if (!error) return;
        error.textContent = `Task progress could not be synchronized: ${message}`;
        error.hidden = false;
    }

    function createSubjectPerformanceCard(subject, status, score, attendance) {
        const card = document.createElement("article");
        card.className = `subject-performance-card ${status.className}`;

        const heading = document.createElement("div");
        heading.className = "subject-performance-card-heading";
        const name = document.createElement("h4");
        name.className = "subject-performance-name";
        name.textContent = subject.subject;
        const badge = document.createElement("span");
        badge.className = `performance-status ${status.className}`;
        badge.textContent = status.label;
        heading.append(name, badge);

        const scoreRow = document.createElement("div");
        scoreRow.className = "subject-score-row";
        const scoreLabel = document.createElement("span");
        scoreLabel.textContent = "Overall score";
        const scoreValue = document.createElement("strong");
        scoreValue.textContent = formatScore(subject.average_score);
        scoreRow.append(scoreLabel, scoreValue);

        const progress = document.createElement("div");
        progress.className = "subject-score-track";
        progress.setAttribute("role", "progressbar");
        progress.setAttribute("aria-label", `${subject.subject} overall score`);
        progress.setAttribute("aria-valuemin", "0");
        progress.setAttribute("aria-valuemax", "100");
        const progressValue = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
        progress.setAttribute("aria-valuenow", String(progressValue));
        const progressBar = document.createElement("span");
        progressBar.className = "subject-score-fill";
        progressBar.style.width = `${progressValue}%`;
        progress.appendChild(progressBar);

        const metrics = document.createElement("dl");
        metrics.className = "subject-performance-metrics";
        [
            ["Attendance*", attendance],
            ["Quiz average", subject.quiz_average],
            ["Assignment average", subject.assignment_average],
            ["Internal assessment", subject.internal_assessment_average]
        ].forEach(([label, value]) => {
            const metric = document.createElement("div");
            metric.className = "subject-performance-metric";
            const term = document.createElement("dt");
            term.textContent = label;
            const detail = document.createElement("dd");
            detail.textContent = formatScore(value);
            metric.append(term, detail);
            metrics.appendChild(metric);
        });

        card.append(heading, scoreRow, progress, metrics);
        return card;
    }

    function isSubjectToFocus(subject) {
        const score = toNumericScore(subject.average_score);
        const attendance = toNumericScore(subject.attendance_percentage);
        const assessmentScores = [
            toNumericScore(subject.quiz_average),
            toNumericScore(subject.assignment_average),
            toNumericScore(subject.internal_assessment_average)
        ];
        return (Number.isFinite(score) && score < 70)
            || (Number.isFinite(attendance) && attendance < 75)
            || assessmentScores.some(value => Number.isFinite(value) && value < 65);
    }

    function createSubjectFocusCard(subject) {
        const card = document.createElement("article");
        card.className = "subject-focus-card";
        const heading = document.createElement("div");
        heading.className = "subject-focus-heading";
        const name = document.createElement("h4");
        name.textContent = subject.subject;
        const badge = document.createElement("span");
        badge.className = "performance-status status-needs-improvement";
        badge.textContent = "Focus";
        heading.append(name, badge);

        const metrics = document.createElement("div");
        metrics.className = "subject-focus-metrics";
        [
            ["Overall", subject.average_score],
            ["Attendance*", subject.attendance_percentage],
            ["Quiz", subject.quiz_average],
            ["Assignment", subject.assignment_average],
            ["Internal assessment", subject.internal_assessment_average]
        ].forEach(([label, value]) => {
            const metric = document.createElement("span");
            metric.textContent = `${label}: ${formatScore(value)}`;
            metrics.appendChild(metric);
        });

        const guidance = getSubjectFocusGuidance(subject);
        const reasonTitle = document.createElement("strong");
        reasonTitle.className = "subject-focus-label";
        reasonTitle.textContent = "Why it needs attention";
        const reasons = document.createElement("ul");
        reasons.className = "subject-focus-reasons";
        guidance.reasons.forEach(reason => {
            const item = document.createElement("li");
            item.textContent = reason;
            reasons.appendChild(item);
        });

        const suggestionTitle = document.createElement("strong");
        suggestionTitle.className = "subject-focus-label";
        suggestionTitle.textContent = "A practical next step";
        const suggestions = document.createElement("ul");
        suggestions.className = "subject-focus-suggestions";
        guidance.suggestions.forEach(suggestion => {
            const item = document.createElement("li");
            item.textContent = suggestion;
            suggestions.appendChild(item);
        });
        card.append(heading, metrics, reasonTitle, reasons, suggestionTitle, suggestions);
        return card;
    }

    function getSubjectFocusGuidance(subject) {
        const reasons = [];
        const suggestions = [];
        const attendance = toNumericScore(subject.attendance_percentage);
        const overall = toNumericScore(subject.average_score);
        const assessments = [
            {
                label: "Quiz average",
                value: toNumericScore(subject.quiz_average),
                suggestion: "Add short quiz-preparation sessions and revisit concepts behind missed questions."
            },
            {
                label: "Assignment average",
                value: toNumericScore(subject.assignment_average),
                suggestion: "Break the next assignment into smaller milestones and review feedback before submitting."
            },
            {
                label: "Internal assessment",
                value: toNumericScore(subject.internal_assessment_average),
                suggestion: "Review internal-assessment feedback and practise the question types that were challenging."
            }
        ];
        if (Number.isFinite(attendance) && attendance < 75) {
            reasons.push(`Subject attendance is ${formatScore(attendance)}, below the 75% focus threshold.`);
            suggestions.push("Attend upcoming classes consistently and review notes for any missed lessons.");
        }
        if (Number.isFinite(overall) && overall < 70) {
            reasons.push(`Overall subject score is ${formatScore(overall)}, below the 70% focus threshold.`);
        }
        assessments.forEach(assessment => {
            if (Number.isFinite(assessment.value) && assessment.value < 65) {
                reasons.push(`${assessment.label} is ${formatScore(assessment.value)}, below the 65% assessment threshold.`);
                suggestions.push(assessment.suggestion);
            }
        });
        const weakestAssessment = assessments
            .filter(assessment => Number.isFinite(assessment.value))
            .sort((left, right) => left.value - right.value)[0];
        if (weakestAssessment && (suggestions.length === 0 || (Number.isFinite(overall) && overall < 70))) {
            if (!suggestions.includes(weakestAssessment.suggestion)) {
                suggestions.push(weakestAssessment.suggestion);
            }
        }
        return { reasons, suggestions };
    }

    function createStrongestSubjectCard(subject) {
        const card = document.createElement("article");
        card.className = "strongest-subject-card";
        const content = document.createElement("div");
        content.className = "strongest-subject-content";
        const label = document.createElement("span");
        label.className = "strongest-subject-eyebrow";
        label.textContent = "Top overall result";
        const name = document.createElement("h4");
        name.textContent = subject.subject;
        const message = document.createElement("p");
        message.textContent = "This is your strongest subject right now—keep using the learning habits that are working for you.";
        content.append(label, name, message);
        const score = document.createElement("strong");
        score.className = "strongest-subject-score";
        score.textContent = formatScore(subject.average_score);
        card.append(content, score);
        return card;
    }

    function wrapSubjectLabel(subject) {
        const words = String(subject).split(/\s+/);
        const lines = [];
        let line = "";
        words.forEach(word => {
            if (line && `${line} ${word}`.length > 18) {
                lines.push(line);
                line = word;
            } else {
                line = line ? `${line} ${word}` : word;
            }
        });
        if (line) lines.push(line);
        return lines;
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
        ["confidenceValue", "studentInsightsConfidence"].forEach(id => {
            const element = document.getElementById(id);
            if (element && element.textContent.includes("--")) element.textContent = "—";
        });
    }

    function hideError() {
        if (errorBanner) errorBanner.style.display = "none";
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
        })[character]);
    }
});
