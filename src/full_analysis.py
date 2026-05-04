import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

ECC_FILE = "ecc_results.csv"
KYBER_FILE = "kyber_results.csv"

OUTPUT_DIR = Path("analysis_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

FINAL_DATASET = OUTPUT_DIR / "final_combined_dataset.csv"
SUMMARY_TABLE = OUTPUT_DIR / "summary_statistics.csv"
SUCCESS_TABLE = OUTPUT_DIR / "success_rates.csv"
FAILURE_CLIFF_TABLE = OUTPUT_DIR / "failure_cliff_points.csv"
JSI_TABLE = OUTPUT_DIR / "jitter_sensitivity_index.csv"

FAILURE_THRESHOLD = 90.0  # proposal definition: success rate below 90%


# ============================================================
# LOAD + CLEAN DATA
# ============================================================

ecc = pd.read_csv(ECC_FILE)
kyber = pd.read_csv(KYBER_FILE)

data = pd.concat([ecc, kyber], ignore_index=True)

# Ensure numeric columns are numeric
numeric_cols = [
    "packet_loss_percent",
    "base_delay_ms",
    "jitter_ms",
    "trial_number",
    "success",
    "handshake_time_ms"
]

for col in numeric_cols:
    data[col] = pd.to_numeric(data[col], errors="coerce")

# Remove invalid rows
data = data.dropna(subset=["algorithm", "packet_loss_percent", "jitter_ms", "success", "handshake_time_ms"])

# Save combined dataset
data.to_csv(FINAL_DATASET, index=False)

print(f"[OK] Combined dataset saved to: {FINAL_DATASET}")
print(f"[INFO] Total rows: {len(data)}")
print(data["algorithm"].value_counts())


# ============================================================
# SUMMARY STATISTICS
# ============================================================

summary = (
    data.groupby(["algorithm", "packet_loss_percent", "jitter_ms"])
    .agg(
        trials=("success", "count"),
        success_rate_percent=("success", lambda x: x.mean() * 100),
        mean_ms=("handshake_time_ms", "mean"),
        median_ms=("handshake_time_ms", "median"),
        std_ms=("handshake_time_ms", "std"),
        min_ms=("handshake_time_ms", "min"),
        max_ms=("handshake_time_ms", "max"),
        p95_ms=("handshake_time_ms", lambda x: x.quantile(0.95))
    )
    .reset_index()
)

summary.to_csv(SUMMARY_TABLE, index=False)
print(f"[OK] Summary statistics saved to: {SUMMARY_TABLE}")


# ============================================================
# SUCCESS RATE + FAILURE CLIFF
# ============================================================

success_rates = (
    data.groupby(["algorithm", "packet_loss_percent"])
    .agg(
        trials=("success", "count"),
        success_rate_percent=("success", lambda x: x.mean() * 100)
    )
    .reset_index()
)

success_rates.to_csv(SUCCESS_TABLE, index=False)
print(f"[OK] Success rates saved to: {SUCCESS_TABLE}")

failure_cliffs = []

for algo in success_rates["algorithm"].unique():
    subset = success_rates[success_rates["algorithm"] == algo].sort_values("packet_loss_percent")
    below = subset[subset["success_rate_percent"] < FAILURE_THRESHOLD]

    if len(below) > 0:
        cliff = below.iloc[0]["packet_loss_percent"]
        note = f"Failure cliff reached at {cliff}% packet loss"
    else:
        cliff = None
        note = "Failure cliff not reached within tested range"

    failure_cliffs.append({
        "algorithm": algo,
        "failure_threshold_percent": FAILURE_THRESHOLD,
        "failure_cliff_packet_loss_percent": cliff,
        "note": note
    })

failure_cliff_df = pd.DataFrame(failure_cliffs)
failure_cliff_df.to_csv(FAILURE_CLIFF_TABLE, index=False)
print(f"[OK] Failure cliff table saved to: {FAILURE_CLIFF_TABLE}")


# ============================================================
# JITTER SENSITIVITY INDEX
# ============================================================
# Definition:
# JSI = mean handshake time at jitter J / mean handshake time at jitter 0
# Computed per algorithm and packet loss level.

jitter_mean = (
    data.groupby(["algorithm", "packet_loss_percent", "jitter_ms"])
    .agg(mean_ms=("handshake_time_ms", "mean"))
    .reset_index()
)

jsi_rows = []

for algo in jitter_mean["algorithm"].unique():
    for loss in sorted(jitter_mean["packet_loss_percent"].unique()):
        subset = jitter_mean[
            (jitter_mean["algorithm"] == algo) &
            (jitter_mean["packet_loss_percent"] == loss)
        ]

        base_row = subset[subset["jitter_ms"] == 0]

        if len(base_row) == 0:
            continue

        base_mean = base_row.iloc[0]["mean_ms"]

        for _, row in subset.iterrows():
            jsi = row["mean_ms"] / base_mean if base_mean != 0 else None

            jsi_rows.append({
                "algorithm": algo,
                "packet_loss_percent": loss,
                "jitter_ms": row["jitter_ms"],
                "baseline_jitter_0_mean_ms": base_mean,
                "mean_ms": row["mean_ms"],
                "JSI": jsi
            })

jsi_df = pd.DataFrame(jsi_rows)
jsi_df.to_csv(JSI_TABLE, index=False)
print(f"[OK] Jitter Sensitivity Index saved to: {JSI_TABLE}")


# ============================================================
# HELPER PLOT FUNCTION
# ============================================================

def save_line_plot(df, x, y, group, title, xlabel, ylabel, filename):
    plt.figure(figsize=(9, 6))

    for label in df[group].unique():
        subset = df[df[group] == label].sort_values(x)
        plt.plot(subset[x], subset[y], marker="o", label=label)

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=300)
    plt.close()

    print(f"[OK] Saved graph: {filename}")


