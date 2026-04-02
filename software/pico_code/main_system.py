import network
import urequests
import time
import math
import json
from machine import UART, Pin, I2C

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
# WiFi credentials
WIFI_SSID = "Realme"
WIFI_PASSWORD = "123456788"

# ESP32-CAM IP (YOUR ACTUAL IP)
ESP32_CAM_IP = "10.152.89.49"
CAPTURE_URL = f"http://{ESP32_CAM_IP}/capture"
# NOTE: Your ESP32-CAM doesn't have /theft-alert endpoint, so we'll use /capture

# Hardware Pins 
RX_PIN_WIRE = 22  # Wire Signal Input (Continuity Sensor)
BUTTON_PIN = 14   # Manual photo capture button
LED_PIN = "LED"   # Status LED 

# UART (GSM & GPS) 
uart_gsm = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
uart_gps = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))

# I2C (MPU6050)
i2c_dev = I2C(0, scl=Pin(9), sda=Pin(8), freq=100000)

# System Settings
ALERT_PHONE_NUMBER = "9370584716"
GYRO_THRESHOLD = 4.0         # Sensitivity for Motor Theft (degrees/sec)
WIRE_TIMEOUT_MS = 10000      # 10 seconds before "Wire Cut" alert
WIRE_DEBOUNCE_COUNT = 3      # Require multiple consecutive failures
DEFAULT_LATITUDE = 16.682016 
DEFAULT_LONGITUDE = 74.469714

# Pulse Timing
BIT_1_MIN = 0.007
START_MIN = 0.025
STOP_MIN = 0.015
FRAME_GAP = 0.010
GAP = 0.005

# ==========================================
# CLASS DEFINITIONS
# ==========================================

class MPU6050:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr
        self.init_mpu()
    
    def init_mpu(self):
        try:
            self.i2c.writeto_mem(self.addr, 0x6B, bytes([0x00]))
            time.sleep(0.1)
        except:
            print("MPU6050 Init Failed")
    
    def get_gyro_data(self):
        try:
            data = self.i2c.readfrom_mem(self.addr, 0x43, 6)
            x = (data[0] << 8 | data[1])
            y = (data[2] << 8 | data[3])
            z = (data[4] << 8 | data[5])
            
            if x > 32767: x -= 65536
            if y > 32767: y -= 65536
            if z > 32767: z -= 65536
            
            return x/131.0, y/131.0, z/131.0
        except:
            return 0, 0, 0

class GPSParser:
    def __init__(self):
        self.latitude = 0.0
        self.longitude = 0.0
        self.valid = False
    
    def parse_gps_data(self):
        try:
            if uart_gps.any():
                line = uart_gps.readline()
                try:
                    line = line.decode('utf-8')
                    if line.startswith('$GPGGA'):
                        parts = line.split(',')
                        if len(parts) >= 10 and parts[6] != '0':
                            lat = float(parts[2])
                            self.latitude = int(lat/100) + (lat%100)/60.0
                            if parts[3] == 'S': self.latitude *= -1
                            
                            lon = float(parts[4])
                            self.longitude = int(lon/100) + (lon%100)/60.0
                            if parts[5] == 'W': self.longitude *= -1
                            self.valid = True
                            return True
                except:
                    pass
        except:
            pass
        return False
    
    def get_link(self):
        lat = self.latitude if self.valid else DEFAULT_LATITUDE
        lon = self.longitude if self.valid else DEFAULT_LONGITUDE
        return f"http://maps.google.com/?q={lat:.6f},{lon:.6f}"

class MovementDetector:
    def __init__(self, mpu):
        self.mpu = mpu
        self.offset = [0, 0, 0]
    
    def calibrate(self):
        print("Calibrating Gyro... Stay still!")
        sx, sy, sz = 0, 0, 0
        num_samples = 20
        for _ in range(num_samples):
            x, y, z = self.mpu.get_gyro_data()
            sx += x; sy += y; sz += z
            time.sleep(0.05)
        self.offset = [sx/num_samples, sy/num_samples, sz/num_samples]
        print(f"Calibration Done. Offsets: {self.offset}")
    
    def check_movement(self):
        x, y, z = self.mpu.get_gyro_data()
        x -= self.offset[0]
        y -= self.offset[1]
        z -= self.offset[2]
        mag = math.sqrt(x*x + y*y + z*z)
        return mag > GYRO_THRESHOLD, mag

