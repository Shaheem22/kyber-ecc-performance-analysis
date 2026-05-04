# Post-Quantum Cryptography Performance Analysis for IoT — Kyber vs ECC

> **Course:** Wireless and Mobile Security (CY315) | GIKI  
> **Team:** Muhammad Shaheem + teammates  
> **Status:** Complete

---

## Overview

This project benchmarks **Kyber (post-quantum)** against **ECC (classical)** cryptographic handshakes in simulated IoT network conditions. Using MQTT over TLS, we tested both algorithms across varying levels of packet loss and jitter to evaluate their real-world viability in constrained wireless environments.

The motivation: as quantum computing threatens classical cryptography, **Kyber** (a NIST-standardized post-quantum KEM) is a candidate replacement for ECC in IoT security. But does it hold up under degraded network conditions? This project answers that empirically.

---

## Key Findings

- **Both algorithms maintained 100% success rate** across all tested packet loss levels (0–10%) and jitter levels (0–50ms)
- **Kyber was consistently faster** — baseline handshake ~330ms vs ECC's ~590ms under identical conditions
- **ECC showed higher variance** under jitter, with std deviation rising significantly at 20ms and 50ms jitter
- **Neither algorithm hit a failure cliff** within the tested range, suggesting both are robust for typical IoT deployments
- Kyber's lower and more stable handshake times make it a strong candidate for latency-sensitive IoT use cases

---

## Experimental Setup

| Parameter | Values Tested |
|---|---|
| Packet Loss | 0%, 1%, 2%, 3%, 5%, 7%, 10% |
| Jitter | 0ms, 20ms, 50ms |
| Base Delay | 50ms (fixed) |
| Trials per Scenario | 30 |
| Timeout | 5 seconds |
| Protocol | MQTT over TLS (port 8883) |
| Network Emulation | Linux `tc netem` on loopback interface |

---

## Repo Structure

```
├── src/
│   ├── experiment_runner_ecc.py       # ECC_TLS trial runner
│   ├── experiment_runner_kyber.py     # KYBER_TLS trial runner
│   └── full_analysis.py              # Statistical analysis + plot generation
│
├── data/
│   ├── RESULTS-ECC.csv               # Raw ECC trial results
│   ├── RESULTS-KYBER.csv             # Raw Kyber trial results
│   ├── final_combined_dataset.csv    # Merged dataset
│   ├── summary_statistics.csv        # Per-scenario stats (mean, std, p95, etc.)
│   ├── success_rates.csv             # Success rates by algorithm + packet loss
│   ├── failure_cliff_points.csv      # Failure cliff detection output
│   └── jitter_sensitivity_index.csv  # JSI per algorithm
│
├── figures/                          # All generated plots (20 charts)
│
├── report/
│   ├── WAMS_Overleaf.pdf             # Full research report
│   └── WAMS_CY315_Presentation.pptx # Final presentation slides
│
├── .gitignore
└── README.md
```

---

## How to Run

### 1. Install dependencies

```bash
pip install paho-mqtt pandas matplotlib
```

### 2. Run experiments

> **Note:** The experiment runners require a running Mosquitto TLS broker and `sudo` access for `tc netem`. Run on Linux.

```bash
# ECC experiment
sudo python src/experiment_runner_ecc.py

# Kyber experiment
sudo python src/experiment_runner_kyber.py
```

Results are saved to `RESULTS-ECC.csv` and `RESULTS-KYBER.csv`.

### 3. Run analysis

```bash
python src/full_analysis.py
```

Generates all plots into `figures/` and CSVs into `data/`.

---

## Dependencies

- Python 3.8+
- `paho-mqtt` — MQTT client
- `pandas` — data processing
- `matplotlib` — plotting
- Linux `tc` / `netem` — network condition emulation
- Mosquitto broker with TLS configured

---

## Course

Wireless and Mobile Security — CY315  
Ghulam Ishaq Khan Institute of Engineering Sciences and Technology (GIKI)
