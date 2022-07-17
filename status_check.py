#!/usr/bin/env python3

from datetime import datetime
import psutil
import logging
import sys
import requests
import pytz
from dotenv import dotenv_values
import os
import json

config = {
    **dotenv_values(".env"),
    **os.environ,
}

IST = pytz.timezone("Asia/Kolkata")
FORMAT = "%(asctime)s | %(message)s"
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=FORMAT)


SERVICES = json.load(open("services.json"))

NOTIFICATION_CHANNELS = [
    {
        "method": "POST",
        "body": {
            "source": "{args}",
            "origin": "{args}",
            "message": "**{args} Error** → Server is not running please check asap.",
            "hashTag": "#MidDayData",
        },
        "headers": {"authorization": config.get("WEBHOOK_TOKEN")},
        "url": config.get("WEBHOOK_URL"),
        "condition": lambda current_time: True,
    },
    {
        "method": "POST",
        "body": {
            "To": config.get("SMS_TO"),
            "MessagingServiceSid": config.get("SMS_SID"),
            "Body": "**{args}** → SK404 Server is not running please check asap.",
        },
        "headers": {
            "Authorization": config.get("SMS_AUTH"),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        "url": config.get("SMS_URL"),
        "condition": lambda current_time: current_time.hour >= 10
        and (
            (current_time.minute > 15 and current_time.minute < 30)
            or (current_time.minute > 45 and current_time.minute < 60)
        ),
    },
]


def alert(service):
    logging.info(f"Service is not running : {service}")
    for notification in NOTIFICATION_CHANNELS:
        try:
            current_time = datetime.now(IST)
            payload = {}
            logging.info(
                f"Current time in IST : {current_time}, hour : {current_time.hour}"
            )
            for k, v in notification.get("body", {}).items():
                payload[k] = v.format(args=service.get("args"))
            if notification.get("method") == "GET":
                if notification.get("condition", lambda a: True)(current_time):
                    r = requests.get(notification.get("url"))
                    logging.info(f"Response  : {r.text}")
                else:
                    logging.info(f"Condition not met fpr notification")
            elif notification.get("method") == "POST":
                if notification.get("condition", lambda a: True)(current_time):
                    r = requests.post(
                        notification.get("url"),
                        data=payload,
                        headers=notification.get("headers", {}),
                    )
                    logging.info(f"Response  : {r.text}")
                else:
                    logging.info(f"Condition not met for notification")
        except Exception as ex:
            logging.exception(f"Error while sending notification ")


def execute():
    for service in SERVICES:
        found = False
        for process in psutil.process_iter():
            try:
                if process.pid == int(service.get("processId", -1)):
                    found = True
                    break
                if (
                    service.get("processName", "")
                    and process.name().lower() == service.get("processName").lower()
                ):
                    found = True
                    break
                cmdline = process.cmdline()
                if cmdline and service.get("args") and service.get("args") in cmdline:
                    found = True
                    break
            except psutil.AccessDenied:
                pass
            except:
                logging.exception(f"Error for pid : {process}")
        logging.info(f"Found status for service : {service}  is  → {found}")
        if not found:
            # alert that service is not running
            alert(service)


# def run():
#     from time import sleep

#     while True:
#         print("run")
#         execute()
#         sleep(40)


if __name__ == "__main__":
    execute()
