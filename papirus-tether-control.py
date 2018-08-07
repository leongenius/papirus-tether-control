#!/usr/bin/env python3
# Based on papirus-button example

from __future__ import print_function

import os
import sys
import string
import subprocess
from papirus import Papirus
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from time import sleep
from datetime import datetime, timedelta
from pyroute2 import IPDB
from pyroute2.dhcp.dhcp4socket import DHCP4Socket 
import RPi.GPIO as GPIO

# Check EPD_SIZE is defined
EPD_SIZE=0.0
if os.path.exists('/etc/default/epd-fuse'):
    exec(open('/etc/default/epd-fuse').read())
if EPD_SIZE == 0.0:
    print("Please select your screen size by running 'papirus-config'.")
    sys.exit()

# Running as root only needed for older Raspbians without /dev/gpiomem
if not (os.path.exists('/dev/gpiomem') and os.access('/dev/gpiomem', os.R_OK | os.W_OK)):
    user = os.getuid()
    if user != 0:
        print('Please run script as root')
        sys.exit()

# Command line usage
# papirus-buttons

hatdir = '/proc/device-tree/hat'

WHITE = 1
BLACK = 0

SIZE = 24

# Assume Papirus Zero
SW1 = 21
SW2 = 16
SW3 = 20 
SW4 = 19
SW5 = 26

# Check for HAT, and if detected redefine SW1 .. SW5
if (os.path.exists(hatdir + '/product')) and (os.path.exists(hatdir + '/vendor')) :
   with open(hatdir + '/product') as f :
      prod = f.read()
   with open(hatdir + '/vendor') as f :
      vend = f.read()
   if (prod.find('PaPiRus ePaper HAT') == 0) and (vend.find('Pi Supply') == 0) :
       # Papirus HAT detected
       SW1 = 16
       SW2 = 26
       SW3 = 20
       SW4 = 21
       SW5 = -1

# Constants
DOUBLE_PUSH_INTERVAL = timedelta(seconds=5)
REFRESH_INTERVAL = timedelta(seconds=60)
TIME_FMT = "%m/%d %H:%M:%S"
USB0 = "usb0"
USB1 = "usb1"
HALT_CMD = "halt"
REBOOT_CMD = "reboot"
# Other global states
CurrentTime = datetime.now()
NextRefresh = CurrentTime
PapirusDevice = None
LastShutdownPushTime = None
PendingShutdown = None
PendingReboot = None

def main(argv):
    global SIZE
    global PapirusDevice
    global CurrentTime

    GPIO.setmode(GPIO.BCM)

    GPIO.setup(SW1, GPIO.IN)
    GPIO.setup(SW2, GPIO.IN)
    GPIO.setup(SW3, GPIO.IN)
    GPIO.setup(SW4, GPIO.IN)
    if SW5 != -1:
        GPIO.setup(SW5, GPIO.IN)

    PapirusDevice = Papirus(rotation = int(argv[0]) if len(sys.argv) > 1 else 0)


    # Use smaller font for smaller displays
    if PapirusDevice.height <= 96:
        SIZE = 18

    PapirusDevice.clear()

    write_text(PapirusDevice, "Ready... SW1 + SW2 to exit.", SIZE)
    sleep (5.0)

    print("Starting...")

    while True:
        CurrentTime = datetime.now()
        forceRefresh = False
        try:
            # Exit when SW1 and SW2 are pressed simultaneously
            if (GPIO.input(SW1) == False) and (GPIO.input(SW2) == False) :
                write_text(PapirusDevice, "Exiting ...", SIZE)
                sleep(0.2)
                PapirusDevice.clear()
                sys.exit()

            if GPIO.input(SW1) == False:
                # Press twice to shutdown
                handleShutdown()
                forceRefresh = True
            elif GPIO.input(SW2) == False:
                # Press twice to reboot
                handleReboot()
                forceRefresh = True
            elif GPIO.input(SW3) == False:
                # switch to usb1
                switch_tether_device(USB1)
                forceRefresh = True
            elif GPIO.input(SW4) == False:
                # switch to usb0
                switch_tether_device(USB0)
                forceRefresh = True
    
            clear_pending_states(False)
            refresh_dashboard(forceRefresh)
        except Exception as ex:
            write_text(PapirusDevice, str(ex), SIZE)
        sleep(0.1)

