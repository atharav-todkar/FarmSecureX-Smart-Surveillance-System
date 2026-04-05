# ==========================================
# FarmSecureX – Integrated Security System
# Patent Filed: 7th December 2025
# Application No.: 202521123445
#
# Description:
#   Smart surveillance system for agriculture motor
#   and copper cable theft detection using:
#   - Coded pulse continuity sensing (every 200ms)
#   - GPS-based location tracking
#   - GSM-based SMS + voice call alerts
#   - Gyroscope-based motor theft classification
#   - ESP32-CAM for visual evidence capture
#
# Hardware: Raspberry Pi Pico W
# Language: MicroPython
# Team: Atharav Todkar, Pranav Mirje, Om Patil, Aniruddha More
# ==========================================

import network
import urequests
import time
import math
import json
from machine import UART, Pin, I2C

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================

# WiFi credentials for ESP32-CAM communication
WIFI_SSID = "Realme"
WIFI_PASSWORD = "123456788"

# ESP32-CAM IP address on local network
# Update this if your camera IP changes
ESP32_CAM_IP = "10.152.89.49"
CAPTURE_URL = f"http://{ESP32_CAM_IP}/capture"

# Hardware Pin Definitions
RX_PIN_WIRE = 22  # GPIO22 — receives coded pulse from motor cable
BUTTON_PIN = 14   # GPIO14 — manual photo capture trigger
LED_PIN = "LED"   # Onboard LED — status indicator

# UART0: GSM module (SIM A7670E) for SMS and voice calls
uart_gsm = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

# UART1: GPS module (GY-GPS6MV2) for location tracking
uart_gps = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))

# I2C0: MPU6050 gyroscope for motor vibration detection
i2c_dev = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)

# Alert Configuration
ALERT_PHONE_NUMBER = "9370584716"  # Farmer's phone number for SMS + call

# Gyroscope threshold — magnitude above this value triggers motor theft alert
# Increase if false positives occur, decrease if detection is too slow
GYRO_THRESHOLD = 4.0  # degrees/sec

# Wire signal timeout — if no coded pulse received for this duration, raise alert
WIRE_TIMEOUT_MS = 10000  # 10 seconds

# Number of consecutive signal failures before triggering wire tamper alert
# Prevents false alarms from momentary signal noise
WIRE_DEBOUNCE_COUNT = 3

# Default GPS coordinates used if GPS module has no fix yet
# Location: Ichalkaranji, Maharashtra
DEFAULT_LATITUDE = 16.682016
DEFAULT_LONGITUDE = 74.469714

# ==========================================
# CODED PULSE TIMING CONSTANTS
# ==========================================
# Core innovation: Pico W sends a unique coded pulse pattern every 200ms
# through the motor cable at low voltage. The receiver decodes this pattern.
# Any signal loss or mismatch = tampering detected.

BIT_1_MIN = 0.007   # Minimum pulse width (seconds) to register as binary '1'
START_MIN = 0.025   # Minimum start pulse width — marks beginning of a frame
STOP_MIN = 0.015    # Minimum stop pulse width — marks end of a frame
FRAME_GAP = 0.010   # Gap between start pulse and data bits
GAP = 0.005         # Gap between individual data bits


# ==========================================
# CLASS: MPU6050 Gyroscope
# ==========================================

class MPU6050:
    """
    Interface for MPU6050 6-axis gyroscope/accelerometer via I2C.
    Used to detect motor vibration — confirms motor theft when
    wire tampering has already been detected.
    """
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr  # Default I2C address for MPU6050
        self.init_mpu()

    def init_mpu(self):
        """Wake up MPU6050 from sleep mode (register 0x6B = power management)"""
        try:
            self.i2c.writeto_mem(self.addr, 0x6B, bytes([0x00]))
            time.sleep(0.1)
        except:
            print("MPU6050 Init Failed")

    def get_gyro_data(self):
        """
        Read raw gyroscope data from registers 0x43–0x48.
        Converts raw 16-bit signed integers to degrees/second.
        Sensitivity scale factor: 131 LSB per deg/s (default ±250 dps range).
        Returns: (x, y, z) in degrees/second
        """
        try:
            data = self.i2c.readfrom_mem(self.addr, 0x43, 6)

            # Combine high and low bytes for each axis
            x = (data[0] << 8 | data[1])
            y = (data[2] << 8 | data[3])
            z = (data[4] << 8 | data[5])

            # Convert from unsigned to signed 16-bit integer
            if x > 32767: x -= 65536
            if y > 32767: y -= 65536
            if z > 32767: z -= 65536

            # Scale to degrees/second using MPU6050 sensitivity factor
            return x / 131.0, y / 131.0, z / 131.0
        except:
            return 0, 0, 0


