# 8. Code Architecture and Explanation

## 8.1 Overview

The FarmSecureX system software is divided into modular components to ensure scalability, maintainability, and clarity. The implementation is based on embedded programming using the Raspberry Pi Pico W.

---

## 8.2 Main System Code

The main system integrates multiple functionalities:

* Wire continuity detection using coded signals
* GSM-based alert system (SMS and call)
* GPS-based location tracking
* Camera integration using ESP32-CAM
* Gyroscope-based movement detection

This module acts as the central controller for the entire system.

---

## 8.3 Movement Detection Module

A separate module is implemented for movement detection using the MPU6050 gyroscope sensor.

Features:

* Detects abnormal motor movement
* Sends alert via GSM
* Supports maintenance mode to avoid false alarms

---

## 8.4 Software Architecture

The system follows a modular architecture:

* Sensor Layer → Gyroscope, signal input
* Processing Layer → Microcontroller logic
* Communication Layer → GSM, GPS
* Monitoring Layer → Camera system

---

## 8.5 Key Functionalities

* Real-time signal monitoring
* Event-driven alert system
* Theft classification logic
* Remote notification capability

---

## 8.6 Advantages of Implementation

* Modular and scalable design
* Real-time response system
* Efficient and low-power operation
* Suitable for embedded environments

---
