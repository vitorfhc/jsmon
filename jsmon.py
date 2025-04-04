#!/usr/bin/env python3

import requests
import os
import hashlib
import json
import difflib
import jsbeautifier
import argparse
import uuid
from urllib.parse import urlparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from decouple import config

TELEGRAM_TOKEN = config("JSMON_TELEGRAM_TOKEN", default="CHANGEME")
TELEGRAM_CHAT_ID = config("JSMON_TELEGRAM_CHAT_ID", default="CHANGEME")
NOTIFY_TELEGRAM = config("JSMON_NOTIFY_TELEGRAM", default=False, cast=bool)
DISCORD_WEBHOOK_URL = config("JSMON_DISCORD_WEBHOOK_URL", default="CHANGEME", cast=str)
NOTIFY_DISCORD = config("JSMON_NOTIFY_DISCORD", default=False, cast=bool)


def is_valid_endpoint(endpoint):
    """Validate if the given endpoint is a valid URL.

    Args:
        endpoint (str): The URL to validate

    Returns:
        bool: True if the URL is valid, False otherwise
    """
    try:
        result = urlparse(endpoint)
        # Check if scheme and netloc are present
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_endpoint_list(endpointdir):
    endpoints = []
    filenames = []
    for dp, dirnames, files in os.walk(endpointdir):
        filenames.extend(files)
    filenames = list(filter(lambda x: x[0] != ".", filenames))
    for file in filenames:
        with open("{}/{}".format(endpointdir, file), "r") as f:
            endpoints.extend(f.readlines())

    # Load all endpoints from a dir into a list
    return list(map(lambda x: x.strip(), endpoints))


def get_endpoint(endpoint):
    # get an endpoint, return its content with timeout and error handling
    try:
        r = requests.get(endpoint, timeout=10, verify=False)
        r.raise_for_status()  # Raise an exception for bad status codes
        return r.text
    except requests.Timeout:
        print(f"Timeout error accessing endpoint: {endpoint}")
        return None
    except requests.RequestException as e:
        print(f"Error accessing endpoint {endpoint}: {e}")
        return None


def get_hash(string):
    # Hash a string
    if string is None:
        return None
    return hashlib.md5(string.encode("utf8")).hexdigest()[:10]


def save_endpoint(endpoint, ephash, eptext):
    # save endpoint content to file
    # add it to  list of
    with open("jsmon.json", "r") as jsm:
        jsmd = json.load(jsm)
        if endpoint in jsmd.keys():
            jsmd[endpoint].append(ephash)
        else:
            jsmd[endpoint] = [ephash]

    with open("jsmon.json", "w") as jsm:
        json.dump(jsmd, jsm)

    with open("downloads/{}".format(ephash), "w") as epw:
        epw.write(eptext)


def get_previous_endpoint_hash(endpoint):
    # get previous endpoint version
    # or None if doesnt exist
    with open("jsmon.json", "r") as jsm:
        jsmd = json.load(jsm)
        if endpoint in jsmd.keys():
            return jsmd[endpoint][-1]
        else:
            return None


def get_file_stats(fhash):
    return os.stat("downloads/{}".format(fhash))


def get_diff(old, new):
    from jsbeautifier import BeautifierOptions

    opt = {
        "indent_with_tabs": 1,
        "keep_function_indentation": 0,
    }
    options = BeautifierOptions(opt)
    oldlines = open("downloads/{}".format(old), "r").readlines()
    newlines = open("downloads/{}".format(new), "r").readlines()
    oldbeautified = jsbeautifier.beautify("".join(oldlines), options).splitlines()
    newbeautified = jsbeautifier.beautify("".join(newlines), options).splitlines()
    # print(oldbeautified)
    # print(newbeautified)

    differ = difflib.HtmlDiff()
    html = differ.make_file(oldbeautified, newbeautified)
    # open("test.html", "w").write(html)
    return html


def notify_telegram(endpoint, prev, new, diff, prevsize, newsize):
    print("[!!!] Endpoint [ {} ] has changed from {} to {}".format(endpoint, prev, new))
    log_entry = "{} has been updated from <code>{}</code>(<b>{}</b>Bytes) to <code>{}</code>(<b>{}</b>Bytes)".format(
        endpoint, prev, prevsize, new, newsize
    )
    payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": log_entry, "parse_mode": "HTML"}
    fpayload = {"document": ("diff.html", diff)}

    sendfile = requests.post(
        "https://api.telegram.org/bot{token}/sendDocument".format(token=TELEGRAM_TOKEN),
        files=fpayload,
        data=payload,
    )
    # print(sendfile.content)
    return sendfile
    # test2 = requests.post("https://api.telegram.org/bot{token}/sendMessage".format(token=TELEGRAM_TOKEN),
    #                         data=payload).content