# ==========================================
# CLASS: GPS Parser
# ==========================================

class GPSParser:
    """
    Parses NMEA sentences from GPS module (GY-GPS6MV2) via UART1.
    Extracts latitude and longitude from $GPGGA sentences.
    Generates Google Maps link for SMS alerts.
    """
    def __init__(self):
        self.latitude = 0.0
        self.longitude = 0.0
        self.valid = False  # True only when GPS has acquired a satellite fix

    def parse_gps_data(self):
        """
        Read and parse $GPGGA NMEA sentence from GPS module.
        $GPGGA contains: time, lat, lon, fix quality, satellites, altitude.
        Converts DDMM.MMMM format to decimal degrees.
        Returns True if valid fix obtained.
        """
        try:
            if uart_gps.any():
                line = uart_gps.readline()
                try:
                    line = line.decode('utf-8')
                    if line.startswith('$GPGGA'):
                        parts = line.split(',')
                        # parts[6] = fix quality; '0' means no fix
                        if len(parts) >= 10 and parts[6] != '0':

                            # Convert latitude from DDMM.MMMM to decimal degrees
                            lat = float(parts[2])
                            self.latitude = int(lat / 100) + (lat % 100) / 60.0
                            if parts[3] == 'S':
                                self.latitude *= -1  # South is negative

                            # Convert longitude from DDDMM.MMMM to decimal degrees
                            lon = float(parts[4])
                            self.longitude = int(lon / 100) + (lon % 100) / 60.0
                            if parts[5] == 'W':
                                self.longitude *= -1  # West is negative

                            self.valid = True
                            return True
                except:
                    pass
        except:
            pass
        return False

    def get_link(self):
        """
        Generate a clickable Google Maps link using current GPS coordinates.
        Falls back to default coordinates if GPS fix not yet acquired.
        """
        lat = self.latitude if self.valid else DEFAULT_LATITUDE
        lon = self.longitude if self.valid else DEFAULT_LONGITUDE
        return f"http://maps.google.com/?q={lat:.6f},{lon:.6f}"


# ==========================================
# CLASS: Movement Detector
# ==========================================

class MovementDetector:
    """
    Wraps MPU6050 to detect significant motor movement/vibration.
    Calibrates gyroscope offsets at startup to eliminate sensor drift.
    Used to distinguish cable-only theft from motor + cable theft.
    """
    def __init__(self, mpu):
        self.mpu = mpu
        self.offset = [0, 0, 0]  # Baseline gyro offsets from calibration

    def calibrate(self):
        """
        Calibrate gyroscope by averaging 20 readings while motor is stationary.
        These offsets are subtracted during movement checks to eliminate drift.
        IMPORTANT: Motor must be completely still during calibration.
        """
        print("Calibrating Gyro... Stay still!")
        sx, sy, sz = 0, 0, 0
        num_samples = 20
        for _ in range(num_samples):
            x, y, z = self.mpu.get_gyro_data()
            sx += x
            sy += y
            sz += z
            time.sleep(0.05)
        self.offset = [sx / num_samples, sy / num_samples, sz / num_samples]
        print(f"Calibration Done. Offsets: {self.offset}")

    def check_movement(self):
        """
        Check if significant motor movement is detected.
        Subtracts calibration offsets, computes 3D magnitude vector.
        Returns: (is_moving: bool, magnitude: float in deg/s)
        Trigger threshold set by GYRO_THRESHOLD constant.
        """
        x, y, z = self.mpu.get_gyro_data()

        # Remove calibration offset to get true movement
        x -= self.offset[0]
        y -= self.offset[1]
        z -= self.offset[2]

        # 3D vector magnitude — combines all axes into single movement value
        mag = math.sqrt(x * x + y * y + z * z)
        return mag > GYRO_THRESHOLD, mag


