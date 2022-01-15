#! /usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import
from pca9685 import PCA9685
import sys

def main():
    with PCA9685(11) as io:
        if len(sys.argv) == 2 and sys.argv[1] == "reset":
            io.reset()
            print("reset")
        elif len(sys.argv) == 4 and sys.argv[1] == "state":
            n = int(sys.argv[2])
            state = bool(int(sys.argv[3]))
            pin = io.pin(n)
            old = pin.state
            pin.state = state
            print("pin %s: state %s (was %s), timings %s" % (n, pin.state, old, pin.timings))
        elif len(sys.argv) == 4 and sys.argv[1] == "duty_cycle":
            n = int(sys.argv[2])
            duty_cycle = int(sys.argv[3])
            pin = io.pin(n)
            old = pin.duty_cycle
            pin.duty_cycle = duty_cycle
            print("pin %s: duty_cycle %s (was %s), timings %s" % (n, pin.duty_cycle, old, pin.timings))
        elif len(sys.argv) == 5 and sys.argv[1] == "timings":
            n = int(sys.argv[2])
            on_time = int(sys.argv[3])
            off_time = int(sys.argv[4])
            pin = io.pin(n)
            old = pin.timings
            pin.timings = (on_time, off_time)
            print("pin %s: timings %s (was %s)" % (n, pin.timings, old))
        else:
            print("Unrecognized command.")
            sys.exit(1)


if __name__ == "__main__":
    main()
