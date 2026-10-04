#!/usr/bin/env python3

import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from datetime import datetime

import requests
import paho.mqtt.publish as mqtt_publish


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

LOG_FILE = "/var/log/battery-monitor.log"

# Trigger when battery becomes <= these percentages
THRESHOLDS = [20, 10, 5]

# HTTP
HTTP_ENABLED = True
HTTP_ENDPOINT = "https://example.com/api/battery"

# MQTT
MQTT_ENABLED = True
MQTT_HOST = "192.168.1.100"
MQTT_PORT = 1883
MQTT_TOPIC = "home/laptop/battery"

MQTT_USERNAME = None
MQTT_PASSWORD = None

# ---------------------------------------------------------

last_percentage = None
triggered_thresholds = set()


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} | {message}"

    print(line, flush=True)

    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Unable to write log: {e}", flush=True)


def send_http(percentage, threshold):
    if not HTTP_ENABLED:
        return

    payload = {
        "device": "ubuntu-laptop",
        "percentage": percentage,
        "threshold": threshold,
        "timestamp": datetime.now().isoformat()
    }

    try:
        response = requests.post(
            HTTP_ENDPOINT,
            json=payload,
            timeout=10
        )

        log(
            f"HTTP notification sent "
            f"status={response.status_code} "
            f"threshold={threshold}%"
        )

    except Exception as e:
        log(f"HTTP notification failed: {e}")


def send_mqtt(percentage, threshold):
    if not MQTT_ENABLED:
        return

    payload = (
        f'{{'
        f'"device":"ubuntu-laptop",'
        f'"percentage":{percentage},'
        f'"threshold":{threshold},'
        f'"timestamp":"{datetime.now().isoformat()}"'
        f'}}'
    )

    try:

        auth = None

        if MQTT_USERNAME:
            auth = {
                "username": MQTT_USERNAME,
                "password": MQTT_PASSWORD
            }

        mqtt_publish.single(
            MQTT_TOPIC,
            payload=payload,
            hostname=MQTT_HOST,
            port=MQTT_PORT,
            auth=auth,
            qos=1,
            retain=False
        )

        log(f"MQTT notification sent threshold={threshold}%")

    except Exception as e:
        log(f"MQTT notification failed: {e}")


def notify(percentage, threshold):

    log(
        f"BATTERY ALERT percentage={percentage:.0f}% "
        f"threshold={threshold}%"
    )

    send_http(percentage, threshold)
    send_mqtt(percentage, threshold)


def check_thresholds(percentage):
    global triggered_thresholds

    for threshold in THRESHOLDS:

        # crossed / reached low threshold
        if percentage <= threshold:

            if threshold not in triggered_thresholds:

                triggered_thresholds.add(threshold)

                notify(
                    percentage,
                    threshold
                )

        else:
            # Battery has charged back above threshold.
            # Allow this threshold to trigger again later.
            triggered_thresholds.discard(threshold)


def property_changed(interface, changed, invalidated):

    global last_percentage

    if interface != "org.freedesktop.UPower.Device":
        return

    if "Percentage" not in changed:
        return

    percentage = float(changed["Percentage"])

    # Avoid duplicate event
    if last_percentage == percentage:
        return

    last_percentage = percentage

    log(f"Battery {percentage:.0f}%")

    check_thresholds(percentage)


# ---------------------------------------------------------
# DBUS / UPOWER
# ---------------------------------------------------------

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

bus = dbus.SystemBus()

upower = bus.get_object(
    "org.freedesktop.UPower",
    "/org/freedesktop/UPower"
)

upower_interface = dbus.Interface(
    upower,
    "org.freedesktop.UPower"
)

devices = upower_interface.EnumerateDevices()

battery_path = None

for device_path in devices:

    device = bus.get_object(
        "org.freedesktop.UPower",
        device_path
    )

    props = dbus.Interface(
        device,
        "org.freedesktop.DBus.Properties"
    )

    try:

        device_type = props.Get(
            "org.freedesktop.UPower.Device",
            "Type"
        )

        # UPower Type 2 = battery
        if int(device_type) == 2:
            battery_path = device_path
            break

    except Exception:
        pass


if not battery_path:
    raise RuntimeError("Battery device not found")


log(f"Using battery: {battery_path}")

battery = bus.get_object(
    "org.freedesktop.UPower",
    battery_path
)

properties = dbus.Interface(
    battery,
    "org.freedesktop.DBus.Properties"
)

current_percentage = float(
    properties.Get(
        "org.freedesktop.UPower.Device",
        "Percentage"
    )
)

last_percentage = current_percentage

log(f"Battery monitor started at {current_percentage:.0f}%")

check_thresholds(current_percentage)


battery.connect_to_signal(
    "PropertiesChanged",
    property_changed,
    dbus_interface="org.freedesktop.DBus.Properties"
)


GLib.MainLoop().run()
