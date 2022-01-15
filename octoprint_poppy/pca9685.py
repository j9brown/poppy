# coding=utf-8
from __future__ import absolute_import
import math
from smbus2 import SMBus, i2c_msg

# Refer to datasheet: https://cdn-shop.adafruit.com/datasheets/PCA9685.pdf
_REGISTER_MODE1 = 0x00
_REGISTER_MODE2 = 0x01
#_REGISTER_SUBADR1 = 0x02
#_REGISTER_SUBADR2 = 0x03
#_REGISTER_SUBADR3 = 0x04
#_REGISTER_ALLCALLADR = 0x05
_REGISTER_LED_BASE = 0x06
_REGISTER_ALL_LED_BASE = 0xFA
_REGISTER_PRE_SCALE = 0xFE

_CLOCK_FREQ = 25000000

class PCA9685():
    def __init__(self, bus_number, unit = 0):
        self._bus = SMBus(bus_number)
        self._address = 0x40 + unit

    def reset(self, pwm_freq = 400):
        prescale = int(_CLOCK_FREQ / 4096 / pwm_freq) - 1
        if prescale < 3:
            raise AttributeError("PWM frequency too high")
        if prescale > 255:
            raise AttributeError("PWM frequency too low")

        # Although the chip supports a soft-reset function, it applies to all chips on
        # the bus rather than individual ones so we set up individual registers instead.

        # Enable PWM, auto-increment, ignore broadcast addresses, push-pull, no inversion.
        self._bus.write_byte_data(self._address, _REGISTER_MODE1, 0x20)

        # Change PWM output on I2C STOP, push-pull, no inversion, high impedance outputs
        # when output not enabled.
        self._bus.write_byte_data(self._address, _REGISTER_MODE2, 0x07)

        # Turn off all PWM channels.
        # Must happen after the MODE2 register's ACK mode bit is set.
        self._bus.write_i2c_block_data(self._address, _REGISTER_ALL_LED_BASE, [0x00, 0x00, 0x00, 0x10])

        # Set prescaler.
        self._bus.write_byte_data(self._address, _REGISTER_PRE_SCALE, prescale)

    def pin(self, pin):
        if pin < 0 or pin > 15:
            raise AttributeError("Invalid pin number")
        return PCA9685.Pin(self, pin)

    def close(self):
        self._bus.close()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    class Pin():
        def __init__(self, io, pin):
            self._io = io
            self._reg = _REGISTER_LED_BASE + pin * 4

        # Pin state: False (fully off), True (fully on), or None (unknown)
        @property
        def state(self):
            timings = self.timings
            if timings == (4096, 0):
                return True
            elif timings == (0, 4096):
                return False
            return None

        @state.setter
        def state(self, value):
            value = bool(value)
            if value:
                self.timings = (4096, 0)
            else:
                self.timings = (0, 4096)

        # Pin duty cycle: 0 (fully off) to 4096 (fully on) or None (unknown)
        @property
        def duty_cycle(self):
            timings = self.timings
            if timings == (4096, 0):
                return 4096
            elif timings == (0, 4096):
                return 0
            elif timings[0] == 0:
                return timings[1]
            return None

        @duty_cycle.setter
        def duty_cycle(self, value):
            value = int(value)
            if value < 0 or value > 4096:
                raise AttributeError("Value must be between 0 and 4096")
            if value == 4096:
                self.timings = (4096, 0)
            elif value == 0:
                self.timings = (0, 4096)
            else:
                self.timings = (0, value)

        # Pin PWM timings: tuple of on_time and off_time, each in the range 0 to 4096.
        # If on_time is 4096, pin is fully on.
        # If off_time is 4096, pin is fully off.
        @property
        def timings(self):
            data = self._io._bus.read_i2c_block_data(self._io._address, self._reg, 4)
            on_time = (data[1] << 8) + data[0]
            off_time = (data[3] << 8) + data[2]
            return (on_time, off_time)

        @timings.setter
        def timings(self, values):
            on_time = int(values[0])
            off_time = int(values[1])
            if on_time < 0 or on_time > 4096 or off_time < 0 or off_time > 4096:
                raise AttributeError("Values must be between 0 and 4096")
            self._io._bus.write_i2c_block_data(self._io._address, self._reg,
                    [on_time & 0xff, on_time >> 8, off_time & 0xff, off_time >> 8])
