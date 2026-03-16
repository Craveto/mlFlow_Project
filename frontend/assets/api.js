async function fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
}

function formatMoney(value) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return "N/A";
    }
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function createAppShell(activeKey, title, subtitle) {
    return `
        <div class="app-shell">
            <aside class="sidebar">
                <div class="brand-mark">Forecast Workspace</div>
                <h1>BTC Forecasting</h1>
                <hr>
                <div class="nav-label">Navigation</div>
                <a class="nav-link ${activeKey === "overview" ? "active" : ""}" href="./index.html">Dashboard Overview</a>
                <a class="nav-link ${activeKey === "drift" ? "active" : ""}" href="./drift.html">Drift Monitoring</a>
                <a class="nav-link ${activeKey === "roi" ? "active" : ""}" href="./roi.html">ROI Analysis</a>
            </aside>
            <main class="content">
                <header class="page-header">
                    <div>
                        <div class="kicker">${title.kicker}</div>
                        <h2>${title.heading}</h2>
                        <p>${subtitle}</p>
                    </div>
                </header>
                <div id="page-root" class="loading">Loading data...</div>
            </main>
        </div>`;
}
