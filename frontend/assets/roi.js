document.addEventListener("DOMContentLoaded", async () => {
    document.body.innerHTML = createAppShell(
        "roi",
        { kicker: "Business Impact View", heading: "ROI & Strategy Performance" },
        "This page converts hourly forecasts into actual trade decisions, charges friction, and ranks models by money made, drawdown avoided, and execution quality."
    );

    const root = document.getElementById("page-root");

    try {
        const data = await fetchJson("/api/roi/");
        if (!data.best_strategy) {
            root.className = "empty";
            root.textContent = "No ROI simulation is available yet. Generate the hourly model bundles first, then reload this page.";
            return;
        }

        const best = data.best_strategy;
        const historyMarkup = data.history.length
            ? data.history.map((entry) => `
                <div class="stack-item">
                    <strong>${entry.model_version}</strong>
                    <div class="muted">Profit: $${formatMoney(entry.simulated_profit_usd)} | Risk reduction: ${entry.risk_reduction_pct.toFixed(1)}%</div>
                    <div class="muted">${entry.period} | ${entry.calculated_at}</div>
                </div>`).join("")
            : '<div class="stack-item muted">No snapshots yet.</div>';

        const strategyRows = data.strategies.map((strategy) => `
            <tr>
                <td><strong>${strategy.model_name}</strong></td>
                <td>${strategy.source_label}</td>
                <td>$${formatMoney(strategy.net_profit_usd)}</td>
                <td>${strategy.return_pct.toFixed(2)}%</td>
                <td>$${formatMoney(strategy.benchmark_profit_usd)}</td>
                <td>${strategy.max_drawdown_pct.toFixed(2)}%</td>
                <td>${strategy.model_threshold_pct.toFixed(3)}%</td>
                <td>${strategy.trades}</td>
                <td>${strategy.long_trades}L / ${strategy.short_trades}S</td>
                <td>${strategy.latest_signal}</td>
            </tr>`).join("");

        root.className = "";
        root.innerHTML = `
            <section class="panel context-grid">
                <div class="context-item"><small>Replay Window</small><strong>${best.window_start} to ${best.window_end}</strong></div>
                <div class="context-item"><small>Initial Capital</small><strong>$${formatMoney(data.assumptions.capital)}</strong></div>
                <div class="context-item"><small>Trade Gate</small><strong>${data.assumptions.threshold_pct.toFixed(2)}% move threshold</strong></div>
                <div class="context-item"><small>Market Coverage</small><strong>${data.context_data.coverage_start || "N/A"} to ${data.context_data.coverage_end || "N/A"}</strong></div>
            </section>
            <section class="section grid-2">
                <div class="card hero">
                    <div class="kicker" style="background: rgba(255,255,255,0.14); color: white;">Top Replay Outcome</div>
                    <h3>${best.model_name}</h3>
                    <div class="hero-value">$${formatMoney(best.net_profit_usd)}</div>
                    <p>${data.recommendation.summary}</p>
                    <div class="metric-grid">
                        <div class="metric"><small>Return</small><strong>${best.return_pct.toFixed(2)}%</strong></div>
                        <div class="metric"><small>Risk Reduction</small><strong>${best.risk_reduction_pct.toFixed(1)}%</strong></div>
                        <div class="metric"><small>Win Rate</small><strong>${best.win_rate_pct.toFixed(1)}%</strong></div>
                    </div>
                </div>
                <div class="stack">
                    <div class="panel table-wrap"><small>Recommendation</small><h3>${data.recommendation.title}</h3><p>${data.recommendation.summary}</p><div class="badge warning">${data.recommendation.confidence_label}</div></div>
                    <div class="panel table-wrap"><small>Benchmark Gap</small><h3>$${formatMoney(best.profit_vs_benchmark_usd)}</h3><div class="muted">Difference versus buy-and-hold.</div></div>
                    <div class="panel table-wrap"><small>Signal Accuracy</small><h3>${best.signal_accuracy_pct.toFixed(1)}%</h3><div class="muted">Directional hit rate on executed trades.</div></div>
                </div>
            </section>
            <section class="section panel">
                <div class="section-title">
                    <h3>Model Leaderboard</h3>
                    <p>Money after fees matters more than raw MSE here.</p>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr><th>Model</th><th>Style</th><th>Net Profit</th><th>Return</th><th>Benchmark</th><th>Drawdown</th><th>Gate</th><th>Trades</th><th>Signal Mix</th><th>Current Bias</th></tr>
                        </thead>
                        <tbody>${strategyRows}</tbody>
                    </table>
                </div>
            </section>
            <section class="section grid-2">
                <div class="panel">
                    <div class="section-title">
                        <h3>Minimal assumptions, useful output</h3>
                        <p>The goal is not a perfect backtest. The goal is a fast and honest read on whether the forecast can survive a simple rule.</p>
                    </div>
                    <div class="table-wrap stack">
                        <div class="stack-item"><strong>Decision rule</strong><div class="muted">Each model uses a confidence gate based on the larger of a ${data.assumptions.threshold_pct.toFixed(2)}% floor or its own ${data.assumptions.signal_quantile_pct.toFixed(0)}th-percentile predicted move.</div></div>
                        <div class="stack-item"><strong>Execution friction</strong><div class="muted">Each active trade pays ${data.assumptions.fee_pct.toFixed(2)}% in simulated cost.</div></div>
                        <div class="stack-item"><strong>Why this page matters</strong><div class="muted">It separates forecasting quality from decision quality by testing whether signals survive simple execution rules.</div></div>
                    </div>
                </div>
                <div class="panel">
                    <div class="section-title">
                        <h3>Best-strategy history</h3>
                        <p>Recent saved winners for a simple audit trail.</p>
                    </div>
                    <div class="table-wrap stack">${historyMarkup}</div>
                </div>
            </section>`;
    } catch (error) {
        root.className = "empty";
        root.textContent = `Failed to load ROI data: ${error.message}`;
    }
});
