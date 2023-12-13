import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn


import datetime
import logging

import asyncio

import aiocoap.resource as resource
import aiocoap
import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
import os
import glob
import time


#smoke module defs
SmokePin = 16
GPIO.setup(SmokePin, GPIO.IN)

#flame sensor defs
FlamePin = 17
GPIO.setup(FlamePin, GPIO.IN)
#tem[ sensor defs
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
GPIO.setwarnings(False) #disable warnings
# GPIO.setmode(GPIO.BOARD) #set pin numbering system


base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'

#variables for holidng true false values
SMOKE = 0
FLAME = 0
TEMP = 0


#buzzer Resources
GPIO.setup(12,GPIO.OUT)
def buzzerOn():
    GPIO.output(12,True)
    
def buzzerOff():
    GPIO.output(12,False)

def buzzerGetter(temp,smoke,flame):
    if smoke:
        if flame:
            #all 3
            if temp:
                print("All 3")
                for x in range(4):
                    buzzerOn()
                    time.sleep(5)
                    buzzerOff()
                    time.sleep(0.25)
            #smoke flame
            else:
                print("smoke flame")
                for x in range(4):
                    buzzerOn()
                    time.sleep(3)
                    buzzerOff()
                    time.sleep(0.5)
        #smoke temp
        elif temp:
            print("smoke temp")
            for x in range(4):
                buzzerOn()
                time.sleep(2)
                buzzerOff()
                time.sleep(0.5)
        #smoke only
        else:
            print("smoke only")
            for x in range(4):
                buzzerOn()
                time.sleep(0.75)
                buzzerOff()
                time.sleep(0.75)
    #flame only
    elif flame:
        print("Flame only")
        for x in range(4):
            buzzerOn()
            time.sleep(0.25)
            buzzerOff()
            time.sleep(0.25)
    #temp only
    elif temp:
        print("temp only")
        for x in range(4):
            buzzerOn()
            time.sleep(0.5)
            buzzerOff()
            time.sleep(0.5)
    #no beep
    else:
        print("None")
        buzzerOff()
        time.sleep(2)


class TimeResource(resource.ObservableResource):
    """Example resource that can be observed. The `notify` method keeps
    scheduling itself, and calles `update_state` to trigger sending
    notifications."""

    def __init__(self):
        super().__init__()

        self.handle = None

    def notify(self):
        self.updated_state()
        self.reschedule()

    def reschedule(self):
        self.handle = asyncio.get_event_loop().call_later(5, self.notify)

    def update_observation_count(self, count):
        if count and self.handle is None:
            print("Starting the clock")
            self.reschedule()
        if count == 0 and self.handle:
            print("Stopping the clock")
            self.handle.cancel()
            self.handle = None

    async def render_get(self, request):
        payload = datetime.datetime.now().\
                strftime("%Y-%m-%d %H:%M").encode('ascii')
        return aiocoap.Message(payload=payload)

class WhoAmI(resource.Resource):
    async def render_get(self, request):
        text = ["Used protocol: %s." % request.remote.scheme]

        text.append("Request came from %s." % request.remote.hostinfo)
        text.append("The server address used %s." % request.remote.hostinfo_local)

        claims = list(request.remote.authenticated_claims)
        if claims:
            text.append("Authenticated claims of the client: %s." % ", ".join(repr(c) for c in claims))
        else:
            text.append("No claims authenticated.")

        return aiocoap.Message(content_format=0,
                payload="\n".join(text).encode('utf8'))

class SmokeResource(resource.Resource):
    async def render_get(self, request):
        time.sleep(2)
        global SMOKE
        SMOKE = GPIO.input(16)
        if SMOKE:
            text = ["No Smoke!"]
            #invert value
            SMOKE = 0
        else:
            SMOKE = 1
            #invert value
            text = ["SMOKE!"]
        return aiocoap.Message(content_format=0,
                payload="\n".join(text).encode('utf8'))

class TempuratureResource(resource.Resource):


    def read_temp_raw(self):
        f = open(device_file, 'r')
        lines = f.readlines()
        f.close()
        return lines

    def read_temp(self):
        lines = self.read_temp_raw()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = self.read_temp_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = float(temp_string)/1000.0
            temp_f = temp_c * 9.0/5.0 + 32
            return temp_c
        
    async def render_get(self, request):
        global TEMP
        text = ["Current Tempurature: %s" % self.read_temp() + " C"]
        if self.read_temp() > 25:
            TEMP = 1
        else:
            TEMP = 0
        return aiocoap.Message(content_format=0,
                payload="\n".join(text).encode('utf8'))
    
class FlameResource(resource.Resource):
    async def render_get(self, request):
        time.sleep(2)
        global FLAME
        FLAME = GPIO.input(17)
        if FLAME:
            text = ["FlameDetected!"]
        else:
            text = ["No Flame"]
        return aiocoap.Message(content_format=0,
                payload="\n".join(text).encode('utf8'))

class LevelResource(resource.Resource):
    async def render_get(self, request):
        buzzerGetter(TEMP,SMOKE,FLAME)
        text = ["Smoke Detection: " + str(SMOKE) + "| Flame Detection: " + str(FLAME) + "| Temperature Detection: " + str(TEMP)]
        return aiocoap.Message(content_format=0,
                payload="\n".join(text).encode('utf8'))


# logging setup

logging.basicConfig(level=logging.INFO)
logging.getLogger("coap-server").setLevel(logging.DEBUG)

async def main():
    # Resource tree creation
    root = resource.Site()

    root.add_resource(['.well-known', 'core'],
            resource.WKCResource(root.get_resources_as_linkheader))
    root.add_resource(['time'], TimeResource())
    root.add_resource(['whoami'], WhoAmI())
    root.add_resource(['smoke'], SmokeResource())
    root.add_resource(['tempurature'], TempuratureResource())
    root.add_resource(['flame'], FlameResource())
    root.add_resource(['level'], LevelResource())

    await aiocoap.Context.create_server_context(root)
    # Run forever
    await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())
e6