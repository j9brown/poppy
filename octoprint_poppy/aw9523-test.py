#! /usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import
from aw9523 import AW9523
import sys

def main():
    with AW9523(11) as io:
        if len(sys.argv) == 2 and sys.argv[1] == "reset":
            io.reset()
        elif len(sys.argv) == 3 and sys.argv[1] == "input":
            n = int(sys.argv[2])
            pin = io.input_pin(n)
            print("input %s: %s" % (n, pin.state))
        elif len(sys.argv) == 4 and sys.argv[1] == "output":
            n = int(sys.argv[2])
            state = bool(int(sys.argv[3]))
            pin = io.output_pin(n)
            pin.state = state
            print("output %s: %s" % (n, pin.state))
        elif len(sys.argv) == 4 and sys.argv[1] == "led":
            n = int(sys.argv[2])
            level = int(sys.argv[3])
            pin = io.led_pin(n)
            pin.level = level
            print("led %s: %s" % (n, level))
        else:
            print("Unrecognized command.")
            sys.exit(1)


if __name__ == "__main__":
    main()