def notify_discord(endpoint, prev, new, prevsize, newsize, diff_link):
    """Sends a notification to Discord via webhook."""

    webhook_data = {
        "username": "JSMon Bot",
        "avatar_url": "https://i.imgur.com/fKL31aD.jpg",  # Example avatar
        "embeds": [
            {
                "title": "JS Endpoint Updated!",
                "description": f"Endpoint: `{endpoint}`",
                "color": 3447003,  # Blue color
                "fields": [
                    {"name": "Previous Hash", "value": f"`{prev}`", "inline": True},
                    {"name": "New Hash", "value": f"`{new}`", "inline": True},
                    {
                        "name": "Previous Size",
                        "value": f"{prevsize} Bytes",
                        "inline": True,
                    },
                    {"name": "New Size", "value": f"{newsize} Bytes", "inline": True},
                    {
                        "name": "Diff Link",
                        "value": f"[View Diff]({diff_link})",
                        "inline": False,
                    },
                ],
                "footer": {"text": "JSMon Change Detection"},
            }
        ],
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=webhook_data, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        print(f"Discord notification sent successfully for {endpoint}.")
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error sending Discord notification for {endpoint}: {e}")
        return None


def notify_error_telegram(endpoint, error_message):
    print(f"[ERROR] Error accessing endpoint: {endpoint}")
    log_entry = (
        f"Error accessing endpoint <code>{endpoint}</code>: <b>{error_message}</b>"
    )
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": log_entry, "parse_mode": "HTML"}

    try:
        sendfile = requests.post(
            "https://api.telegram.org/bot{token}/sendMessage".format(
                token=TELEGRAM_TOKEN
            ),
            data=payload,
        )
        return sendfile
    except Exception as e:
        print(f"Failed to send Telegram error notification: {e}")
        return None


def notify_error_discord(endpoint, error_message):
    """Sends an error notification to Discord via webhook."""
    webhook_data = {
        "username": "JSMon Bot",
        "avatar_url": "https://i.imgur.com/fKL31aD.jpg",
        "embeds": [
            {
                "title": "JSMon Error Alert",
                "description": f"Error accessing endpoint: `{endpoint}`",
                "color": 15158332,  # Red color
                "fields": [
                    {
                        "name": "Error Message",
                        "value": f"```{error_message}```",
                        "inline": False,
                    }
                ],
                "footer": {"text": "JSMon Error Detection"},
            }
        ],
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=webhook_data, timeout=10)
        response.raise_for_status()
        print(f"Discord error notification sent successfully for {endpoint}.")
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error sending Discord error notification for {endpoint}: {e}")
        return None


def notify_error(endpoint, error_message):
    if NOTIFY_TELEGRAM:
        notify_error_telegram(endpoint, error_message)
    if NOTIFY_DISCORD:
        notify_error_discord(endpoint, error_message)


def notify(endpoint, prev, new, diff, diff_link):
    prevsize = get_file_stats(prev).st_size
    newsize = get_file_stats(new).st_size
    if NOTIFY_TELEGRAM:
        notify_telegram(endpoint, prev, new, diff, prevsize, newsize)

    if NOTIFY_DISCORD:
        notify_discord(endpoint, prev, new, prevsize, newsize, diff_link)


def main():
    print("JSMon - Web File Monitor")

    parser = argparse.ArgumentParser(
        description="Monitor web JavaScript files for changes."
    )
    parser.add_argument(
        "--diff-target",
        metavar="DIRECTORY",
        type=str,
        help="Directory to save HTML diff files.",
        default=None,
    )
    parser.add_argument(
        "--diffs-base-url",
        metavar="URL",
        type=str,
        help="Base URL for diff files.",
        default=None,
    )
    parser.add_argument(
        "--notify-on-errors",
        action="store_true",
        help="Send notifications when errors occur while accessing endpoints.",
    )
    args = parser.parse_args()

    diff_target_dir = args.diff_target
    notify_on_errors = args.notify_on_errors

    if args.diffs_base_url and not is_valid_endpoint(args.diffs_base_url):
        print(
            f"Error: Invalid URL provided for --diffs-base-url: {args.diffs_base_url}"
        )
        exit(1)

    if diff_target_dir:
        if not os.path.exists(diff_target_dir):
            try:
                os.makedirs(diff_target_dir)
                print(f"Created diff target directory: {diff_target_dir}")
            except OSError as e:
                print(f"Error creating directory {diff_target_dir}: {e}")
                diff_target_dir = None
        elif not os.path.isdir(diff_target_dir):
            print(
                f"Error: Specified diff target '{diff_target_dir}' is a file, not a directory."
            )
            diff_target_dir = None

    if not (NOTIFY_TELEGRAM or NOTIFY_DISCORD):
        print("You need to setup Telegram or Discord Notifications for JSMon to work!")
        exit(1)
    if NOTIFY_TELEGRAM and "CHANGEME" in [TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        print("Please Set Up your Telegram Token And Chat ID!!!")
    if NOTIFY_DISCORD and "CHANGEME" in [DISCORD_WEBHOOK_URL]:
        print("Please Set Up your Discord Webhook URL!!!")

    allendpoints = get_endpoint_list("targets")

    for ep in allendpoints:
        prev_hash = get_previous_endpoint_hash(ep)
        ep_text = get_endpoint(ep)
        if ep_text is None:
            if notify_on_errors:
                notify_error(ep, "Failed to access endpoint")
            print(f"Skipping endpoint {ep} due to failed request")
            continue

        ep_hash = get_hash(ep_text)
        if ep_hash == prev_hash:
            continue
        else:
            save_endpoint(ep, ep_hash, ep_text)
            diff = None
            diff_link = None
            if prev_hash is not None:
                diff = get_diff(prev_hash, ep_hash)
                if diff_target_dir:
                    id = str(uuid.uuid4())
                    diff_filepath = os.path.join(diff_target_dir, f"{id}.html")
                    with open(diff_filepath, "w") as f:
                        f.write(diff)
                    print(f"Diff saved locally to {diff_filepath}")
                    if args.diffs_base_url:
                        diff_link = f"{args.diffs_base_url}/{id}.html"
                notify(ep, prev_hash, ep_hash, diff, diff_link)
            else:
                print("New Endpoint enrolled: {}".format(ep))


main()