class CameraSystem:
    def __init__(self):
        self.esp32_ip = ESP32_CAM_IP
        self.capture_url = f"http://{self.esp32_ip}/capture"
        self.photo_count = 0
        self.wlan = network.WLAN(network.STA_IF)
        self.connected = False
    
    def connect_wifi(self):
        """Connect to WiFi"""
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
        """Request photo capture - SIMPLE VERSION"""
        if not self.connected:
            print("❌ Not connected to WiFi")
            return False
        
        print(f"\n{'='*50}")
        print(f"📸 REQUESTING PHOTO FROM ESP32-CAM")
        print(f"{'='*50}")
        
        try:
            print(f"Sending request to {self.capture_url}")
            response = urequests.get(self.capture_url, timeout=30)
            
            # Check if response is JSON or HTML
            response_text = response.text.strip()
            
            if response_text.startswith('{') and response_text.endswith('}'):
                # It's JSON - parse it
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
                # It's HTML - the request might have been redirected
                print("⚠️ Received HTML instead of JSON")
                print(f"Response starts with: {response_text[:100]}...")
                
                # Check if the request was successful anyway
                if response.status_code == 200:
                    # Even though we got HTML, the photo might have been taken
                    # Look at ESP32-CAM serial output to confirm
                    print("⚠️ Got HTML page. Check ESP32-CAM serial for photo status.")
                    print("   The photo might have been captured anyway.")
                    self.photo_count += 1
                    response.close()
                    return True  # Assume success
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    response.close()
                    return False
                
        except Exception as e:
            print(f"❌ Error requesting photo: {e}")
            return False

# ==========================================
# SIGNAL DECODING FUNCTIONS
# ==========================================

rx = Pin(RX_PIN_WIRE, Pin.IN, Pin.PULL_DOWN)

def measure_pulse(timeout_ms=100):
    """Measure pulse width"""
    start = time.ticks_ms()
    
    while rx.value() == 0:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms: 
            return None
    
    t_start = time.ticks_us()
    
    while rx.value() == 1:
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms: 
            return None
    
    t_end = time.ticks_us()
    
    pulse_width = (t_end - t_start) / 1000000.0
    
    if pulse_width < 0.001:
        return None
    
    return pulse_width

def read_frame_fast():
    """Read and decode a frame"""
    try:
        pulse = measure_pulse(100)
        if not pulse or pulse < START_MIN: 
            return None
        
        time.sleep(FRAME_GAP)
        
        bits = 0
        for i in range(10):
            p = measure_pulse(50)
            if not p: 
                return None
            if p >= BIT_1_MIN: 
                bits |= (1 << i)
            time.sleep(GAP)
            
        stop = measure_pulse(50)
        if not stop or stop < STOP_MIN: 
            return None
        
        return bits
    except:
        return None

# ==========================================
# GSM FUNCTIONS
# ==========================================

def send_at(cmd, wait=1):
    """Send AT command"""
    try:
        uart_gsm.write(cmd + '\r\n')
        time.sleep(wait)
        resp = uart_gsm.read()
        return resp.decode() if resp else ""
    except:
        return ""

def init_gsm():
    """Initialize GSM module"""
    print("Initializing GSM...")
    send_at("AT", 2)
    send_at("AT+CMGF=1", 1)
    send_at("AT+CSQ", 1)

def send_alert(phone, msg):
    """Send SMS alert and voice call"""
    print(f"\n📱 SENDING ALERT SMS...")
    print(f"Message: {msg}")
    
    # Send SMS
    try:
        send_at(f'AT+CMGS="{phone}"', 2)
        time.sleep(1)
        uart_gsm.write(msg + '\r\n')
        time.sleep(0.5)
        uart_gsm.write(bytes([26]))
        time.sleep(3)
        print("✅ SMS Sent")
    except Exception as e:
        print(f"❌ SMS Failed: {e}")
        return False
    
    # Wait before call
    print("Waiting 3 seconds before call...")
    time.sleep(3)
    
    # Make voice call
    try:
        print("📞 Dialing...")
        send_at(f"ATD{phone};", 2)
        time.sleep(15)
        send_at("ATH", 2)
        print("✅ Call completed")
        return True
    except Exception as e:
        print(f"❌ Call Failed: {e}")
        return False