# ==========================================
# CLASS: Camera System (ESP32-CAM)
# ==========================================

class CameraSystem:
    """
    Controls ESP32-CAM (OV2640) for visual evidence capture via WiFi HTTP.
    Connects Pico W to local WiFi and sends HTTP GET to ESP32-CAM /capture endpoint.
    Photos are stored on the ESP32-CAM's SD card or served via web.
    """
    def __init__(self):
        self.esp32_ip = ESP32_CAM_IP
        self.capture_url = f"http://{self.esp32_ip}/capture"
        self.photo_count = 0
        self.wlan = network.WLAN(network.STA_IF)  # Station mode (client)
        self.connected = False

    def connect_wifi(self):
        """
        Connect Pico W to WiFi network.
        Tries for 10 seconds (20 x 0.5s attempts).
        Required for HTTP communication with ESP32-CAM.
        """
        self.wlan.active(True)
        print("Connecting to WiFi", end="")
        self.wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        for _ in range(20):
            if self.wlan.isconnected():
                break
            print(".", end="")
            time.sleep(0.5)

        if self.wlan.isconnected():
            print("\n✅ WiFi Connected!")
            print(f"   IP Address: {self.wlan.ifconfig()[0]}")
            self.connected = True
            return True
        else:
            print("\n❌ Failed to connect to WiFi")
            self.connected = False
            return False

    def request_photo(self):
        """
        Send HTTP GET request to ESP32-CAM to trigger photo capture.
        Handles both JSON and HTML responses from ESP32-CAM firmware.
        Returns True if photo successfully captured, False otherwise.
        """
        if not self.connected:
            print("❌ Not connected to WiFi")
            return False

        print(f"\n{'='*50}")
        print(f"📸 REQUESTING PHOTO FROM ESP32-CAM")
        print(f"{'='*50}")

        try:
            print(f"Sending request to {self.capture_url}")
            response = urequests.get(self.capture_url, timeout=30)
            response_text = response.text.strip()

            if response_text.startswith('{') and response_text.endswith('}'):
                # ESP32-CAM returned JSON response — parse status field
                result = json.loads(response_text)
                print(f"✅ JSON Response: {result}")

                if result.get("status") == "success":
                    self.photo_count += 1
                    print(f"✅ Photo #{self.photo_count} captured successfully!")
                    response.close()
                    return True
                else:
                    print(f"❌ Failed: {result.get('message', 'Unknown error')}")
                    response.close()
                    return False
            else:
                # ESP32-CAM returned HTML page (some firmware versions do this)
                # HTTP 200 still means the capture endpoint was hit successfully
                print("⚠️ Received HTML instead of JSON")
                print(f"Response starts with: {response_text[:100]}...")

                if response.status_code == 200:
                    print("⚠️ Got HTML page. Check ESP32-CAM serial for photo status.")
                    self.photo_count += 1
                    response.close()
                    return True
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    response.close()
                    return False

        except Exception as e:
            print(f"❌ Error requesting photo: {e}")
            return False


# ==========================================
# CODED PULSE SIGNAL DECODING
# ==========================================

# GPIO22 set as input with pull-down resistor
# Receives coded pulse signal transmitted through motor cable
rx = Pin(RX_PIN_WIRE, Pin.IN, Pin.PULL_DOWN)


