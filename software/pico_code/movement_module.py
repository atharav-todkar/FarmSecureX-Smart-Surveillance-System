# ==========================================
# FarmSecureX – Standalone Movement Alert Module
# Patent Application No.: 202521123445
#
# Description:
#   Standalone gyroscope-based motor movement detection system.
#   Used for testing MPU6050 sensitivity independently, and as a
#   backup module when full integrated system is not deployed.
#
#   Unique Feature: SMS-based Maintenance Mode
#     - Farmer texts "MAINTENANCE" → monitoring pauses (e.g. during repairs)
#     - Farmer texts "RESUME" → monitoring restarts automatically
#     This prevents false alerts during scheduled motor maintenance.
#
# Hardware: Raspberry Pi Pico W
# Sensors: MPU6050 Gyroscope + SIM A7670E GSM
# Language: MicroPython
# Team: Atharav Todkar, Pranav Mirje, Om Patil, Aniruddha More
# ==========================================

from machine import UART, Pin, I2C
import utime
import time
import math

# ==========================================
# CONFIGURATION
# ==========================================

# Gyroscope sensitivity threshold — 3D magnitude above this triggers alert
# Lower value = more sensitive (may cause false alarms from wind/animals)
# Higher value = less sensitive (may miss slow motor removal)
GYRO_THRESHOLD = 4.0      # degrees/second

# I2C pins for MPU6050 gyroscope communication
I2C_SCL_PIN = 9           # GPIO9 — I2C clock line
I2C_SDA_PIN = 8           # GPIO8 — I2C data line

# UART pins for SIM A7670E GSM module
GSM_TX_PIN = 0            # GPIO0 — Pico TX → GSM RX
GSM_RX_PIN = 1            # GPIO1 — Pico RX → GSM TX

# Farmer's phone number for SMS alerts and voice calls
PHONE_NUMBER = "9370584716"

# How often to check gyroscope (seconds)
MOVEMENT_CHECK_INTERVAL = 1

# Minimum time between consecutive alerts — prevents SMS spam
# If motor is continuously vibrating, only 1 alert per 60 seconds
ALERT_COOLDOWN = 60       # seconds

# SMS keywords for remote mode control
# Farmer texts these from their phone to switch system mode
CMD_MAINTENANCE = "MAINTENANCE"  # Pause monitoring during repairs
CMD_RESUME = "RESUME"            # Resume monitoring after repairs


# ==========================================
# CLASS: GSM Module
# ==========================================

