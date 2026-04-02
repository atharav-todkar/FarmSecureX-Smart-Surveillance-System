# 6. Hardware Design

## 6.1 Overview

The hardware design of the FarmSecureX system is based on a modular and low-cost architecture suitable for rural deployment. The system integrates sensing, processing, communication, and power modules to ensure reliable theft detection and alert generation.

---

## 6.2 Components Used

| Component            | Description                                     |
| -------------------- | ----------------------------------------------- |
| Raspberry Pi Pico W  | Main microcontroller for processing and control |
| GSM Module           | Sends SMS alerts to the user                    |
| GPS Module           | Provides real-time location tracking            |
| Gyroscope Sensor     | Detects motor movement                          |
| MAX485 Module        | Ensures reliable long-distance communication    |
| ESP32-CAM            | Captures images during theft                    |
| Battery              | Provides backup power                           |
| Power Supply Circuit | Regulates voltage for system operation          |

---

## 6.3 Component Description

### Raspberry Pi Pico W

Acts as the central controller. It generates coded pulses, monitors signals, and processes sensor inputs.

---

### GSM Module

Used for sending real-time alerts via SMS or call notifications.

---

### GPS Module

Provides accurate geographical location for tracking the stolen motor.

---

### Gyroscope Sensor

Detects tilt, vibration, and movement of the motor for theft classification.

---

### MAX485 Module

Enables robust communication over long distances with noise immunity.

---

### ESP32-CAM

Captures images during theft events, providing visual evidence.

---

### Power System

Includes battery backup and optional solar support for uninterrupted operation.

---

## 6.4 Bill of Materials (BOM)

| Component           | Quantity | Approx Cost (INR) |
| ------------------- | -------- | ----------------- |
| Raspberry Pi Pico W | 1        | 400               |
| GSM Module          | 1        | 300               |
| GPS Module          | 1        | 400               |
| Gyroscope Sensor    | 1        | 150               |
| MAX485 Module       | 2        | 100               |
| ESP32-CAM           | 1        | 500               |
| Battery             | 1        | 300               |
| Miscellaneous       | -        | 300               |

**Total Estimated Cost: ~ 2450 INR**

---

## 6.5 Design Considerations

* Low-cost design for rural affordability
* Low power consumption
* Noise-resistant communication
* Modular architecture for easy maintenance
* Scalability for future upgrades

---
