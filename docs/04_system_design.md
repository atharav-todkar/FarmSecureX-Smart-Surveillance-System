# 4. System Design

## 4.1 Overview

The FarmSecureX system is designed as a smart surveillance framework to detect agricultural motor and copper cable theft using a combination of embedded hardware, sensing mechanisms, and communication modules. The system ensures continuous monitoring, real-time detection, and instant alert generation in case of tampering.

The design focuses on reliability, low power consumption, and suitability for rural environments where continuous monitoring and power availability are major challenges.

---

## 4.2 Block Diagram

![Block Diagram](./block_diagram.png)

---

## 4.3 System Components

### 1. Continuity Signal Generator

A coded low-voltage signal is generated and transmitted through the motor cable. This signal acts as a reference to continuously verify the integrity of the cable.

---

### 2. Communication Interface (MAX485 Module)

The MAX485 module is used for reliable signal transmission over long distances. It ensures noise-resistant communication between the signal generator and the monitoring unit.

---

### 3. Microcontroller (Raspberry Pi Pico W)

The microcontroller acts as the central processing unit of the system. It generates coded pulses, monitors signal continuity, processes sensor data, and controls alert mechanisms.

---

### 4. Gyroscope Sensor

The gyroscope is used to detect motion, tilt, or vibration of the motor. It plays a key role in distinguishing between different theft scenarios.

---

### 5. GSM Module

The GSM module is responsible for sending real-time alerts to the user through SMS or call notifications.

---

### 6. GPS Module

The GPS module provides real-time location tracking of the motor, enabling recovery in case of theft.

---

### 7. ESP32-CAM Module

The ESP32-CAM captures images during theft events, providing visual evidence and enhancing security.

---

### 8. Power Supply and Backup

A rechargeable battery backup system ensures uninterrupted operation even during power outages. Optional solar support can be integrated for remote areas.

---

## 4.4 System Workflow

![Workflow Diagram](./workflow_diagram.jpeg)

---

## 4.5 Working Principle

The system operates by continuously transmitting a coded signal through the motor cable and monitoring its integrity.

* If the coded pulses are received correctly, the system remains in a normal (idle) state
* If the pulses are not received, the system detects cable tampering

Once tampering is detected, the system checks the gyroscope sensor:

* If motor movement is detected → Motor and cable theft
* If no movement is detected → Only cable theft

After classification, the system sends alerts via GSM along with GPS location and optionally captured images.

---

## 4.6 Design Advantages

* Reliable detection using coded continuity signals
* Noise-resistant communication using MAX485
* Accurate theft classification using gyroscope
* Real-time alerts and tracking
* Low-cost and scalable design
* Suitable for rural and remote environments

---
