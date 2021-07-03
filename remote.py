#!/usr/bin/env python

import RPi.GPIO as GPIO
import time
import serial
import os
import socket
import threading


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
AU = 24    # Auto 	GPIO 24 (pin# 18) BROWN
M1 = 22    # Minus 1 	GPIO 22 (pin# 15) ORANGE
M10 = 27   # Minus 10 	GPIO 27 (pin# 13) GREEN
P10 = 17   # Plus 10 	GPIO 17 (pin# 11) BLUE
P1 = 18    # Plus 1 	GPIO 18 (pin# 12) YELLOW
SB = 23    # Standby 	GPIO 23 (pin# 16) WHITE
BUZZER = 25 # Buzzer 	GPIO 25 (pin# 22) WHITE

# RF 433 switches
AUR = 13    # Auto 	GPIO 24 (pin# 18) BROWN
M1R = 26   # Minus 1 	GPIO 22 (pin# 15) ORANGE
P1R = 19    # Plus 1 	GPIO 18 (pin# 12) YELLOW
SBR = 6     # Standby 	GPIO 23 (pin# 16) WHITE


MODE_NORMAL = 1
MODE_STEER_INTO_WIND = 2

# Long press threshold
THRESHOLD = 6

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
		ser.write(b'\x11')
		ser.write(xx)
		ser.write(yy)
		ser.close()

angle = 0
previous_angle = 0

listensocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listensocket.bind(("", 7001))
listensocket.listen(1)
print ("--- Listening to socket keys at TCP:7001")

remote_key = 0
keymap = {"s": 1, "a": 2, "u": 32, "i": 16, "o": 8, "p": 4}

def read_socket_thread():
	global remote_key
	while True:
		print ("Awaiting connection...")
		c,a = listensocket.accept()
		print ("Connection from: " + str(a) )
		while True:
			try:
				m,x = c.recvfrom(1024)
				if m:
					first_line = m.decode().split("\n")[0]
					line_elements = first_line.split(",")
					remote_key = keymap[line_elements[0]]
					print ("remote_key={}".format(remote_key))
				else:
					break;
			except Exception as e:
				print ("exception: " + str(e))
				pass
		print ("Disconnected")
	print ("Ending thread")


socket_thread = threading.Thread(target = read_socket_thread, daemon=True)
socket_thread.start()

def send_command(command):
	global angle
	print ("command="+str(command))

	if command == -10:
		write_seatalk(b'\x06', b'\xF9')
	if command == -1:
		write_seatalk(b'\x05', b'\xFA')
	if command == +1:
		write_seatalk(b'\x07', b'\xF8')
	if command == +10:
		write_seatalk(b'\x08', b'\xF7')
	angle = angle - command
	time.sleep(0.2)
		

def steer_to_angle(angle_to_steer_to):
	global angle
	angle = angle_to_steer_to

	while angle != 0:
		if angle <= -10:
			send_command(-10)
		if angle > -10 and angle < 0:
			send_command(-1)
		if angle > 0 and angle < 10:
			send_command(+1)
		if angle >= 10:
			send_command(+10)

def steer_into_wind():
	global previous_angle

	try:
		with open('/tmp/AWA', 'r') as myfile:
			line = myfile.read().replace("\n", "")
			awa = int(line)
	except:
		awa = 0

	angle=(awa+180) % 360-180
	previous_angle = angle
	print ("awa=" + str(awa) + "; angle=" + str(angle))

	steer_to_angle(angle)