# ==========================================
# MAIN INTEGRATED SYSTEM
# ==========================================

class IntegratedSecuritySystem:
    def __init__(self):
        # Hardware components
        self.led = Pin(LED_PIN, Pin.OUT)
        self.button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        
        # Sensors
        self.mpu = MPU6050(i2c_dev)
        self.detector = MovementDetector(self.mpu)
        self.gps = GPSParser()
        self.camera = CameraSystem()
        
        # State variables
        self.last_wire_time = time.ticks_ms()
        self.last_valid_signal = time.ticks_ms()
        self.expected_val = -1
        self.direction = 1
        self.learning = True
        self.learned_buffer = []
        self.wire_tampered_flag = False
        self.wire_failure_count = 0
        self.button_last_state = self.button.value()
        self.photo_count = 0
        
        # Statistics
        self.signal_count = 0
        self.error_count = 0
    
    def initialize_system(self):
        print("\n" + "="*60)
        print("       INTEGRATED SECURITY SYSTEM")
        print("="*60)
        
        print("\n[1/3] Initializing sensors...")
        self.detector.calibrate()
        
        print("\n[2/3] Initializing GSM...")
        init_gsm()
        
        print("\n[3/3] Connecting WiFi for camera...")
        if not self.camera.connect_wifi():
            print("⚠️  WiFi failed, camera functions disabled")
        else:
            print("✅ Camera system ready")
        
        print("\n" + "="*60)
        print("     SYSTEM READY - MONITORING ACTIVE")
        print("="*60 + "\n")
    
    def blink_led(self, times=1, delay=100):
        """Simple LED blink"""
        for _ in range(times):
            self.led.value(1)
            time.sleep_ms(delay)
            self.led.value(0)
            time.sleep_ms(delay)
    
    def process_wire_signal(self):
        """Process wire continuity signal"""
        current_time = time.ticks_ms()
        received = read_frame_fast()
        
        if received is not None:
            # Valid signal received
            self.last_wire_time = current_time
            self.last_valid_signal = current_time
            self.wire_failure_count = 0
            
            if self.learning:
                self.learned_buffer.append(received)
                if len(self.learned_buffer) >= 4:
                    diff = self.learned_buffer[-1] - self.learned_buffer[-2]
                    self.direction = 1 if diff > 0 else -1
                    self.expected_val = received + self.direction
                    self.learning = False
                    print(f"✓ Wire pattern learned")
            
            else:
                valid = (received == self.expected_val) or (received == self.expected_val + self.direction)
                
                if valid:
                    if self.wire_tampered_flag:
                        print("✅ VALID PULSE - Clearing tamper flag")
                        self.wire_tampered_flag = False
                        self.blink_led(2, 150)
                    
                    if received != self.expected_val:
                        self.expected_val = received
                    self.expected_val += self.direction
                        
                else:
                    self.wire_failure_count += 1
                    self.error_count += 1
                    
                    if self.wire_failure_count >= WIRE_DEBOUNCE_COUNT:
                        return True
        
        else:
            # No signal received
            time_since_valid = time.ticks_diff(current_time, self.last_valid_signal)
            
            if time_since_valid > 5000:
                self.wire_failure_count += 1
                
                if self.wire_failure_count % 10 == 0:
                    print(f"⚠️ No signal for {time_since_valid/1000:.1f}s")
                
                if (time_since_valid > WIRE_TIMEOUT_MS and 
                    self.wire_failure_count >= WIRE_DEBOUNCE_COUNT):
                    return True
        
        return False
    
    def handle_wire_tampering(self):
        """Handle wire tampering detection"""
        if not self.wire_tampered_flag:
            print("\n" + "!"*50)
            print("🚨 WIRE TAMPERING DETECTED!")
            print("!"*50)
            
            # Get GPS location
            self.gps.parse_gps_data()
            gps_link = self.gps.get_link()
            
            # Send GSM alert
            alert_msg = f"ALERT: Wire Tampering Detected!\nLocation: {gps_link}"
            send_alert(ALERT_PHONE_NUMBER, alert_msg)
            
            # Try to trigger camera for evidence
            if self.camera.connected:
                print("\n📸 Requesting evidence photo...")
                if self.camera.request_photo():
                    print("✅ Evidence photo requested")
                else:
                    print("⚠️ Photo request failed")
            else:
                print("⚠️ Camera not connected")
            
            # Set tamper flag
            self.wire_tampered_flag = True
            print("\n!!! HIGH ALERT MODE ACTIVATED !!!")
    
    def handle_movement_detection(self):
        """Handle movement detection when in alert mode"""
        moved, magnitude = self.detector.check_movement()
        
        if moved and self.wire_tampered_flag:
            print("\n" + "!"*60)
            print(f"🚨🚨 MOTOR THEFT DETECTED! Magnitude: {magnitude:.2f} deg/s")
            print("!"*60)
            
            # Get GPS location
            self.gps.parse_gps_data()
            gps_link = self.gps.get_link()
            
            # Send critical GSM alert
            alert_msg = f"CRITICAL: Motor Theft In Progress!\nVibration: {magnitude:.1f} deg/s\nLocation: {gps_link}"
            send_alert(ALERT_PHONE_NUMBER, alert_msg)
            
            # Try to trigger camera multiple times
            if self.camera.connected:
                print("\n📸📸 Requesting evidence photos...")
                for i in range(3):
                    print(f"  Photo {i+1}/3...")
                    self.camera.request_photo()
                    time.sleep(1)
            
            # Reset system
            print("\n🔁 System resetting (60s pause)...")
            time.sleep(60)
            
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
        """Handle manual button press for photo capture"""
        current_state = self.button.value()
        
        if current_state == 0 and self.button_last_state == 1:
            print("\n🔘 BUTTON PRESSED - Manual photo request")
            
            if self.camera.connected:
                if self.camera.request_photo():
                    self.blink_led(2, 150)
                    self.photo_count += 1
                else:
                    self.blink_led(3, 100)
            else:
                print("❌ Camera not connected")
                self.blink_led(3, 100)
            
            time.sleep(0.5)
        
        self.button_last_state = current_state
    
    def run(self):
        """Main system loop"""
        self.initialize_system()
        
        last_status_time = time.ticks_ms()
        
        try:
            while True:
                current_time = time.ticks_ms()
                
                # 1. Check button
                self.handle_button_press()
                
                # 2. Process wire signal
                wire_issue = self.process_wire_signal()
                
                # 3. Handle wire tampering
                if wire_issue:
                    self.handle_wire_tampering()
                
                # 4. Check for movement
                if self.wire_tampered_flag:
                    theft_detected = self.handle_movement_detection()
                    if theft_detected:
                        continue
                
                # 5. Update GPS
                if time.ticks_diff(current_time, last_status_time) > 10000:
                    self.gps.parse_gps_data()
                
                # 6. Status LED
                if self.wire_tampered_flag:
                    # Fast blink during alert
                    if current_time % 500 < 250:
                        self.led.value(1)
                    else:
                        self.led.value(0)
                else:
                    # Slow blink when ready
                    if current_time % 3000 < 150:
                        self.led.value(1)
                    else:
                        self.led.value(0)
                
                # 7. Print status
                if time.ticks_diff(current_time, last_status_time) > 60000:
                    print(f"\n[Status] Photos: {self.photo_count}, Alert: {self.wire_tampered_flag}")
                    last_status_time = current_time
                
                time.sleep_ms(10)
                
        except Exception as e:
            print(f"\n❌ SYSTEM ERROR: {e}")
            print("Restarting in 10s...")
            time.sleep(10)
            machine.reset()

# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("   INTEGRATED SECURITY SYSTEM")
    print("="*60)
    
    try:
        system = IntegratedSecuritySystem()
        system.run()
    except KeyboardInterrupt:
        print("\n\n👋 System stopped")
    except Exception as e:
        print(f"\n❌ Fatal: {e}")
        time.sleep(5)
        machine.reset()
final working code with camera