class GSM_Module:
    """
    Controls SIM A7670E GSM module via UART for:
    - Sending SMS alerts to farmer
    - Making voice calls for urgent alerts
    - Receiving SMS commands for remote mode control

    AT Command Reference:
      ATE0        — Disable echo (cleaner serial output)
      AT+CMGF=1   — Set SMS to text mode
      AT+CNMI     — Route incoming SMS directly to serial (no storage needed)
      AT+CMGS     — Send SMS
      ATD         — Dial a voice call
      ATH         — Hang up
    """

    def __init__(self, uart_id=0, baudrate=115200,
                 tx_pin=GSM_TX_PIN, rx_pin=GSM_RX_PIN):
        # Initialize UART0 for GSM communication
        self.gsm = UART(uart_id, baudrate=baudrate,
                        tx=Pin(tx_pin), rx=Pin(rx_pin))
        utime.sleep(2)  # Allow GSM module to power up fully
        self.initialized = False

    def send_at(self, command, timeout=3000, wait_for_ok=True):
        """
        Send an AT command to GSM module and wait for response.
        Reads serial buffer until OK/ERROR received or timeout expires.

        Args:
            command: AT command string (e.g. "AT+CMGF=1")
            timeout: Max wait time in milliseconds
            wait_for_ok: If True, stop reading when OK or ERROR seen
        Returns: Full response string from GSM module
        """
        self.gsm.write(command + '\r\n')
        start_time = utime.ticks_ms()
        response = ""

        while utime.ticks_diff(utime.ticks_ms(), start_time) < timeout:
            if self.gsm.any():
                chunk = self.gsm.read(self.gsm.any()).decode()
                response += chunk
            # Stop early if we got a definitive response
            if wait_for_ok and ("OK" in response or "ERROR" in response):
                break
            utime.sleep(0.1)

        return response

    def initialize(self):
        """
        Configure GSM module with required AT commands at startup.
        AT+CNMI=1,2,0,0,0 routes incoming SMS text directly to serial
        output — this is what allows check_incoming_sms() to work
        without needing to poll the SIM card storage.
        """
        print("📱 Initializing GSM...")
        self.send_at("AT")              # Basic handshake — verify module alive
        self.send_at("ATE0")            # Turn off echo for cleaner output
        self.send_at("AT+CMGF=1")       # Text mode SMS (vs PDU mode)
        self.send_at("AT+CNMI=1,2,0,0,0")  # Route new SMS directly to serial
        self.initialized = True
        return True

    def check_incoming_sms(self):
        """
        Scan serial buffer for incoming SMS command keywords.
        Works because AT+CNMI routes SMS content directly to UART output.

        Checks for:
          "MAINTENANCE" → pause monitoring (e.g. farmer doing repairs)
          "RESUME"      → restart monitoring after maintenance

        Returns: "MAINTENANCE", "RESUME", or None if no command found.
        """
        if self.gsm.any():
            try:
                # Convert to uppercase so commands work regardless of case
                raw_data = self.gsm.read(self.gsm.any()).decode().upper()
                if CMD_MAINTENANCE in raw_data:
                    return "MAINTENANCE"
                elif CMD_RESUME in raw_data:
                    return "RESUME"
            except:
                pass
        return None

    def send_sms(self, phone_number, message):
        """
        Send SMS alert to farmer's phone.
        Flow: AT+CMGS → write message → send Ctrl+Z (0x1A) to confirm.
        """
        print(f"📤 Sending SMS to {phone_number}...")
        # Start SMS — don't wait for OK here, GSM waits for message body
        self.send_at('AT+CMGS="' + phone_number + '"', 5000, False)
        utime.sleep(0.5)
        # Write message body followed by Ctrl+Z to send
        self.gsm.write(message + '\x1A')
        utime.sleep(3)  # Wait for SMS transmission to complete
        return True

    def make_call(self, phone_number, duration=20):
        """
        Make a voice call to farmer for urgent alerts.
        ATD<number>; — semicolon means voice call (not data call).
        Rings for `duration` seconds then hangs up automatically.
        Voice call ensures alert reaches farmer even if SMS is delayed.
        """
        print(f"📞 Calling {phone_number}...")
        self.send_at('ATD' + phone_number + ';', 5000)
        utime.sleep(duration)   # Let it ring
        self.send_at("ATH")     # ATH = hang up
        return True


# ==========================================
# CLASS: MPU6050 Gyroscope
# ==========================================

class MPU6050:
    """
    Interface for MPU6050 6-axis IMU (gyroscope + accelerometer) via I2C.
    Only gyroscope data is used here for motor rotation/vibration detection.

    Register Map (used here):
      0x6B — Power management (write 0x00 to wake from sleep)
      0x43 — Gyroscope data start (6 bytes: X_H, X_L, Y_H, Y_L, Z_H, Z_L)

    Default sensitivity: ±250 dps → scale factor = 131 LSB per deg/s
    """

    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr  # Default I2C address (AD0 pin = LOW)
        self.wake_up()

    def wake_up(self):
        """
        Wake MPU6050 from default sleep mode by writing 0x00
        to power management register 0x6B.
        """
        try:
            self.i2c.writeto_mem(self.addr, 0x6B, bytes([0x00]))
            print("✅ MPU6050 Active")
        except Exception as e:
            print("❌ MPU6050 Error:", e)

    def get_gyro_data(self):
        """
        Read 6 bytes of raw gyroscope data from registers 0x43–0x48.
        Each axis uses 2 bytes (high + low) = 16-bit signed integer.
        Converts raw value to degrees/second using 131 LSB/dps scale.
        Returns: (x, y, z) rotation rates in degrees/second
        """
        try:
            data = self.i2c.readfrom_mem(self.addr, 0x43, 6)
            x = self.tobits(data[0], data[1])
            y = self.tobits(data[2], data[3])
            z = self.tobits(data[4], data[5])
            # Scale raw counts to degrees/second
            return x / 131.0, y / 131.0, z / 131.0
        except:
            return 0, 0, 0

    def tobits(self, high, low):
        """
        Combine high and low bytes into a signed 16-bit integer.
        MPU6050 sends data big-endian (high byte first).
        Values > 32767 are negative (two's complement conversion).
        """
        val = (high << 8) | low
        if val > 32767:
            val -= 65536  # Convert to signed
        return val


# ==========================================
# CLASS: Movement Alert System (Main Logic)
# ==========================================

