# coding=utf-8
from __future__ import absolute_import
import math
from smbus2 import SMBus, i2c_msg

# Refer to datasheet: https://cdn-shop.adafruit.com/product-files/4886/AW9523+English+Datasheet.pdf
_CHIP_ADDRESS = 0x58
_CHIP_ID = 0x23

_REGISTER_PORT_INPUT_BASE = 0x00
_REGISTER_PORT_OUTPUT_BASE = 0x02
_REGISTER_PORT_DIRECTION_BASE = 0x04
#_REGISTER_PORT_INTERRUPT_BASE = 0x06
_REGISTER_CONTROL = 0x07
_REGISTER_ID = 0x10
_REGISTER_PORT_MODE_BASE = 0x12
_REGISTER_PORT_CURRENT_BASE = 0x20
_REGISTER_RESET = 0x7f

class AW9523():
    def __init__(self, bus_number):
        self._bus = SMBus(bus_number)
        self._check_chip_id()
    
    def _check_chip_id(self):
        id = self._bus.read_byte_data(_CHIP_ADDRESS, _REGISTER_ID)
        if id != _CHIP_ID:
            raise AttributeError("AW9523 not found on the I2C bus")

    def reset(self):
        # Reset all registers to defaults.
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_RESET, 0x00)

        # Enable push-pull behavior on all pins.
        # Set drive current to 1/4 (~9.25 mA).
        self._bus.write_byte_data(_CHIP_ADDRESS, _REGISTER_CONTROL, 0x13)

    def input_pin(self, pin):
        if pin < 0 or pin > 15:
            raise AttributeError("Invalid pin number")
        self._write_port_bit(pin, _REGISTER_PORT_DIRECTION_BASE, True)
        self._write_port_bit(pin, _REGISTER_PORT_MODE_BASE, True)
        return AW9523.InputPin(self, pin)

    def output_pin(self, pin):
        if pin < 0 or pin > 15:
            raise AttributeError("Invalid pin number")
        self._write_port_bit(pin, _REGISTER_PORT_DIRECTION_BASE, False)
        self._write_port_bit(pin, _REGISTER_PORT_MODE_BASE, True)
        return AW9523.OutputPin(self, pin)

    def led_pin(self, pin):
        if pin < 0 or pin > 15:
            raise AttributeError("Invalid pin number")
        self._write_port_bit(pin, _REGISTER_PORT_MODE_BASE, False)
        return AW9523.LedPin(self, pin)

    def _read_port_bit(self, pin, base_reg):
        reg = base_reg if pin < 8 else base_reg + 1
        bit = 1 << (pin & 7)
        return bool(self._bus.read_byte_data(_CHIP_ADDRESS, reg) & bit)

    def _write_port_bit(self, pin, base_reg, state):
        reg = base_reg if pin < 8 else base_reg + 1
        bit = 1 << (pin & 7)
        old_value = self._bus.read_byte_data(_CHIP_ADDRESS, reg)
        new_value = old_value & ~bit
        if state:
            new_value |= bit
        if new_value != old_value:
            self._bus.write_byte_data(_CHIP_ADDRESS, reg, new_value)

    def close(self):
        self._bus.close()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    class InputPin():
        def __init__(self, io, pin):
            self._io = io
            self._pin = pin

        # State: True (high) or False (low)
        @property
        def state(self):
            return self._io._read_port_bit(self._pin, _REGISTER_PORT_INPUT_BASE)

    class OutputPin():
        def __init__(self, io, pin):
            self._io = io
            self._pin = pin

        # State: True (high) or False (low)
        @property
        def state(self):
            return self._io._read_port_bit(self._pin, _REGISTER_PORT_OUTPUT_BASE)

        @state.setter
        def state(self, value):
            value = bool(value)
            self._io._write_port_bit(self._pin, _REGISTER_PORT_OUTPUT_BASE, value)

    class LedPin():
        def __init__(self, io, pin):
            self._io = io
            if pin < 8:
                self._reg = _REGISTER_PORT_CURRENT_BASE + pin + 4
            elif pin < 12:
                self._reg = _REGISTER_PORT_CURRENT_BASE + pin - 8
            else:
                self._reg = _REGISTER_PORT_CURRENT_BASE + pin

        # LED current level: 0 (no current) to 255 (maximum current)
        def level(self, value):
            value = int(value)
            if value < 0 or value > 255:
                raise AttributeError("Level must be between 0 and 255")
            self._io._bus.write_byte_data(_CHIP_ADDRESS, self._reg, value)

        # No getter available because the register is not readable.
        level = property(None, level)
