#! /usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import
from emc2101 import EMC2101
import time

def main():
    with EMC2101(11) as fan:
        while True:
            fan.poll()
            print("fan: int %s, ext %s, tgt %s, spd %s, status %s" %
                (fan.internal_temperature,
                fan.external_temperature,
                fan.target_temperature,
                fan.fan_speed,
                fan.status))
            time.sleep(1.0 / 16)

if __name__ == "__main__":
    main()