# ============================================================
# GRAPH 1: FAILURE CLIFF GRAPH
# ============================================================

plt.figure(figsize=(9, 6))

for algo in success_rates["algorithm"].unique():
    subset = success_rates[success_rates["algorithm"] == algo].sort_values("packet_loss_percent")
    plt.plot(
        subset["packet_loss_percent"],
        subset["success_rate_percent"],
        marker="o",
        label=algo
    )

plt.axhline(y=90, linestyle="--", label="90% Failure Threshold")
plt.title("Failure Cliff: Success Rate vs Packet Loss")
plt.xlabel("Packet Loss (%)")
plt.ylabel("Success Rate (%)")
plt.ylim(0, 105)
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "01_failure_cliff_success_rate.png", dpi=300)
plt.close()

print("[OK] Saved graph: 01_failure_cliff_success_rate.png")


# ============================================================
# GRAPH 2: AVERAGE HANDSHAKE TIME VS PACKET LOSS
# ============================================================

avg_loss = (
    data.groupby(["algorithm", "packet_loss_percent"])
    .agg(mean_ms=("handshake_time_ms", "mean"))
    .reset_index()
)

save_line_plot(
    avg_loss,
    x="packet_loss_percent",
    y="mean_ms",
    group="algorithm",
    title="Average Handshake Time vs Packet Loss",
    xlabel="Packet Loss (%)",
    ylabel="Average Handshake Time (ms)",
    filename="02_avg_handshake_vs_packet_loss.png"
)


# ============================================================
# GRAPH 3: STANDARD DEVIATION VS PACKET LOSS
# ============================================================

std_loss = (
    data.groupby(["algorithm", "packet_loss_percent"])
    .agg(std_ms=("handshake_time_ms", "std"))
    .reset_index()
)

save_line_plot(
    std_loss,
    x="packet_loss_percent",
    y="std_ms",
    group="algorithm",
    title="Handshake Variability vs Packet Loss",
    xlabel="Packet Loss (%)",
    ylabel="Standard Deviation (ms)",
    filename="03_stddev_vs_packet_loss.png"
)


# ============================================================
# GRAPH 4: WORST-CASE HANDSHAKE TIME VS PACKET LOSS
# ============================================================

max_loss = (
    data.groupby(["algorithm", "packet_loss_percent"])
    .agg(max_ms=("handshake_time_ms", "max"))
    .reset_index()
)

save_line_plot(
    max_loss,
    x="packet_loss_percent",
    y="max_ms",
    group="algorithm",
    title="Worst-Case Handshake Time vs Packet Loss",
    xlabel="Packet Loss (%)",
    ylabel="Maximum Handshake Time (ms)",
    filename="04_worst_case_vs_packet_loss.png"
)


# ============================================================
# GRAPH 5: 95TH PERCENTILE VS PACKET LOSS
# ============================================================

p95_loss = (
    data.groupby(["algorithm", "packet_loss_percent"])
    .agg(p95_ms=("handshake_time_ms", lambda x: x.quantile(0.95)))
    .reset_index()
)