def write_text(papirus, text, size):

    # initially set all white background
    image = Image.new('1', papirus.size, WHITE)

    # prepare for drawing
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', size)

    # Calculate the max number of char to fit on line
    line_size = (papirus.width / (size*0.65))

    current_line = 0
    text_lines = [""]

    # Compute each line
    for word in text.split():
        # If there is space on line add the word to it
        if (len(text_lines[current_line]) + len(word)) < line_size:
            text_lines[current_line] += " " + word
        else:
            # No space left on line so move to next one
            text_lines.append("")
            current_line += 1
            text_lines[current_line] += " " + word

    current_line = 0
    for l in text_lines:
        current_line += 1
        draw.text( (0, ((size*current_line)-size)) , l, font=font, fill=BLACK)

    papirus.display(image)
    papirus.partial_update()

def get_status():
    status = ""
    # line 1: current oif
    status += get_default_route_status()
    # line 2: last update time
    status += get_refresh_time_status()
    # line 3: "press again to shutdown"
    status += get_pending_reboot_status()
    status += get_pending_shutdown_status()
    return status

def get_default_route_status():
    try:
        with IPDB() as ipdb:
            try:
                defaultRoute = ipdb.routes['default']
            except KeyError as keyEx:
                return "No default route\n"
            else:
                ifIndex = defaultRoute.oif
                ifName = ipdb.interfaces[ifIndex].ifname
                gateway = defaultRoute.gateway
                return ifName + "/" + gateway + "\n" 
    except Exception as ex:
        return "Exception: " + ex + "\n"
    
def get_refresh_time_status():
    return CurrentTime.strftime(TIME_FMT) + "\n"

def get_pending_reboot_status():
    if (PendingReboot is not None):
        return "Press again to reboot\n"
    return ""

def get_pending_shutdown_status():
    if (PendingShutdown is not None):
        return "Press again to shutdown\n"
    return ""

def switch_tether_device(device):
    if (device is not None):
        with IPDB() as ipdb:
            interfaces = ipdb.interfaces
            ifNames = interfaces.keys()
            try:
                defaultRoute = ipdb.routes['default']
            except:
                pass
            else:
                if (device in ifNames):
                    interface = interfaces[device]
                    index = interface.index
                    defaultRoute.oif = index
                    # TODO: timeout after 5 seconds
                    '''
                    with DPCP4Socket(device) as dhclient:
                        dhclient.put()
                        dhcpLease = dhclient.get()
                        gateway = dhcpLease['options']['router'][0]
                        if gateway is not None:
                            defaultRoute.gateway = gateway
                    '''
                    ipdb.commit()

def refresh_dashboard(force=False):
    global NextRefresh
    if (force or should_refresh_dashboard()):
        NextRefresh = CurrentTime + REFRESH_INTERVAL
        dashboardStatus = get_status()
        print("Refreshed at: " + CurrentTime.strftime(TIME_FMT))
        if (PapirusDevice is not None):
            write_text(PapirusDevice, dashboardStatus, SIZE)

def should_refresh_dashboard():
    return NextRefresh <= CurrentTime

def clear_pending_states(force=False):
    global PendingShutdown
    global PendingReboot
    global NextRefresh
    if (PendingShutdown is not None):
        if (force or CurrentTime > PendingShutdown):
            NextRefresh = CurrentTime
            PendingShutdown = None
    
    if (PendingReboot is not None):
        if (force or CurrentTime > PendingReboot):
            NextRefresh = CurrentTime
            PendingReboot = None

def handleReboot():
    global PendingReboot
    if (PendingReboot is None):
        clear_pending_states(True)
        PendingReboot = CurrentTime + DOUBLE_PUSH_INTERVAL
    elif (CurrentTime <= PendingReboot):
        try:
            write_text(PapirusDevice, "Rebooting\n" + get_refresh_time_status(), SIZE)
            os.system(REBOOT_CMD)
        except Exception as ex:
            write_text(PapirusDevice, str(ex), SIZE)
        finally:
            clear_pending_states(True)

def handleShutdown():
    global PendingShutdown
    if (PendingShutdown is None):
        clear_pending_states(True)
        PendingShutdown = CurrentTime + DOUBLE_PUSH_INTERVAL
    elif (CurrentTime <= PendingShutdown):
        try:
            write_text(PapirusDevice, "Shuting down\n" + get_refresh_time_status(), SIZE)
            os.system(HALT_CMD)
        except Exception as ex:
            write_text(PapirusDevice, str(ex), SIZE)
        finally:
            clear_pending_states(True)

if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit('interrupted')
