#!/usr/bin/env python3

from datetime import datetime
import collections.abc
import psutil
import logging
import sys
import requests
from requests.adapters import HTTPAdapter, Retry
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
            "incident": {
                "type": "incident",
                "title": "**{args} Error** → Server is not running please check asap.",
                "service": {
                    "id": config.get("PAGER_DUTY_SERVICE_ID"),
                    "type": "service_reference",
                },
                "body": {
                    "type": "incident_body",
                    "details": "{args} Server is not running please check asap.",
                },
            }
        },
        "headers": {
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Authorization": f"Token token={config.get('PAGER_DUTY_API_KEY')}",
            "Content-Type": "application/json",
            "From": config.get("PAGER_DUTY_EMAIL"),
        },
        "url": config.get("PAGER_DUTY_URL"),
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


def update_dict(d, service):
    for k, v in d.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_dict(d.get(k, {}), service)
        elif isinstance(v, list):
            for l in v:
                l = update_dict(l, service)
        elif isinstance(v, str):
            d[k] = v.format(args=service.get("args"))
        elif isinstance(v, int) or isinstance(v, float) or isinstance(v, bool):
            d[k] = v
        else:
            raise Exception("unknown type in update_dict")
    return d


def alert(service):
    logging.info(f"\nService is not running : {service}")
    for notification in NOTIFICATION_CHANNELS:
        try:
            print("\n")
            current_time = datetime.now(IST)
            payload = {}
            logging.info(
                f"\nCurrent time in IST : {current_time}, hour : {current_time.hour}"
            )
            payload = update_dict(notification.get("body", {}), service)

            s = requests.Session()
            retries = Retry(
                total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
            )
            s.mount("http://", HTTPAdapter(max_retries=retries))

            if notification.get("method") == "GET":
                if notification.get("condition", lambda a: True)(current_time):
                    r = s.get(notification.get("url"))
                    logging.info(f"Response  : {r.text}")
                else:
                    logging.info(f"Condition not met fpr notification")
            elif notification.get("method") == "POST":
                if notification.get("condition", lambda a: True)(current_time):
                    r = s.post(
                        notification.get("url"),
                        data=json.dumps(payload),
                        headers=notification.get("headers", {}),
                    )
                    logging.info(f"Response  : {r.text}")
                else:
                    logging.info(f"Condition not met for notification")
        except Exception as ex:
            logging.exception(f"Error while sending notification ")


def execute():
    for service in SERVICES:
        if service:
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
                    if (
                        cmdline
                        and service.get("args")
                        and service.get("args") in cmdline
                    ):
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