save_line_plot(
    p95_loss,
    x="packet_loss_percent",
    y="p95_ms",
    group="algorithm",
    title="95th Percentile Handshake Time vs Packet Loss",
    xlabel="Packet Loss (%)",
    ylabel="95th Percentile Handshake Time (ms)",
    filename="05_p95_vs_packet_loss.png"
)


# ============================================================
# GRAPH 6: AVERAGE HANDSHAKE TIME VS JITTER
# ============================================================

avg_jitter = (
    data.groupby(["algorithm", "jitter_ms"])
    .agg(mean_ms=("handshake_time_ms", "mean"))
    .reset_index()
)

save_line_plot(
    avg_jitter,
    x="jitter_ms",
    y="mean_ms",
    group="algorithm",
    title="Average Handshake Time vs Jitter",
    xlabel="Jitter (ms)",
    ylabel="Average Handshake Time (ms)",
    filename="06_avg_handshake_vs_jitter.png"
)


# ============================================================
# GRAPH 7: STANDARD DEVIATION VS JITTER
# ============================================================

std_jitter = (
    data.groupby(["algorithm", "jitter_ms"])
    .agg(std_ms=("handshake_time_ms", "std"))
    .reset_index()
)

save_line_plot(
    std_jitter,
    x="jitter_ms",
    y="std_ms",
    group="algorithm",
    title="Handshake Variability vs Jitter",
    xlabel="Jitter (ms)",
    ylabel="Standard Deviation (ms)",
    filename="07_stddev_vs_jitter.png"
)


# ============================================================
# GRAPH 8: JITTER SENSITIVITY INDEX
# ============================================================

# Average JSI across packet loss values for a simple final graph
jsi_avg = (
    jsi_df.groupby(["algorithm", "jitter_ms"])
    .agg(JSI=("JSI", "mean"))
    .reset_index()
)

save_line_plot(
    jsi_avg,
    x="jitter_ms",
    y="JSI",
    group="algorithm",
    title="Jitter Sensitivity Index (JSI)",
    xlabel="Jitter (ms)",
    ylabel="Relative Mean Latency Increase",
    filename="08_jitter_sensitivity_index.png"
)


# ============================================================
# GRAPH 9: OVERALL BOXPLOT
# ============================================================

plt.figure(figsize=(8, 6))

algorithms = sorted(data["algorithm"].unique())
box_data = [data[data["algorithm"] == algo]["handshake_time_ms"] for algo in algorithms]

plt.boxplot(box_data, labels=algorithms)
plt.title("Handshake Time Distribution: ECC vs Kyber")
plt.ylabel("Handshake Time (ms)")
plt.grid(True)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "09_boxplot_overall_ecc_vs_kyber.png", dpi=300)
plt.close()

print("[OK] Saved graph: 09_boxplot_overall_ecc_vs_kyber.png")


# ============================================================
# GRAPH 10: BOXPLOTS PER PACKET LOSS
# ============================================================

for loss in sorted(data["packet_loss_percent"].unique()):
    subset = data[data["packet_loss_percent"] == loss]

    plt.figure(figsize=(8, 6))
    box_data = [
        subset[subset["algorithm"] == algo]["handshake_time_ms"]
        for algo in algorithms
    ]

    plt.boxplot(box_data, labels=algorithms)
    plt.title(f"Handshake Time Distribution at {loss}% Packet Loss")
    plt.ylabel("Handshake Time (ms)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"10_boxplot_packet_loss_{loss}.png", dpi=300)
    plt.close()

print("[OK] Saved packet-loss boxplots")


# ============================================================
# GRAPH 11: BOXPLOTS PER JITTER LEVEL
# ============================================================

for jitter in sorted(data["jitter_ms"].unique()):
    subset = data[data["jitter_ms"] == jitter]

    plt.figure(figsize=(8, 6))
    box_data = [
        subset[subset["algorithm"] == algo]["handshake_time_ms"]
        for algo in algorithms
    ]

    plt.boxplot(box_data, labels=algorithms)
    plt.title(f"Handshake Time Distribution at {jitter} ms Jitter")
    plt.ylabel("Handshake Time (ms)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"11_boxplot_jitter_{jitter}.png", dpi=300)
    plt.close()

print("[OK] Saved jitter boxplots")


# ============================================================
# FINAL PRINT SUMMARY
# ============================================================

print("\n========== FINAL SUMMARY ==========")
print("\nFailure Cliff:")
print(failure_cliff_df.to_string(index=False))

print("\nAverage JSI:")
print(jsi_avg.to_string(index=False))

print("\nAll outputs saved in folder:")
print(OUTPUT_DIR)
