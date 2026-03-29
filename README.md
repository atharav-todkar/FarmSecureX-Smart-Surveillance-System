# 🌾 Smart Surveillance Framework for Agriculture Motor and Copper Cable Theft Detection

## 🚀 FarmSecureX – Smart Surveillance System

FarmSecureX is an intelligent, low-cost surveillance and protection system designed to prevent **agricultural motor and copper cable theft** in remote rural environments. The system provides **real-time monitoring, instant alerts, and location tracking**, ensuring continuous protection of critical farm infrastructure.

---

## 🎯 Problem Statement

Agricultural motors and copper cables installed in remote farms are highly vulnerable to theft due to lack of monitoring and security. This results in:

* Significant financial losses
* Irrigation downtime
* Reduced crop productivity
* Increased maintenance costs

There is a need for a **reliable, affordable, and scalable smart surveillance solution** tailored for rural environments.

---

## 💡 Proposed Solution

FarmSecureX introduces a **coded continuity-based sensing mechanism** using a Raspberry Pi Pico W to detect cable tampering with high reliability.

The system integrates:

* 📡 GSM module for real-time alerts
* 📍 GPS module for location tracking
* ⚙️ Gyroscope sensor for motion detection
* 📷 Camera module for visual evidence

It accurately distinguishes between:

* Cable theft
* Motor + cable theft

A **battery backup with solar support** ensures uninterrupted 24/7 operation even in off-grid conditions.

---

## 🔑 Key Features

* 🔐 Coded continuity signal-based detection (UART-free architecture)
* ⚡ Real-time GSM alert system
* 📍 GPS-based tracking for recovery
* 🧠 Smart theft classification using gyroscope
* 🔋 Battery backup with solar charging
* 📷 Evidence capture using camera module
* 💰 Low-cost and scalable design

---

## 🧠 System Architecture

![Block Diagram](docs/block_diagram.png)

---

## ⚙️ Working Principle

1. Raspberry Pi Pico W generates coded pulses every 200 ms
2. Pulses travel through motor cable (low-voltage path)
3. If cable is intact → signal verified
4. If cable is cut → signal loss detected
5. Gyroscope checks motor movement
6. System classifies theft type
7. GSM sends alert + GPS location to farmer

---

## 🏗️ Hardware Components

* Raspberry Pi Pico W
* GSM Module
* GPS Module
* Gyroscope Sensor
* Camera Module
* Rechargeable Battery System

---

## 🔬 Methodology

The system uses a **coded low-voltage pulse technique** instead of conventional communication protocols. This improves:

* Noise immunity
* Reliability in rural environments
* Detection accuracy

Any disturbance in the coded signal is immediately detected as a tampering event.

---

## 📊 Expected Outcomes

* ✅ Reliable theft detection system
* ✅ Instant alert and response capability
* ✅ Accurate classification of theft scenarios
* ✅ Improved asset recovery using GPS
* ✅ Continuous monitoring during power failure

---

## 🌍 Applications

* Agricultural irrigation systems
* Rural farm installations
* Streetlight cable protection
* Railway signaling systems
* Power distribution networks
* Industrial motor protection

---

## 📈 Commercial Viability

* Over **20 million irrigation pump sets in India**
* High demand in theft-prone rural areas
* Affordable alternative to CCTV and manual security
* Scalable to infrastructure protection systems

---

## 🧑‍💻 Team

* Atharav Ramchandra Todkar
* Pranav Chandrakant Mirje
* Om Suhas Patil
* Aniruddha Prakash More

---

## 📂 Project Structure

```
FarmSecureX/
│── docs/
│── hardware/
│── software/
│── results/
│── media/
```

---

## 🔮 Future Scope

* 🌐 IoT-based remote dashboard
* 🤖 AI-based theft prediction
* ☁️ Cloud integration for monitoring
* 📱 Mobile application support

---

## 📜 License

This project is licensed under the MIT License.

---

## 📬 Contact

For collaborations, research opportunities, or queries, feel free to connect via GitHub.

---

⭐ If you find this project useful, consider giving it a star!
