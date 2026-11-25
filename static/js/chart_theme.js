(() => {
    const colors = Object.freeze({
        overall: "#F97316",
        quiz: "#38BDF8",
        assignment: "#34D399",
        internalAssessment: "#FDBA74",
        attendance: "#0EA5E9",
        positive: "#34D399",
        negative: "#FACC15"
    });

    window.AcademicChartTheme = Object.freeze({ colors });

    if (!window.Chart || !Chart.defaults) return;

    Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    Chart.defaults.color = "#94A3B8";

    const legendLabels = Chart.defaults.plugins.legend.labels;
    legendLabels.color = "#F8FAFC";
    legendLabels.usePointStyle = true;
    legendLabels.boxWidth = 9;
    legendLabels.padding = 14;

    const tooltip = Chart.defaults.plugins.tooltip;
    tooltip.backgroundColor = "#080C18";
    tooltip.titleColor = "#F8FAFC";
    tooltip.bodyColor = "#94A3B8";
    tooltip.borderColor = "rgba(148, 163, 184, 0.3)";
    tooltip.borderWidth = 1;
    tooltip.padding = 10;
    tooltip.displayColors = true;
})();