def steer_previous_angle():
	global previous_angle

	steer_to_angle(-previous_angle)

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(SB, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Stand By:   1
GPIO.setup(AU, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Auto:       2
GPIO.setup(P1, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # +1:         4
GPIO.setup(P10, GPIO.IN, pull_up_down=GPIO.PUD_UP) # +10:        8
GPIO.setup(M10, GPIO.IN, pull_up_down=GPIO.PUD_UP) # -10:       16
GPIO.setup(M1, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # -1:        32

GPIO.setup(SBR, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Stand By:   1
GPIO.setup(AUR, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Auto:       2
GPIO.setup(P1R, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # +1:         4
GPIO.setup(M1R, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # -1:        32
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
	while (GPIO.input(SB) == 1 and GPIO.input(SBR) == 1 and GPIO.input(AU) == 1 and GPIO.input(AUR) == 1 and GPIO.input(P1) == 1 and GPIO.input(P1R) == 1 and GPIO.input(P10) == 1 and GPIO.input(M10) == 1 and GPIO.input(M1) == 1 and GPIO.input(M1R) == 1 and remote_key == 0):
		time.sleep (0.05)

	# wait for a possible second one or the key to be finished vibrating
	time.sleep (0.05)
	
	# store the key (combination) in one variable
	key = (1-GPIO.input(SB)) + (1-GPIO.input(SBR)) + 2*(1-GPIO.input(AU)) + 2*(1-GPIO.input(AUR)) + 4*(1-GPIO.input(P1)) + 4*(1-GPIO.input(P1R)) + 8*(1-GPIO.input(P10)) + 16*(1-GPIO.input(M10)) + 32*(1-GPIO.input(M1)) + 32*(1-GPIO.input(M1R)) + remote_key;
	remote_key = 0

	# wait for a long press. Actually, there are no real interesting long presses to implement.
	counter = 0
	while  (GPIO.input(SB) == 0 or GPIO.input(SBR) == 0 or GPIO.input(AU) == 0 or GPIO.input(AUR) == 0 or GPIO.input(P1) == 0 or GPIO.input(P1R) == 0 or GPIO.input(P10) == 0 or GPIO.input(M10) == 0 or GPIO.input(M1) == 0 or GPIO.input(M1R) == 0) and counter < 1000: 
		time.sleep (0.1)
		counter = counter + 1
		if (counter > THRESHOLD):
			# Long press
			counter = -1000;
			print ("Long " + str(key))
			# Standby
			if (key == 1):
				print ("Standby LONG (" + str(key) + ")")
				write_seatalk(b'\x02', b'\xFD')
			if (key == 4):
				key = 8
				counter = 1000;
			if (key == 32):
				key = 16
				counter = 1000;
			beep(2)

	# Short press
	if (counter > 0):

		# Stand by
		if (key == 1):
			print ("Stand by (" + str(key) + ")")
			beep(2)
			write_seatalk(b'\x02', b'\xFD')
			mode = MODE_NORMAL
		# Auto
		if (key == 2 and mode == MODE_NORMAL):
			print ("Auto (" + str(key) + ")")
			beep(1)
			write_seatalk(b'\x01', b'\xFE')
		# Auto steer back
		if (key == 2 and mode == MODE_STEER_INTO_WIND):
			print ("Steer previous wind angle")
			beep(3)
			steer_previous_angle()
			mode = MODE_NORMAL

		# +1
		if (key == 4): 
			print ("+1 (" + str(key) + ")")
			beep(1)
			write_seatalk(b'\x07', b'\xF8')
		# +10
		if (key == 8): 
			print ("+10 (" + str(key) + ")")
			beep(2)
			write_seatalk(b'\x08', b'\xF7')
		# -10
		if (key == 16): 
			print ("-10 (" + str(key) + ")")
			beep(2)
			write_seatalk(b'\x06', b'\xF9')
		# -1
		if (key == 32): 
			print ("-1 (" + str(key) + ")")
			beep(1)
			write_seatalk(b'\x05', b'\xFA')

		# Track -10 & +10
		if (key == 24): 
			print ("Track (" + str(key) + ")")
			beep(3)
			write_seatalk(b'\x28', b'\xD7')
		# Tack Port -1 & -10
		if (key == 48): 
			print ("Tack Port (" + str(key) + ")")
			beep(3)
			write_seatalk(b'\x21', b'\xDE')
		# Tack Starboard +1 & +10
		if (key == 12): 
			print ("Tack Starboard (" + str(key) + ")")
			beep(3)
			write_seatalk(b'\x22', b'\xDD')
		# Toggle auto seastate +1 & -1
		if (key == 36):
			print ("Toggle auto seastate (" + str(key) + ")")
			beep(3)
			write_seatalk(b'\x20', b'\xDF')

		if (key == 3 and mode == MODE_NORMAL):
			print ("Steer into wind")
			beep(3)
			steer_into_wind()
			mode = MODE_STEER_INTO_WIND
			

		try:
			os.system('ssh tc@10.10.10.3 "echo ' + str(key) + ' > /tmp/remote" & ')
		except:
			pass

	# Wait for key to be lifted
	while  (GPIO.input(SB) == 0 or GPIO.input(SBR) == 0 or GPIO.input(AU) == 0 or GPIO.input(AUR) == 0 or GPIO.input(P1) == 0 or GPIO.input(P1R) == 0 or GPIO.input(P10) == 0 or GPIO.input(M10) == 0 or GPIO.input(M1) == 0 or GPIO.input(M1R) == 0):
		time.sleep (0.1)

