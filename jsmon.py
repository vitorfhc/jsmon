#!/usr/bin/env python3

import requests
import os
import hashlib
import json
import difflib
import jsbeautifier
import argparse
import uuid
import signal
import sys
from urllib.parse import urlparse
import urllib3
from notifiers import DiscordNotifier
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

notifier = DiscordNotifier()

# Global flag to track if we should continue running
running = True


def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) gracefully."""
    global running
    print("Received interrupt signal. Exiting gracefully...")
    running = False
    sys.exit(0)


# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)


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
        r = requests.get(endpoint, timeout=10, verify=False, allow_redirects=False)

        # Check status code
        if not (200 <= r.status_code < 300):
            warning_msg = f"Non-2xx status code: {r.status_code}"
            raise Exception(warning_msg)

        return r
    except requests.RequestException as e:
        raise Exception(f"Error accessing endpoint {endpoint}: {e}")


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


def get_diff(old, new, content_type):
    from jsbeautifier import BeautifierOptions

    opt = {
        "indent_with_tabs": 1,
        "keep_function_indentation": 0,
    }
    options = BeautifierOptions(opt)
    old_filepath = f"downloads/{old}"
    new_filepath = f"downloads/{new}"

    try:
        with open(old_filepath, "r") as f_old, open(new_filepath, "r") as f_new:
            old_content = f_old.read()
            new_content = f_new.read()

        if "javascript" in content_type:
            old_lines = jsbeautifier.beautify(old_content, options).splitlines()
            new_lines = jsbeautifier.beautify(new_content, options).splitlines()
        else:
            old_lines = old_content.splitlines()
            new_lines = new_content.splitlines()

        differ = difflib.HtmlDiff()
        html = differ.make_file(old_lines, new_lines)
        return html
    except FileNotFoundError as e:
        print(f"Error generating diff: Could not find file {e.filename}")
        return f"<p>Error generating diff: Could not find file {e.filename}</p>"
    except Exception as e:
        print(f"Error generating diff between {old} and {new}: {e}")
        return f"<p>Error generating diff: {e}</p>"


def notify_error(endpoint, error_message):
    fields = [
        ("Error Type", "Endpoint Access Error"),
        ("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    notifier.notify_error(endpoint, error_message, fields)


def notify(endpoint, prev, new, diff_link):
    prevsize = get_file_stats(prev).st_size
    newsize = get_file_stats(new).st_size
    fields = [
        ("Previous Hash", f"`{prev}`"),
        ("New Hash", f"`{new}`"),
        ("Previous Size", f"{prevsize} Bytes"),
        ("New Size", f"{newsize} Bytes"),
    ]

    if diff_link is not None:
        fields.append(("Diff Link", f"[View Diff]({diff_link})"))

    notifier.notify_change(endpoint, fields)


def notify_warning(endpoint, warning_message):
    fields = [
        ("Warning Type", "Content Warning"),
        ("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    notifier.notify_warning(endpoint, warning_message, fields)


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
    args = parser.parse_args()

    diff_target_dir = args.diff_target

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

    allendpoints = get_endpoint_list("targets")

    for ep in allendpoints:
        if not running:
            break
        if ep.strip() == "":
            continue
        if not is_valid_endpoint(ep):
            notify_error(ep, "Invalid endpoint")
            print(f"Skipping endpoint {ep} due to invalid endpoint")
            continue
        prev_hash = get_previous_endpoint_hash(ep)
        try:
            response = get_endpoint(ep)
            ep_text = response.text.strip()
            content_type = response.headers.get("Content-Type", "").lower()

        except Exception as e:
            notify_error(ep, str(e))
            print(f"Skipping endpoint {ep} due to error: {e}")
            continue

        ep_hash = get_hash(ep_text)
        if ep_hash == prev_hash:
            continue
        else:
            save_endpoint(ep, ep_hash, ep_text)
            diff = None
            diff_link = None
            if prev_hash is not None:
                diff = get_diff(prev_hash, ep_hash, content_type)
                if diff_target_dir:
                    id = str(uuid.uuid4())
                    diff_filepath = os.path.join(diff_target_dir, f"{id}.html")
                    with open(diff_filepath, "w") as f:
                        f.write(diff)
                    print(f"Diff saved locally to {diff_filepath}")
                    if args.diffs_base_url:
                        diff_link = f"{args.diffs_base_url}/{id}.html"
                notify(ep, prev_hash, ep_hash, diff_link)
            else:
                print("New Endpoint enrolled: {}".format(ep))


main()
