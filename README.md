
Conversation with Gemini
convert this to a readme for github

Your Markdown (README.md) file is ready:
MD icon
README
 MD 
Open

I have converted the graduation project proposal into a comprehensive README.md formatted specifically for a GitHub repository.

Here is a brief summary of the information included in the repository documentation based on the provided PDF:


Project Details: The project is from the School of Engineering and Natural Sciences at Istanbul Medipol University. It is being developed by team members Maria Riham Boukerou and Abdallah I.F. Yaish, under the supervision of advisor Malik Geylani.  
PDF
+ 2


Core Concept: The PASS-PAC (Portable Physical Access Security Assessment Platform) is designed for the authorized testing of RFID and NFC cards.  
PDF


Workflow: The system integrates hardware and software to capture credentials, identify protocols, perform vulnerability analysis, and handle reporting.  
PDF


Target Audience: The tool aims to provide an affordable and easy-to-use alternative to existing complex tools, directly assisting security professionals and red teams with physical access penetration testing.  
PDF
+ 1




Gemini is AI and can make mistakes.

# PASS-PAC: Portable Physical Access Security Assessment Platform

![Institution](https://img.shields.io/badge/Institution-Istanbul%20Medipol%20University-red)
![Course](https://img.shields.io/badge/Course-Graduation%20Project%202025--2026-blue)
![Status](https://img.shields.io/badge/Status-Phase%201%20(Software%20Prototype)-brightgreen)

## Project Overview
**PASS-PAC** (Portable Physical Access Security Assessment Platform) is an integrated system designed for the authorized security assessment of RFID and NFC-based physical access control systems. 

The credential at the entrance remains a weak spot in current security systems, often relying on inadequate authentication measures vulnerable to replication. While powerful tools for RFID/NFC analysis exist (like Proxmark3 or Flipper Zero), they can be overly complex, tethered, or closed-ecosystem. PASS-PAC bridges this gap by offering a portable, easy-to-use, and low-cost solution tailored for security professionals, red teams, and penetration testers.

## Key Features
* **Integrated Workflow:** Consolidates credential collection, protocol identification, vulnerability assessment, evidence logging, and reporting into a single process.
* **Multi-Protocol Support:** Capable of assessing both Low Frequency (LF RFID 125 kHz) and High Frequency (HF/NFC 13.56 MHz) credentials.
* **Structured Assessment & Logging:** Features a local dashboard for managing assessment sessions, simulating scans, classifying data by risk level, and generating operator recommendations.
* **Portability & Covert Deployment:** Designed for real-world red-team operations.
* **Modular Architecture:** Built using a Raspberry Pi main compute board with dedicated HF/NFC and LF reader paths.

## System Architecture
The hardware operates via a centralized Power Node supplying all main components:
1.  **HF / NFC Path:** Captures 13.56 MHz credentials.
2.  **LF Reader Path:** Captures legacy 125 kHz credentials.
3.  **Main Compute Board:** A Raspberry Pi handles processing, protocol analysis, and risk evaluation.
4.  **Display Interface:** Provides a basic local UI for visible results.
5.  **Local Storage & Logging:** Securely saves session data and test events.

### Assessment Workflow
`RFID/NFC Card` ➔ `PASS-PAC Device` ➔ `Credential Capture` ➔ `Protocol Analysis` ➔ `Risk Evaluation` ➔ `Results & Logging`

## Project Scope & Boundaries
* **Scope:** RFID/NFC security assessment, credential analysis, vulnerability identification, and structured logging/reporting.
* **Boundaries:** The device is strictly intended for **authorized** testing environments, educational, and security auditing purposes. Advanced cryptographic breaking is out of scope.

## Current Status (Phase 1)
The project is currently utilizing simulated datasets and publicly accessible RFID/NFC data to design and test the software architecture.
* ✅ Local dashboard and session management implemented.
* ✅ Simulation of RFID/NFC scans for LF and HF technologies (EM4100, T5577, MIFARE Classic, NTAG).
* ✅ Risk level classification and evidence logging functional.
* ⏳ **Next Phase (Project II):** Integration with actual hardware components (Proxmark3 Easy 512K, Raspberry Pi) and validation via physical test cards.

## Team Members
* **Abdallah I.F. Yaish** (Group Representative)
* **Maria Riham Boukerou**
* **Project Advisor:** Malik Geylani

*School of Engineering and Natural Sciences, Istanbul Medipol University*
README.md
Displaying README.md.
