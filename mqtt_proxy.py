#!/usr/bin/env python3

import yaml
import paho.mqtt.client as mqtt
import binascii
import os
import subprocess
import time
import threading

CONFIG_FILE = '/etc/mqtt_proxy.conf'
CONFIG=None
client=None

def get_config():
    with open(CONFIG_FILE, 'r') as ymlfile:
        config = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return config


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print('Connected with result code: {}'.format(mqtt.connack_string(rc)))
    command_topic = CONFIG['shows']['command_topic']
    print('Listening for commands on {}'.format(command_topic))
    client.subscribe(command_topic)


def lightshow_state():
    result = subprocess.run(['systemctl', 'is-active', '--quiet', 'lightshow'])
    if result.returncode == 0:
        return "on"
    else:
        return "off"


def lightshow_watcher():
    current_state = lightshow_state()
    state_topic = CONFIG['shows']['state_topic']

    while True:
        time.sleep(3)
        new_state = lightshow_state()
        if new_state != current_state:
            current_state = new_state
            print('publishing new state: {}'.format(current_state))
            client.publish(state_topic, current_state, retain=True)


def main():
    ### SETUP MQTT ###
    global CONFIG
    global client
    CONFIG = get_config()
    user = CONFIG['mqtt']['user']
    password = CONFIG['mqtt']['password']
    host = CONFIG['mqtt']['host']
    port = CONFIG['mqtt']['port']
    command_topic = CONFIG['shows']['command_topic']
    state_topic = CONFIG['shows']['state_topic']

    # print(user)
    # print(password)
    # print(host)
    # print(port)
    # print(command_topic)

    client = mqtt.Client(client_id="MQTTLightshow_" + binascii.b2a_hex(os.urandom(6)).decode(), clean_session=True, userdata=None, protocol=mqtt.MQTTv31)

    client.on_connect = on_connect

    client.username_pw_set(user, password=password)
    client.connect(host, port, keepalive=60)

    def on_message(client, userdata, msg):
        show_command = msg.payload.decode()
        print('command: {}'.format(show_command))
        if show_command == 'on':
            subprocess.run(['systemctl', 'start', 'lightshow'])
            print('lightshow started')
        elif show_command == 'off':
            subprocess.run(['systemctl', 'stop', 'lightshow'])
            print('lightshow stopped')
        else:
            print('Unknown command.')

    client.message_callback_add(command_topic, on_message)

    # Publish initial state
    client.publish(state_topic, lightshow_state(), retain=True)

    lightshow_watch_thread = threading.Thread(target=lightshow_watcher)
    lightshow_watch_thread.daemon = True
    lightshow_watch_thread.start()

    client.loop_forever()   


if __name__ == '__main__':
    main()
