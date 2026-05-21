# Security Policy

## Supported Versions

Use this section to tell people about which versions of your project are
currently being supported with security updates.

| Version | Status |
| :--- | :--- |
| 5.0.x (CVS-3.0) | :white_check_mark: |
| < 5.0.0 | :x:                |

## Privacy-First Security

AI Friend is designed with **Sovereign Privacy** as a core architectural requirement:
- **Local Inference**: Default configurations use Ollama and local TTS to ensure no voice or reasoning data leaves your network.
- **Air-Gapped Ready**: The system is designed to function without external internet access once models are cached.
- **Binary Audio Transport**: Audio payloads are transported over the LAN mesh via strict binary PCM `orjson` serialization, effectively mitigating plain-text JSON network sniffing.
- **No Data Harvesting**: We do not collect telemetry or conversation logs.

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability, please follow these steps:

1.  **Do NOT create a public GitHub issue.** Global visibility of an exploit before a patch is ready puts all users at risk.
2.  Email the security team at **aniketsahaworkspace@gmail.com** or open a **Private Advisory** on GitHub.
3.  Include a detailed description of the vulnerability, steps to reproduce, and potential impact.

### Response Timeline
-   **Acknowledgement**: Within 48 hours.
-   **Assessment**: Within 1 week.
-   **Fix**: As soon as possible, prioritized by severity.

Thank you for helping keep AI Friend safe! 🛡️