class MovementAlertSystem:
    """
    Main controller for standalone movement detection module.

    Monitoring Logic:
      Every 1 second → read gyroscope → compute 3D magnitude
      If magnitude > GYRO_THRESHOLD → trigger alert (SMS + call)
      Alert cooldown = 60s to prevent repeated alerts for same event

    Remote Control via SMS:
      Farmer texts "MAINTENANCE" → system pauses (no false alarms during repairs)
      Farmer texts "RESUME"      → system restarts monitoring automatically
      This is a key real-world feature for practical farm deployment.
    """

    def __init__(self):
        self.gsm = GSM_Module()

        # I2C at 400kHz (fast mode) for quicker sensor reads
        self.i2c = I2C(0, scl=Pin(I2C_SCL_PIN),
                       sda=Pin(I2C_SDA_PIN), freq=400000)
        self.mpu = MPU6050(self.i2c)

        self.last_alert_time = 0      # Timestamp of last alert sent
        self.maintenance_mode = False  # False = monitoring active

    def start(self):
        """
        Initialize GSM and begin monitoring loop.
        Sends startup confirmation SMS so farmer knows system is online.
        """
        if self.gsm.initialize():
            print("🚀 System Online.")
            self.gsm.send_sms(PHONE_NUMBER,
                              "SYSTEM START: Monitoring Active.")
            self.main_loop()

    def main_loop(self):
        """
        Continuous monitoring loop running every MOVEMENT_CHECK_INTERVAL seconds.

        Each iteration:
          1. Check serial buffer for incoming SMS commands (MAINTENANCE/RESUME)
          2. If monitoring active → read gyroscope → check threshold
          3. If maintenance mode → skip sensor check, show paused status
          4. Print live status to serial monitor for debugging
        """
        print("\nMonitoring for movement... (Text 'MAINTENANCE' to pause)")

        while True:
            # Step 1: Check for remote SMS commands from farmer
            sms_cmd = self.gsm.check_incoming_sms()

            if sms_cmd == "MAINTENANCE" and not self.maintenance_mode:
                # Farmer is doing repairs — pause alerts to avoid false alarms
                self.maintenance_mode = True
                print("\n[MODE] -> MAINTENANCE ACTIVATED")
                self.gsm.send_sms(PHONE_NUMBER,
                    "MODE CHANGE: Maintenance mode ON. Monitoring paused.")

            elif sms_cmd == "RESUME" and self.maintenance_mode:
                # Repairs done — resume normal theft monitoring
                self.maintenance_mode = False
                print("\n[MODE] -> MONITORING RESUMED")
                self.gsm.send_sms(PHONE_NUMBER,
                    "MODE CHANGE: Maintenance mode OFF. Monitoring resumed.")

            # Step 2: Execute monitoring or maintenance mode logic
            if not self.maintenance_mode:
                # Read all 3 gyroscope axes
                gx, gy, gz = self.mpu.get_gyro_data()

                # Compute 3D vector magnitude — combines all axes into
                # single movement value regardless of rotation direction
                magnitude = math.sqrt(gx**2 + gy**2 + gz**2)

                if magnitude > GYRO_THRESHOLD:
                    self.trigger_alert(magnitude)

                # Live status display on serial monitor (overwrites same line)
                print("Status: [SAFE] Magnitude: {:.2f}   ".format(magnitude),
                      end='\r')
            else:
                print("Status: [MAINTENANCE MODE] System Paused...   ",
                      end='\r')

            utime.sleep(MOVEMENT_CHECK_INTERVAL)

    def trigger_alert(self, mag):
        """
        Send SMS + voice call alert when movement threshold exceeded.
        ALERT_COOLDOWN prevents repeated alerts for the same event —
        if motor keeps vibrating, farmer only gets 1 alert per minute.

        Args:
            mag: Detected movement magnitude in degrees/second
        """
        now = time.time()

        # Check if enough time has passed since last alert
        if now - self.last_alert_time > ALERT_COOLDOWN:
            print(f"\n🚨 ALERT! Movement Detected: {mag:.2f}")

            # Send SMS with magnitude value for farmer's reference
            self.gsm.send_sms(PHONE_NUMBER,
                f"🚨 ALERT: Movement detected ({mag:.1f} deg/s)!")

            # Follow up with voice call — ensures farmer is notified
            self.gsm.make_call(PHONE_NUMBER)

            # Record alert time to enforce cooldown
            self.last_alert_time = now


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    try:
        system = MovementAlertSystem()
        system.start()
    except KeyboardInterrupt:
        print("\n⏹ System Terminated.")
