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
from copy import deepcopy

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
        "name": "SKTECH_WEBHOOK",
        "method": "POST",
        "body": {
            "source": "{name}",
            "origin": "{name}",
            "message": "**{name} Error** → Server is not running please check asap.",
            "hashTag": "#MidDayData",
        },
        "headers": {
            "authorization": config.get("WEBHOOK_TOKEN"),
            "Content-Type": "application/json",
        },
        "url": config.get("WEBHOOK_URL"),
        "condition": lambda current_time: True,
    },
    {
        "name": "PAGER_DUTY",
        "method": "POST",
        "body": {
            "incident": {
                "type": "incident",
                "title": "**{name} Error** → Server is not running please check asap.",
                "service": {
                    "id": config.get("PAGER_DUTY_SERVICE_ID"),
                    "type": "service_reference",
                },
                "body": {
                    "type": "incident_body",
                    "details": "{name} Server is not running please check asap.",
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
        "condition": lambda current_time: False,
    },
    {
        "name": "PAGER_DUTY_EVENT",
        "method": "POST",
        "body": {
            "payload": {
                "summary": "**{name} Error** → Server is not running please check asap.",
                "severity": "critical",
                "source": "{name}",
            },
            "routing_key": config.get("PAGER_DUTY_INTEGRATION_KEY"),
            "event_action": "trigger",
            "dedup_key": "{name}",
        },
        "headers": {
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Authorization": f"Token token={config.get('PAGER_DUTY_API_KEY')}",
            "Content-Type": "application/json",
            "From": config.get("PAGER_DUTY_EMAIL"),
        },
        "url": config.get("PAGER_DUTY_EVENT_URL"),
        "condition": lambda current_time: True,
    },
    {
        "name": "TWILIO_SMS",
        "method": "POST",
        "body": {
            "To": config.get("SMS_TO"),
            "MessagingServiceSid": config.get("SMS_SID"),
            "Body": "**{name}** → SK404 Server is not running please check asap.",
        },
        "headers": {
            "Authorization": config.get("SMS_AUTH"),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        "url": config.get("SMS_URL"),
        "condition": lambda current_time: False,
    },
]


def _update_dict(notification, service):
    for k, v in notification.items():
        if isinstance(v, collections.abc.Mapping):
            notification[k] = _update_dict(notification.get(k, {}), service)
        elif isinstance(v, list):
            for l in v:
                l = _update_dict(l, service)
        elif isinstance(v, str):
            notification[k] = v.format(name=service.get("name"))
        elif isinstance(v, int) or isinstance(v, float) or isinstance(v, bool):
            notification[k] = v
        else:
            raise Exception("unknown type in update_dict")
    return notification


def alert(service):
    logging.info(f"Service is not running : {service}")
    for notification in deepcopy(NOTIFICATION_CHANNELS):
        try:
            current_time = datetime.now(IST)
            if not notification.get("condition", lambda a: True)(current_time):
                logging.info(
                    f"Condition not met for notification : {notification.get('name')} → {current_time}"
                )
                continue
            payload = {}
            payload = _update_dict(notification.get("body", {}).copy(), service)
            s = requests.Session()
            retries = Retry(
                total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
            )
            s.mount("http://", HTTPAdapter(max_retries=retries))

            if notification.get("method") == "GET":
                r = s.get(notification.get("url"))
                logging.info(f"Response  : {r.text}")

            elif notification.get("method") == "POST":
                r = s.post(
                    notification.get("url"),
                    data=json.dumps(payload),
                    headers=notification.get("headers", {}),
                )
                logging.info(f"Response  : {r.text}")

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
                        and all(i in cmdline for i in service.get("args"))
                    ):
                        found = True
                        break
                except psutil.AccessDenied:
                    pass
                except:
                    logging.exception(f"Error for pid : {process}")
            print("\n")
            logging.info(f"Found status for service : {service}  is  → {found}")
            if not found:
                # alert that service is not running
                alert(service)


if __name__ == "__main__":
    execute()
