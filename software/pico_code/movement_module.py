from machine import UART, Pin, I2C
import utime
import time
import math

# ==========================================
# CONFIGURATION
# ==========================================
GYRO_THRESHOLD = 4.0      # Sensitivity (degrees/second)
I2C_SCL_PIN = 9           # MPU6050 SCL
I2C_SDA_PIN = 8           # MPU6050 SDA
GSM_TX_PIN = 0            # GSM TX (Connect to Pico RX)
GSM_RX_PIN = 1            # GSM RX (Connect to Pico TX)

PHONE_NUMBER = "9370584716" 
MOVEMENT_CHECK_INTERVAL = 1
ALERT_COOLDOWN = 60       # 1 minute between alerts

# Commands
CMD_MAINTENANCE = "MAINTENANCE"
CMD_RESUME = "RESUME"

# ==========================================
# GSM MODULE CLASS
# ==========================================

class GSM_Module:
    def __init__(self, uart_id=0, baudrate=115200, tx_pin=GSM_TX_PIN, rx_pin=GSM_RX_PIN):
        self.gsm = UART(uart_id, baudrate=baudrate, tx=Pin(tx_pin), rx=Pin(rx_pin))
        utime.sleep(2)
        self.initialized = False
    
    def send_at(self, command, timeout=3000, wait_for_ok=True):
        self.gsm.write(command + '\r\n')
        start_time = utime.ticks_ms()
        response = ""
        while utime.ticks_diff(utime.ticks_ms(), start_time) < timeout:
            if self.gsm.any():
                chunk = self.gsm.read(self.gsm.any()).decode()
                response += chunk
            if wait_for_ok and ("OK" in response or "ERROR" in response):
                break
            utime.sleep(0.1)
        return response
    
    def initialize(self):
        print("📱 Initializing GSM...")
        self.send_at("AT")
        self.send_at("ATE0")       # Echo off
        self.send_at("AT+CMGF=1")  # SMS Text Mode
        # Set module to output new SMS content directly to serial
        self.send_at("AT+CNMI=1,2,0,0,0") 
        self.initialized = True
        return True

    def check_incoming_sms(self):
        """Scans serial buffer for command keywords"""
        if self.gsm.any():
            try:
                raw_data = self.gsm.read(self.gsm.any()).decode().upper()
                if CMD_MAINTENANCE in raw_data:
                    return "MAINTENANCE"
                elif CMD_RESUME in raw_data:
                    return "RESUME"
            except:
                pass
        return None

    def send_sms(self, phone_number, message):
        print(f"📤 Sending SMS to {phone_number}...")
        self.send_at('AT+CMGS="' + phone_number + '"', 5000, False)
        utime.sleep(0.5)
        self.gsm.write(message + '\x1A')
        utime.sleep(3)
        return True

    def make_call(self, phone_number, duration=20):
        print(f"📞 Calling {phone_number}...")
        self.send_at('ATD' + phone_number + ';', 5000)
        utime.sleep(duration)
        self.send_at("ATH") # Hang up
        return True

# ==========================================
# MPU6050 GYROSCOPE CLASS
# ==========================================

class MPU6050:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr
        self.wake_up()
    
    def wake_up(self):
        try:
            self.i2c.writeto_mem(self.addr, 0x6B, bytes([0x00]))
            print("✅ MPU6050 Active")
        except Exception as e:
            print("❌ MPU6050 Error:", e)
    
    def get_gyro_data(self):
        try:
            data = self.i2c.readfrom_mem(self.addr, 0x43, 6)
            # Combine high/low bytes
            x = self.tobits(data[0], data[1])
            y = self.tobits(data[2], data[3])
            z = self.tobits(data[4], data[5])
            return x/131.0, y/131.0, z/131.0
        except:
            return 0, 0, 0

    def tobits(self, high, low):
        val = (high << 8) | low
        if val > 32767: val -= 65536
        return val

# ==========================================
# MOVEMENT ALERT SYSTEM (MAIN LOGIC)
# ==========================================

class MovementAlertSystem:
    def __init__(self):
        self.gsm = GSM_Module()
        self.i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=400000)
        self.mpu = MPU6050(self.i2c)
        
        self.last_alert_time = 0
        self.maintenance_mode = False 

    def start(self):
        if self.gsm.initialize():
            print("🚀 System Online.")
            self.gsm.send_sms(PHONE_NUMBER, "SYSTEM START: Monitoring Active.")
            self.main_loop()

    def main_loop(self):
        print("\nMonitoring for movement... (Text 'MAINTENANCE' to pause)")
        
        while True:
            # 1. Check for Mode Selection SMS
            sms_cmd = self.gsm.check_incoming_sms()
            
            if sms_cmd == "MAINTENANCE" and not self.maintenance_mode:
                self.maintenance_mode = True
                print("\n[MODE] -> MAINTENANCE ACTIVATED")
                self.gsm.send_sms(PHONE_NUMBER, "MODE CHANGE: Maintenance mode ON. Monitoring paused.")
                
            elif sms_cmd == "RESUME" and self.maintenance_mode:
                self.maintenance_mode = False
                print("\n[MODE] -> MONITORING RESUMED")
                self.gsm.send_sms(PHONE_NUMBER, "MODE CHANGE: Maintenance mode OFF. Monitoring resumed.")

            # 2. Execute Mode Logic
            if not self.maintenance_mode:
                # Get sensor data
                gx, gy, gz = self.mpu.get_gyro_data()
                magnitude = math.sqrt(gx**2 + gy**2 + gz**2)
                
                if magnitude > GYRO_THRESHOLD:
                    self.trigger_alert(magnitude)
                
                print("Status: [SAFE] Magnitude: {:.2f}   ".format(magnitude), end='\r')
            else:
                print("Status: [MAINTENANCE MODE] System Paused...   ", end='\r')

            utime.sleep(MOVEMENT_CHECK_INTERVAL)

    def trigger_alert(self, mag):
        now = time.time()
        if now - self.last_alert_time > ALERT_COOLDOWN:
            print(f"\n🚨 ALERT! Movement Detected: {mag:.2f}")
            self.gsm.send_sms(PHONE_NUMBER, f"🚨 ALERT: Movement detected ({mag:.1f} deg/s)!")
            self.gsm.make_call(PHONE_NUMBER)
            self.last_alert_time = now

# ==========================================
# EXECUTION
# ==========================================
if __name__ == "__main__":
    try:
        system = MovementAlertSystem()
        system.start()
    except KeyboardInterrupt:
        print("\n⏹ System Terminated.")
