# 🛡️Accounts-Enumeration

An advanced timing and payload analysis A/B testing tool designed to detect account enumeration vulnerabilities and state leaks across endpoints.

---

## 🚀 New Features & Updates (v2.0)
* **Advanced Statistical Analysis:** Relies on the Median, Median Absolute Deviation (MAD), and P95 percentiles to ensure result accuracy and reduce noise.
* **Separation Score Evaluation (Sep-Score):** Measures the clarity of timing deviations compared to the baseline noise floor.
* **Visual Representation (Rich UI):** Features colored Sparklines and detailed report matrices built using the `rich` library.
* **Multi-Field Support:** Supports scanning via Email, Username, or Phone fields.
* **Configuration Persistence:** Save and reuse configuration settings seamlessly via a `config.json` file.

---

## 🛠️ Features Overview
* **Endpoint Probing:** Measures response times and payload sizes concurrently with custom sample configurations.
* **Baseline and Target Comparison:** Evaluates fake baselines against target inputs to identify subtle anomalies.
* **Automated Verdict Generation:** Categorizes responses into clear statuses (High Anomaly, Likely Anomaly, or Clean).
* **Lightweight & Clean:** Built with efficient Python code utilizing `httpx` and `rich`.

## Prerequisites
Ensure you have Python installed on your system. The tool requires the following Python libraries:
* `httpx`
* `rich`

## Disclaimer
This tool is created for educational purposes, authorized security assessments, and Bug Bounty programs only.
The developer assumes no liability and is not responsible for any misuse or damage caused by this program.
Use responsibly and only on targets you have explicit permission to test.


## ⭐ Support

If you find this tool useful, please consider giving it a **star** ⭐ on GitHub — it helps others discover the project !
