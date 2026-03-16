document.addEventListener("DOMContentLoaded", async () => {
    document.body.innerHTML = createAppShell(
        "drift",
        { kicker: "Data Stability View", heading: "Drift Monitoring" },
        "A compact market-stability view built from processed BTC-USD hourly data, focused on volatility shifts and price displacement from the 21-hour trend."
    );

    const root = document.getElementById("page-root");

    try {
        const data = await fetchJson("/api/drift/");
        const drift = data.drift_snapshot;

        root.className = "";
        root.innerHTML = `
            <section class="panel context-grid">
                <div class="context-item"><small>Data Source</small><strong>${data.data_context.data_source}</strong><div class="muted">${data.data_context.symbol} | ${data.data_context.data_frequency}</div></div>
                <div class="context-item"><small>Coverage</small><strong>${data.data_context.coverage_start}</strong><div class="muted">to ${data.data_context.coverage_end}</div></div>
                <div class="context-item"><small>Latest Market Date</small><strong>${drift.latest_date}</strong></div>
                <div class="context-item"><small>Dashboard Refreshed</small><strong>${data.data_context.dashboard_time}</strong></div>
            </section>
            <section class="section grid-2">
                <div class="card hero">
                    <div class="kicker" style="background: rgba(255,255,255,0.14); color: white;">Drift Status</div>
                    <h3>${drift.status}</h3>
                    <div class="hero-value">${drift.latest_volatility}</div>
                    <p>${drift.summary}</p>
                    <div class="metric-grid two">
                        <div class="metric"><small>Latest Market Time</small><strong>${drift.latest_date}</strong></div>
                        <div class="metric"><small>Latest Hourly Return</small><strong>${drift.latest_return}</strong></div>
                    </div>
                </div>
                <div class="grid-3">
                    <div class="panel table-wrap"><small>Latest Hourly Return</small><h3>${drift.latest_return}</h3><div class="muted">Most recent one-hour move.</div></div>
                    <div class="panel table-wrap"><small>24-Hour Volatility</small><h3>${drift.latest_volatility}</h3><div class="muted">Short-term realized hourly volatility.</div></div>
                    <div class="panel table-wrap"><small>Volatility Ratio</small><h3>${drift.volatility_ratio}</h3><div class="muted">24-hour vs 7-day baseline.</div></div>
                    <div class="panel table-wrap" style="grid-column: 1 / -1;"><small>Price vs MA21</small><h3>${drift.price_vs_ma21}</h3><div class="muted">Distance between the latest close and the 21-hour moving average.</div></div>
                </div>
            </section>
            <section class="section grid-2">
                <div class="panel">
                    <div class="section-title">
                        <h3>How this page reads drift</h3>
                        <p>This page uses lightweight heuristics so you can quickly spot instability before moving to a full monitoring stack.</p>
                    </div>
                    <div class="table-wrap stack">
                        <div class="stack-item"><strong>Volatility ratio is the main trigger</strong><div class="muted">If recent 24-hour volatility rises well above the 7-day baseline, the page raises the drift status.</div></div>
                        <div class="stack-item"><strong>Price displacement gives extra context</strong><div class="muted">A large move away from the 21-hour trend can indicate a regime shift even if the latest hourly return is small.</div></div>
                        <div class="stack-item"><strong>Use this as a front-door monitor</strong><div class="muted">It is intentionally simple and readable, so you can decide when deeper drift analysis is needed.</div></div>
                    </div>
                </div>
                <div class="panel">
                    <div class="section-title">
                        <h3>Signal Thresholds</h3>
                        <p>The current page uses these simple breakpoints.</p>
                    </div>
                    <div class="table-wrap stack">
                        <div class="stack-item"><strong>Stable</strong><div class="muted">${data.thresholds.stable}</div></div>
                        <div class="stack-item"><strong>Watch</strong><div class="muted">${data.thresholds.watch}</div></div>
                        <div class="stack-item"><strong>Alert</strong><div class="muted">${data.thresholds.alert}</div></div>
                    </div>
                </div>
            </section>`;
    } catch (error) {
        root.className = "empty";
        root.textContent = `Failed to load drift data: ${error.message}`;
    }
});