def measure_pulse(timeout_ms=100):
    """
    Measure the width (duration) of a single incoming pulse on GPIO22.
    Waits for rising edge, then measures how long signal stays HIGH.

    This is the core of the coded pulse detection — the width of each
    pulse encodes information about the signal frame (start/stop/data bits).

    Returns: pulse width in seconds, or None if timeout exceeded.
    """
    start = time.ticks_ms()

    # Wait for signal to go HIGH (rising edge)
    while rx.value() == 0:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            return None  # Timeout — no pulse received

    t_start = time.ticks_us()

    # Measure how long signal stays HIGH (falling edge)
    while rx.value() == 1:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            return None  # Timeout — pulse too long (abnormal)

    t_end = time.ticks_us()

    # Convert microseconds to seconds
    pulse_width = (t_end - t_start) / 1000000.0

    # Ignore noise — pulses shorter than 1ms are invalid
    if pulse_width < 0.001:
        return None

    return pulse_width


def read_frame_fast():
    """
    Decode one complete coded pulse frame from the motor cable signal.

    Frame structure:
      [START pulse] → [10 data bits] → [STOP pulse]

    Each frame is generated by the transmitter every 200ms.
    The receiver validates the frame structure and extracts the data value.
    A valid, expected data value = cable intact.
    Missing or mismatched frame = cable tampered.

    Returns: decoded integer value if frame valid, None otherwise.
    """
    try:
        # Read and validate START pulse (must be >= START_MIN width)
        pulse = measure_pulse(100)
        if not pulse or pulse < START_MIN:
            return None  # No valid start pulse — skip this frame

        time.sleep(FRAME_GAP)  # Brief gap before data bits begin

        # Read 10 data bits (LSB first)
        bits = 0
        for i in range(10):
            p = measure_pulse(50)
            if not p:
                return None  # Incomplete frame — discard
            if p >= BIT_1_MIN:
                bits |= (1 << i)  # Pulse >= threshold = binary '1'
            time.sleep(GAP)     # Gap between bits

        # Read and validate STOP pulse (must be >= STOP_MIN width)
        stop = measure_pulse(50)
        if not stop or stop < STOP_MIN:
            return None  # Invalid stop pulse — discard frame

        return bits  # Return decoded 10-bit value

    except:
        return None


# ==========================================
# GSM MODULE FUNCTIONS
# ==========================================

def send_at(cmd, wait=1):
    """
    Send an AT command to the SIM A7670E GSM module via UART0.
    All GSM operations (SMS, calls, network check) use AT commands.
    Returns decoded response string, or empty string on failure.
    """
    try:
        uart_gsm.write(cmd + '\r\n')
        time.sleep(wait)
        resp = uart_gsm.read()
        return resp.decode() if resp else ""
    except:
        return ""


def init_gsm():
    """
    Initialize GSM module with required AT commands:
    - AT: Basic check (module alive)
    - AT+CMGF=1: Set SMS to text mode (vs PDU mode)
    - AT+CSQ: Check signal quality (for debugging)
    """
    print("Initializing GSM...")
    send_at("AT", 2)       # Basic handshake
    send_at("AT+CMGF=1", 1)  # Text mode SMS
    send_at("AT+CSQ", 1)   # Signal strength check


def send_alert(phone, msg):
    """
    Send SMS alert followed by a voice call to the farmer's phone.

    SMS Flow:
      AT+CMGS="<number>" → write message text → send Ctrl+Z (ASCII 26)

    Call Flow:
      ATD<number>; → wait 15 seconds (ring time) → ATH (hang up)

    The voice call ensures the farmer is alerted even if SMS is delayed.
    Returns True if both SMS and call succeeded.
    """
    print(f"\n📱 SENDING ALERT SMS...")
    print(f"Message: {msg}")

    # Send SMS
    try:
        send_at(f'AT+CMGS="{phone}"', 2)  # Start SMS to phone number
        time.sleep(1)
        uart_gsm.write(msg + '\r\n')       # Write message body
        time.sleep(0.5)
        uart_gsm.write(bytes([26]))        # Ctrl+Z signals end of SMS
        time.sleep(3)
        print("✅ SMS Sent")
    except Exception as e:
        print(f"❌ SMS Failed: {e}")
        return False

    # Brief pause before dialing
    print("Waiting 3 seconds before call...")
    time.sleep(3)

    # Make voice call — rings for 15 seconds then hangs up
    try:
        print("📞 Dialing...")
        send_at(f"ATD{phone};", 2)  # Dial number (semicolon = voice call)
        time.sleep(15)              # Let it ring
        send_at("ATH", 2)          # Hang up
        print("✅ Call completed")
        return True
    except Exception as e:
        print(f"❌ Call Failed: {e}")
        return False


