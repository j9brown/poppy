# coding=utf-8
from __future__ import absolute_import
import math
from smbus2 import SMBus, i2c_msg

# Refer to datasheet: https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf
_CHIP_ADDRESS = 0x4c
_CHIP_PRODUCT_ID = 0x16
_CHIP_MANUFACTURER_ID = 0x5d

_REGISTER_TEMP_INTERNAL = 0x00
_REGISTER_TEMP_EXTERNAL_MSB = 0x01
_REGISTER_TEMP_EXTERNAL_LSB = 0x10
_REGISTER_STATUS = 0x02
_REGISTER_CONFIG = 0x03
_REGISTER_CONVERSION_RATE = 0x04
_REGISTER_LIMIT_INTERNAL_HIGH = 0x05
_REGISTER_LIMIT_EXTERNAL_HIGH_MSB = 0x07
_REGISTER_LIMIT_EXTERNAL_HIGH_LSB = 0x13
_REGISTER_LIMIT_EXTERNAL_LOW_MSB = 0x08
_REGISTER_LIMIT_EXTERNAL_LOW_LSB = 0x14
_REGISTER_LIMIT_TCRIT = 0x19
_REGISTER_LIMIT_TCRIT_HYSTERESIS = 0x21
_REGISTER_ALERT_MASK = 0x16
_REGISTER_IDEALITY_FACTOR = 0x17
_REGISTER_BETA_COMPENSATION = 0x18
_REGISTER_TACH_READING_LSB = 0x46
_REGISTER_TACH_READING_MSB = 0x47
_REGISTER_TACH_LIMIT_LSB = 0x48
_REGISTER_TACH_LIMIT_MSB = 0x49
_REGISTER_FAN_CONFIG = 0x4a
_REGISTER_FAN_SPIN_UP = 0x4b
_REGISTER_FAN_SETTING = 0x4c
_REGISTER_FAN_PWM_FREQ = 0x4d
_REGISTER_FAN_PWM_FREQ_DIVIDE = 0x4e
_REGISTER_FAN_LUT_HYSTERESIS = 0x4f
_REGISTER_FAN_LUT_T1 = 0x50
_REGISTER_FAN_LUT_S1 = 0x51
_REGISTER_AVERAGING_FILTER = 0xbf
_REGISTER_PRODUCT_ID = 0xfd
_REGISTER_MANUFACTURER_ID = 0xfe

_PWM_FREQ = 7 # 25.7 kHz
_PWM_FULL_DUTY = _PWM_FREQ * 2

_DEFAULT_TEMPERATURE_LIMITS = {
    "internal_temperature_high": 40,
    "external_temperature_low": 18,
    "external_temperature_high": 50,
    "external_temperature_critical": 60
}

_DEFAULT_TARGET_TEMPERATURE = 0

def _toSignedByte(x):
    return x if x < 128 else x - 256

