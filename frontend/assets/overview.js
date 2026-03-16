document.addEventListener("DOMContentLoaded", async () => {
    document.body.innerHTML = createAppShell(
        "overview",
        { kicker: "BTC-USD Hourly Forecast Hub", heading: "BTCUSD Forecasting Dashboard Overview" },
        "Live model snapshots from Yahoo Finance hourly BTC-USD data, with one clear next-hour forecast and side-by-side model comparisons."
    );

    const root = document.getElementById("page-root");

    try {
        const data = await fetchJson("/api/overview/");
        const active = data.forecast_cards.active;
        const runRows = data.runs.length
            ? data.runs.map((run) => `
                <tr>
                    <td>${run.run_id.slice(0, 10)}</td>
                    <td>${run.start_time}</td>
                    <td><span class="pill">${run.model_type}</span></td>
                    <td>${run.mse === null ? "N/A" : run.mse.toFixed(6)}</td>
                    <td>${run.status}</td>
                </tr>`).join("")
            : '<tr><td colspan="5">No experiment runs found.</td></tr>';

        const registry = data.registry_versions.length
            ? data.registry_versions.map((version) => `
                <div class="stack-item">
                    <small>Version</small>
                    <strong>${version.version}</strong>
                    <div class="badge secondary">${version.stage}</div>
                </div>`).join("")
            : '<div class="stack-item muted">No registered versions yet. Saved local bundles are still powering the dashboard forecasts.</div>';

        function miniCard(title, card, variant) {
            return `
                <div class="card mini ${variant}">
                    <div class="kicker" style="background: rgba(255,255,255,0.14); color: white;">${card.source_label}</div>
                    <h3>${title}</h3>
                    <div class="mini-value">$ ${card.forecast}</div>
                    <div class="metric-grid two">
                        <div class="metric"><small>Move</small><strong>${card.delta_pct}</strong></div>
                        <div class="metric"><small>Change</small><strong>$${card.change_amount}</strong></div>
                    </div>
                    <p>${card.status}</p>
                    <p>Last check error: $${card.validation.error}</p>
                    <p>Updated: ${card.updated_at}</p>
                </div>`;
        }

        root.className = "";
        root.innerHTML = `
            <section class="panel context-grid">
                <div class="context-item"><small>Data Source</small><strong>${data.data_context.data_source}</strong><div class="muted">${data.data_context.symbol} | ${data.data_context.data_frequency}</div></div>
                <div class="context-item"><small>Coverage</small><strong>${data.data_context.coverage_start}</strong><div class="muted">to ${data.data_context.coverage_end}</div></div>
                <div class="context-item"><small>Latest Market Date</small><strong>${data.data_context.latest_market_time}</strong></div>
                <div class="context-item"><small>Dashboard Refreshed</small><strong>${data.data_context.dashboard_time}</strong></div>
            </section>
            <section class="section grid-2">
                <div class="card hero">
                    <div class="kicker" style="background: rgba(255,255,255,0.14); color: white;">${active.source_label} Active Model</div>
                    <h3>${active.forecast_horizon} Forecast</h3>
                    <div class="hero-value">$ ${active.forecast}</div>
                    <div>Latest hourly close: $ ${active.latest_close}</div>
                    <div class="metric-grid">
                        <div class="metric"><small>Predicted Move</small><strong>${active.delta_pct}</strong></div>
                        <div class="metric"><small>Change vs Close</small><strong>$${active.change_amount}</strong></div>
                        <div class="metric"><small>Bundle Updated</small><strong>${active.updated_at}</strong></div>
                    </div>
                    <p>Last completed check: predicted $${active.validation.prediction} vs actual $${active.validation.actual} | abs error $${active.validation.error}</p>
                </div>
                <div class="grid-2">
                    ${miniCard(`RNN ${data.forecast_horizon}`, data.forecast_cards.rnn, "dark")}
                    ${miniCard(`ARIMA ${data.forecast_horizon}`, data.forecast_cards.arima, "brown")}
                </div>
            </section>
            <section class="section grid-2">
                ${miniCard(`Linear ${data.forecast_horizon}`, data.forecast_cards.linear, "dark")}
                <div class="card mini green">
                    <div class="kicker" style="background: rgba(255,255,255,0.14); color: white;">Model Quality</div>
                    <h3>Best Model MSE</h3>
                    <div class="mini-value">${data.best_model_metric}</div>
                    <div class="metric-grid two">
                        <div class="metric"><small>Top Model</small><strong>${data.best_model_name}</strong></div>
                        <div class="metric"><small>Interpretation</small><strong>Lower is better</strong></div>
                    </div>
                    <p>Best tracked run across available model families.</p>
                </div>
            </section>
            <section class="section grid-2">
                <div class="panel">
                    <div class="section-title">
                        <h3>Best Run Per Model</h3>
                        <p>One top tracked run for each model family so comparisons stay balanced.</p>
                    </div>
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr><th>Run ID</th><th>Start Time</th><th>Model Type</th><th>MSE</th><th>Status</th></tr>
                            </thead>
                            <tbody>${runRows}</tbody>
                        </table>
                    </div>
                </div>
                <div class="panel">
                    <div class="section-title">
                        <h3>Model Registry Status</h3>
                        <p>Tracked versions currently visible from MLflow registration.</p>
                    </div>
                    <div class="table-wrap stack">${registry}</div>
                </div>
            </section>`;
    } catch (error) {
        root.className = "empty";
        root.textContent = `Failed to load overview data: ${error.message}`;
    }
});