# ==========================================
# MAIN INTEGRATED SECURITY SYSTEM
# ==========================================

class IntegratedSecuritySystem:
    """
    Main controller class that integrates all subsystems:
    - Coded pulse wire monitoring (core innovation)
    - Gyroscope-based motor theft detection
    - GPS location tracking
    - GSM SMS + voice call alerts
    - ESP32-CAM evidence capture
    - Manual photo capture via button

    Theft Classification Logic:
      Wire signal lost/mismatch only → Wire Tampering alert
      Wire tampered + motor vibration → Motor Theft alert (critical)
    """

    def __init__(self):
        # GPIO setup
        self.led = Pin(LED_PIN, Pin.OUT)
        self.button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)  # Active LOW button

        # Sensor and subsystem objects
        self.mpu = MPU6050(i2c_dev)
        self.detector = MovementDetector(self.mpu)
        self.gps = GPSParser()
        self.camera = CameraSystem()

        # Wire signal state tracking
        self.last_wire_time = time.ticks_ms()
        self.last_valid_signal = time.ticks_ms()
        self.expected_val = -1       # Expected next coded pulse value
        self.direction = 1           # Direction of value change (+1 or -1)
        self.learning = True         # True during initial pattern learning phase
        self.learned_buffer = []     # Buffer to learn initial pulse pattern
        self.wire_tampered_flag = False   # True when wire tamper detected
        self.wire_failure_count = 0       # Consecutive signal failure counter
        self.button_last_state = self.button.value()

        # Statistics
        self.signal_count = 0  # Total valid signals received
        self.error_count = 0   # Total signal errors/mismatches
        self.photo_count = 0   # Total photos captured

    def initialize_system(self):
        """
        Full system startup sequence:
        1. Calibrate gyroscope (motor must be still)
        2. Initialize GSM module
        3. Connect to WiFi for camera
        """
        print("\n" + "=" * 60)
        print("       INTEGRATED SECURITY SYSTEM")
        print("=" * 60)

        print("\n[1/3] Initializing sensors...")
        self.detector.calibrate()  # Gyro calibration — keep motor still!

        print("\n[2/3] Initializing GSM...")
        init_gsm()

        print("\n[3/3] Connecting WiFi for camera...")
        if not self.camera.connect_wifi():
            print("⚠️  WiFi failed, camera functions disabled")
        else:
            print("✅ Camera system ready")

        print("\n" + "=" * 60)
        print("     SYSTEM READY - MONITORING ACTIVE")
        print("=" * 60 + "\n")

    def blink_led(self, times=1, delay=100):
        """
        Blink onboard LED for visual feedback.
        Used to confirm actions (photo taken, alert sent, system reset).
        """
        for _ in range(times):
            self.led.value(1)
            time.sleep_ms(delay)
            self.led.value(0)
            time.sleep_ms(delay)

    def process_wire_signal(self):
        """
        Core monitoring function — reads and validates coded pulse from cable.

        Phase 1 — Learning (first 4 frames):
          System learns the initial coded pulse value and direction of change.
          This adapts to any starting value without hardcoding.

        Phase 2 — Monitoring:
          Each new frame is compared to the expected next value.
          Valid frame → reset failure counter, update expected value.
          Invalid frame → increment failure counter.
          WIRE_DEBOUNCE_COUNT consecutive failures → raise tamper flag.

        Returns True if wire tampering is detected, False otherwise.
        """
        current_time = time.ticks_ms()
        received = read_frame_fast()

        if received is not None:
            # Valid frame received — cable is intact
            self.last_wire_time = current_time
            self.last_valid_signal = current_time
            self.wire_failure_count = 0  # Reset failure counter

            if self.learning:
                # Collect initial frames to learn pulse pattern
                self.learned_buffer.append(received)
                if len(self.learned_buffer) >= 4:
                    # Determine if values are incrementing or decrementing
                    diff = self.learned_buffer[-1] - self.learned_buffer[-2]
                    self.direction = 1 if diff > 0 else -1
                    self.expected_val = received + self.direction
                    self.learning = False
                    print(f"✓ Wire pattern learned")

            else:
                # Check if received value matches expected coded pattern
                valid = (received == self.expected_val) or \
                        (received == self.expected_val + self.direction)

                if valid:
                    # Signal valid — clear any previous tamper flag
                    if self.wire_tampered_flag:
                        print("✅ VALID PULSE - Clearing tamper flag")
                        self.wire_tampered_flag = False
                        self.blink_led(2, 150)

                    # Advance expected value for next frame
                    if received != self.expected_val:
                        self.expected_val = received
                    self.expected_val += self.direction

                else:
                    # Signal mismatch — possible tampering
                    self.wire_failure_count += 1
                    self.error_count += 1

                    if self.wire_failure_count >= WIRE_DEBOUNCE_COUNT:
                        return True  # Confirmed tamper — raise alert

        else:
            # No pulse received — cable may be cut
            time_since_valid = time.ticks_diff(current_time, self.last_valid_signal)

            if time_since_valid > 5000:
                self.wire_failure_count += 1

                # Log warning every 10 failures
                if self.wire_failure_count % 10 == 0:
                    print(f"⚠️ No signal for {time_since_valid / 1000:.1f}s")

                # Trigger alert after timeout + debounce threshold met
                if (time_since_valid > WIRE_TIMEOUT_MS and
                        self.wire_failure_count >= WIRE_DEBOUNCE_COUNT):
                    return True  # Cable cut confirmed — raise alert

        return False  # No tampering detected

    def handle_wire_tampering(self):
        """
        Respond to wire tampering detection:
        1. Get current GPS coordinates
        2. Send SMS alert with Google Maps link
        3. Request photo evidence from ESP32-CAM
        4. Set wire_tampered_flag to activate motor theft monitoring
        """
        if not self.wire_tampered_flag:
            print("\n" + "!" * 50)
            print("🚨 WIRE TAMPERING DETECTED!")
            print("!" * 50)

            # Get GPS location for alert message
            self.gps.parse_gps_data()
            gps_link = self.gps.get_link()

            # Send SMS + voice call alert
            alert_msg = f"ALERT: Wire Tampering Detected!\nLocation: {gps_link}"
            send_alert(ALERT_PHONE_NUMBER, alert_msg)

            # Capture photo evidence via ESP32-CAM
            if self.camera.connected:
                print("\n📸 Requesting evidence photo...")
                if self.camera.request_photo():
                    print("✅ Evidence photo requested")
                else:
                    print("⚠️ Photo request failed")
            else:
                print("⚠️ Camera not connected")

            # Activate high alert mode — enables motor theft monitoring
            self.wire_tampered_flag = True
            print("\n!!! HIGH ALERT MODE ACTIVATED !!!")

    def handle_movement_detection(self):
        """
        Check for motor vibration when wire tamper is already active.
        Wire tampered + motor vibration = Motor Theft (most critical scenario).

        Response:
        1. Send critical SMS + call with vibration magnitude
        2. Capture 3 photos in quick succession for better evidence
        3. Reset system after 60 second pause (prevents alert spam)
        Returns True if motor theft confirmed, False otherwise.
        """
        moved, magnitude = self.detector.check_movement()

        if moved and self.wire_tampered_flag:
            print("\n" + "!" * 60)
            print(f"🚨🚨 MOTOR THEFT DETECTED! Magnitude: {magnitude:.2f} deg/s")
            print("!" * 60)

            # Get updated GPS location
            self.gps.parse_gps_data()
            gps_link = self.gps.get_link()

            # Send critical alert with vibration data
            alert_msg = (f"CRITICAL: Motor Theft In Progress!\n"
                         f"Vibration: {magnitude:.1f} deg/s\n"
                         f"Location: {gps_link}")
            send_alert(ALERT_PHONE_NUMBER, alert_msg)

            # Capture 3 rapid photos for maximum evidence
            if self.camera.connected:
                print("\n📸📸 Requesting evidence photos...")
                for i in range(3):
                    print(f"  Photo {i + 1}/3...")
                    self.camera.request_photo()
                    time.sleep(1)

            # 60 second cooldown before resuming monitoring
            # Prevents repeated alerts for same theft event
            print("\n🔁 System resetting (60s pause)...")
            time.sleep(60)

            # Full system state reset
            self.last_wire_time = time.ticks_ms()
            self.last_valid_signal = time.ticks_ms()
            self.learning = True
            self.wire_tampered_flag = False
            self.wire_failure_count = 0
            self.learned_buffer = []
            self.blink_led(2, 150)

            print("✅ System reset complete")
            return True

        return False

    def handle_button_press(self):
        """
        Detect manual button press (GPIO14, active LOW) for on-demand photo capture.
        Useful for testing camera system without triggering a theft event.
        LED blinks 2x on success, 3x on failure.
        """
        current_state = self.button.value()

        # Detect falling edge (button pressed)
        if current_state == 0 and self.button_last_state == 1:
            print("\n🔘 BUTTON PRESSED - Manual photo request")

            if self.camera.connected:
                if self.camera.request_photo():
                    self.blink_led(2, 150)  # Success indicator
                    self.photo_count += 1
                else:
                    self.blink_led(3, 100)  # Failure indicator
            else:
                print("❌ Camera not connected")
                self.blink_led(3, 100)

            time.sleep(0.5)  # Debounce delay

        self.button_last_state = current_state

    def run(self):
        """
        Main monitoring loop — runs indefinitely after initialization.

        Each iteration (every ~10ms):
          1. Check manual button press
          2. Process wire continuity signal (coded pulse check)
          3. Handle wire tampering if detected
          4. Check motor movement if in high alert mode
          5. Update GPS coordinates every 10 seconds
          6. Update status LED (fast blink = alert, slow blink = normal)
          7. Print status summary every 60 seconds
        """
        self.initialize_system()
        last_status_time = time.ticks_ms()

        try:
            while True:
                current_time = time.ticks_ms()

                # Step 1: Check manual photo button
                self.handle_button_press()

                # Step 2: Read and validate coded pulse from cable
                wire_issue = self.process_wire_signal()

                # Step 3: If wire tampered — send alert + capture photo
                if wire_issue:
                    self.handle_wire_tampering()

                # Step 4: If in alert mode — check for motor movement
                if self.wire_tampered_flag:
                    theft_detected = self.handle_movement_detection()
                    if theft_detected:
                        continue  # Restart loop after system reset

                # Step 5: Update GPS every 10 seconds
                if time.ticks_diff(current_time, last_status_time) > 10000:
                    self.gps.parse_gps_data()

                # Step 6: LED status indicator
                if self.wire_tampered_flag:
                    # Fast blink (500ms cycle) — high alert mode active
                    if current_time % 500 < 250:
                        self.led.value(1)
                    else:
                        self.led.value(0)
                else:
                    # Slow blink (3s cycle, 150ms ON) — normal monitoring
                    if current_time % 3000 < 150:
                        self.led.value(1)
                    else:
                        self.led.value(0)

                # Step 7: Print system status every 60 seconds
                if time.ticks_diff(current_time, last_status_time) > 60000:
                    print(f"\n[Status] Photos: {self.photo_count}, "
                          f"Alert: {self.wire_tampered_flag}")
                    last_status_time = current_time

                time.sleep_ms(10)  # 10ms loop delay — ~100 iterations/second

        except Exception as e:
            print(f"\n❌ SYSTEM ERROR: {e}")
            print("Restarting in 10s...")
            time.sleep(10)
            machine.reset()  # Hardware reset on unhandled exception


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("   FARMSECUREX INTEGRATED SECURITY SYSTEM")
    print("   Patent Application No.: 202521123445")
    print("=" * 60)

    try:
        system = IntegratedSecuritySystem()
        system.run()
    except KeyboardInterrupt:
        print("\n\n👋 System stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        time.sleep(5)
        machine.reset()  # Auto-restart on fatal error