class EMC2101():
    def __init__(self, bus_number):
        self._bus = SMBus(bus_number)
        self._internal_temperature = 0
        self._external_temperature = 0
        self._target_temperature = _DEFAULT_TARGET_TEMPERATURE
        self._temperature_limits = _DEFAULT_TEMPERATURE_LIMITS
        self._fan_speed = 0
        self._status = {
            "internal_temperature_high": False,
            "external_temperature_low": False,
            "external_temperature_high": False,
            "external_temperature_critical": False,
            "external_temperature_fault": False,
            "tach_fault": False
        }

        self._check_chip_id()
        self._configure_static()
        self._configure_temperature_limits()
        self._configure_temperature_target()
    
    def _check_chip_id(self):
        pid = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_PRODUCT_ID)
        mid = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_MANUFACTURER_ID)
        if pid != _CHIP_PRODUCT_ID or mid != _CHIP_MANUFACTURER_ID:
            raise AttributeError("EMC2101 not found on the I2C bus")

    def _configure_static(self):
        # Enable TACH function, disable STANDBY, enable PWM, enable bus timeouts,
        # enable TCRIT override, enable TRIC queuing.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_CONFIG, 0x87)

        # Perform 16 conversions per second to allow for better filtering.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_CONVERSION_RATE, 0x08)

        # Disable all interrupts because the interrupts are not wired up anyway.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_ALERT_MASK, 0xff)

        # Set ideality factor, using 1.0040 for a typical 2N3904 NPN transitor
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_IDEALITY_FACTOR, 0x0f)

        # Disable beta compensation since we're using a diode-connected transistor,
        # as per the data sheet's recommendations.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_BETA_COMPENSATION, 0x07)

        # Set tach limit to a minimum of 400 RPM to ensure fan spin up.
        # The Noctua NF-A8 fan has a minimum rotational speed of 450 RPM +/- 20%.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_TACH_LIMIT_LSB, 0xbc)
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_TACH_LIMIT_MSB, 0x34)

        # Set fan PWM frequency to 25.7 kHz using a 360 kHz base clock.
        # The Noctua NF-A8 fan recommends 25 kHz, acceptable range of 21-28 kHz.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_PWM_FREQ, _PWM_FREQ)
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_PWM_FREQ_DIVIDE, 1)

        # Set fan spin-up to drive the fan at 50% for up to 3.2 seconds until
        # the tach limit is reached.  Goal is to minimize start-up noise.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_SPIN_UP, 0x2f)

        # Turn the fan off when the LUT is not used.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_SETTING, 0)

        # Enable averaging level 2 to guard against electrical noise.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_AVERAGING_FILTER, 0x06)

    def _configure_temperature_limits(self):
        # Set temperature limits for status alerts.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_LIMIT_INTERNAL_HIGH,
                self._temperature_limits["internal_temperature_high"])
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_LIMIT_EXTERNAL_LOW_MSB,
                self._temperature_limits["external_temperature_low"])
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_LIMIT_EXTERNAL_LOW_LSB, 0)
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_LIMIT_EXTERNAL_HIGH_MSB,
                self._temperature_limits["external_temperature_high"])
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_LIMIT_EXTERNAL_HIGH_LSB, 0)
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_LIMIT_TCRIT,
                self._temperature_limits["external_temperature_critical"])
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_LIMIT_TCRIT_HYSTERESIS,
                self._temperature_limits["external_temperature_critical"] -
                self._temperature_limits["external_temperature_high"])

    def _configure_temperature_target(self):
        # Set fan configuration and look-up table.
        # The configuration register is written twice: first to make the LUT writable
        # and then to enable the LUT and make it read-only. Because the fan setting register
        # is initialized to zero, the fan will be turned off if the LUT remains disabled.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_CONFIG, 0x27)
        if self._target_temperature > 0:
            # Set hysteresis to a moderately low value to allow for more fine-grained control
            # of the temperature around the target.  Relies on the filtering to reduce
            # surges.
            self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_LUT_HYSTERESIS, 1)

            # Prepare a look-up table designed to keep the temperature close to the target.
            self._write_lut_entry(0, self._target_temperature, 0)
            self._write_lut_entry(1, self._target_temperature + 2, 20)
            self._write_lut_entry(2, self._target_temperature + 4, 40)
            self._write_lut_entry(3, self._target_temperature + 6, 60)
            self._write_lut_entry(4, self._target_temperature + 8, 80)
            self._write_lut_entry(5, self._target_temperature + 10, 100)
            self._write_lut_padding(6)
            self._write_lut_padding(7)

            # Enable the look-up table.
            self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_CONFIG, 0x07)

    def _write_lut_entry(self, index, temperature, duty_cycle):
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_LUT_T1 + index * 2,
                min(max(int(temperature), 0), 127))
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_LUT_S1 + index * 2,
                math.ceil(duty_cycle * _PWM_FULL_DUTY / 100))

    def _write_lut_padding(self, index):
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_LUT_T1 + index * 2, 0x7f)
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_FAN_LUT_S1 + index * 2, 0x3f)

    def close(self):
        self._bus.close()

    def poll(self):
        self._poll_internal_temperature()
        self._poll_external_temperature()
        self._poll_fan_speed()
        self._poll_status()

    def _poll_internal_temperature(self):
        t = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_TEMP_INTERNAL)
        self._internal_temperature = _toSignedByte(t)

    def _poll_external_temperature(self):
        # Read MSB first to latch LSB
        th = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_TEMP_EXTERNAL_MSB)
        tl = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_TEMP_EXTERNAL_LSB)
        self._external_temperature = _toSignedByte(th) + tl / 256

    def _poll_fan_speed(self):
        # Read LSB first to latch MSB (yes, this is the opposite of external temperature)
        tl = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_TACH_READING_LSB)
        th = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_TACH_READING_MSB)
        t = th * 256 + tl
        self._fan_speed = round(5400000 / t) if t > 0 and t < 65535 else 0

    def _poll_status(self):
        s = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_STATUS)
        self._status["internal_temperature_high"] = bool(s & 0x40)
        self._status["external_temperature_low"] = bool(s & 0x08)
        self._status["external_temperature_high"] = bool(s & 0x10)
        self._status["external_temperature_critical"] = bool(s & 0x02)
        self._status["external_temperature_fault"] = bool(s & 0x04)
        self._status["tach_fault"] = bool(s & 0x01)

    @property
    def internal_temperature(self):
        return self._internal_temperature

    @property
    def external_temperature(self):
        return self._external_temperature

    @property
    def target_temperature(self):
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, value):
        value = int(value)
        if value != self._target_temperature:
            self._target_temperature = value
            self._configure_temperature_target()

    @property
    def fan_speed(self):
        return self._fan_speed

    @property
    def status(self):
        return self._status

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
