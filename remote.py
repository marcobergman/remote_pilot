#!/usr/bin/env python

import RPi.GPIO as GPIO
import time
import serial
import os
import steer_into_wind

# ST2000 remote control with Raspberry Pi 2
# Marco Bergman 2019
#
#   +5V    (01) ---------------------+
#                                    |
#                                   +++
#               2 x NPN             | |
#               2 x 10k             | |
#                                   +++       c------o SEATALK
#                                    |     | /
#                              c-----+----b|<
#                   +---+   | /            | \
#   GPIO14 (08) ----+   +--b|<                e
#                   +---+   | \               |
#                              e              |
#                              |              |
#   GND    (03) ---------------+--------------+
#
# auto startup: add "python /root/remote.py &" in /etc/rc.local before the exit

# GPIO constants: connect switches to ground on these GPIO pins
AU = 24    # Auto       GPIO 24 (pin# 18) BROWN
M1 = 22    # Minus 1    GPIO 22 (pin# 15) ORANGE
M10 = 27   # Minus 10   GPIO 27 (pin# 13) GREEN
P10 = 17   # Plus 10    GPIO 17 (pin# 11) BLUE
P1 = 18    # Plus 1     GPIO 18 (pin# 12) YELLOW
SB = 23    # Standby    GPIO 23 (pin# 16) WHITE
BUZZER = 25 # Buzzer    GPIO 25 (pin# 22) WHITE

MODE_NORMAL = 1
MODE_STEER_INTO_WIND = 2

# Long press threshold
THRESHOLD = 10

def write_seatalk (xx, yy):
        # thanks to http://www.thomasknauf.de/seatalk.htm
        with serial.Serial() as ser:
                ser.baudrate = 4800
                ser.port = '/dev/serial0'
                ser.stopbits=serial.STOPBITS_ONE
                ser.bytesize=serial.EIGHTBITS

                ser.open()
                ser.parity = serial.PARITY_MARK
                ser.write(b'\x86')
                ser.parity = serial.PARITY_SPACE
                ser.write(b'\x11' + chr(int(xx, 16)) + chr(int(yy, 16)))
                ser.close()


GPIO.setmode(GPIO.BCM)
GPIO.setup(SB, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Stand By:   1
GPIO.setup(AU, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Auto:       2
GPIO.setup(P1, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # +1:         4
GPIO.setup(P10, GPIO.IN, pull_up_down=GPIO.PUD_UP) # +10:        8
GPIO.setup(M10, GPIO.IN, pull_up_down=GPIO.PUD_UP) # -10:       16
GPIO.setup(M1, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # -1:        32
GPIO.setup(BUZZER, GPIO.OUT)


def beep(b):
        if ( b == 1 ):
                GPIO.output(BUZZER, 1)
                time.sleep(0.1)
                GPIO.output(BUZZER, 0)
        if ( b == 2 ):
                GPIO.output(BUZZER, 1)
                time.sleep(0.2)
                GPIO.output(BUZZER, 0)
        if ( b == 3 ):
                beep(1)
                time.sleep(0.1)
                beep(1)


beep(3)

mode=MODE_NORMAL

while 1:
        # wait for a button to be pressed
        while (GPIO.input(SB) == 1 and GPIO.input(AU) == 1 and GPIO.input(P1) == 1 and GPIO.input(P10) == 1 and GPIO.input(M10) == 1 and GPIO.input(M1) == 1):
                time.sleep (0.05)

        # wait for a possible second one or the key to be finished vibrating
        time.sleep (0.05)

        # store the key (combination) in one variable
        key = (1-GPIO.input(SB)) + 2*(1-GPIO.input(AU)) + 4*(1-GPIO.input(P1)) + 8*(1-GPIO.input(P10)) + 16*(1-GPIO.input(M10)) + 32*(1-GPIO.input(M1));

        # wait for a long press. Actually, there are no real interesting long presses to implement.
        counter = 0.1
        while (1==2): # (GPIO.input(SB) == 1 and GPIO.input(AU) == 1 and GPIO.input(P1) == 1 and GPIO.input(P10) == 1 and GPIO.input(M10) == 1 and GPIO.input(M1) == 1):
                time.sleep (0.1)
                counter = counter + 1
                if (counter > THRESHOLD):
                        # Long press
                        counter = -1000;
                        print "Long " + str(key)
                        # Standby
                        if (key == 1):
                                print "Standby (" + str(key) + ")"
                                write_seatalk("02", "FD")
                        beep(2)

        # Short press
        if (counter > 0):

                # Stand by
                if (key == 1):
                        print "Stand by (" + str(key) + ")"
                        write_seatalk("02", "FD")
                        beep(2)
                # Auto
                if (key == 2):
                        print "Auto (" + str(key) + ")"
                        write_seatalk("01", "FE")
                        beep(1)

                # +1
                if (key == 4):
                        print "+1 (" + str(key) + ")"
                        write_seatalk("07", "F8")
                        beep(1)
                # +10
                if (key == 8):
                        print "+10 (" + str(key) + ")"
                        write_seatalk("08", "F7")
                        beep(2)
                # -10
                if (key == 16):
                        print "-10 (" + str(key) + ")"
                        write_seatalk("06", "F9")
                        beep(2)
                # -1
                if (key == 32):
                        print "-1 (" + str(key) + ")"
                        write_seatalk("05", "FA")
                        beep(1)

                # Track -10 & +10
                if (key == 24):
                        print "Track (" + str(key) + ")"
                        write_seatalk("28", "D7")
                        beep(3)
                # Tack Port -1 & -10
                if (key == 48):
                        print "Tack Port (" + str(key) + ")"
                        write_seatalk("21", "DE")
                        beep(3)
                # Tack Starboard +1 & +10
                if (key == 12):
                        print "Tack Starboard (" + str(key) + ")"
                        write_seatalk("22", "DD")
                        beep(3)
                # Toggle auto seastate +1 & -1
                if (key == 36):
                        print "Toggle auto seastate (" + str(key) + ")"
                        write_seatalk("20", "DF")
                        beep(3)

                if (key == 3 and mode == MODE_NORMAL):
                        print "Steer into wind"
                        steer_into_wind.steer_into_wind()


                try:
                        os.system('ssh tc@10.10.10.3 "echo ' + str(key) + ' > /tmp/remote"')
                except:
                        pass

        # Wait for key to be lifted
        while  (GPIO.input(SB) == 0 or GPIO.input(AU) == 0 or GPIO.input(P1) == 0 or GPIO.input(P10) == 0 or GPIO.input(M10) == 0 or GPIO.input(M1) == 0):
                time.sleep (0.1)
