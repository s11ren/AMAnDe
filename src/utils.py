#!/usr/bin/env python3

from termcolor import *
import logging
import requests


class CustomFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno == logging.INFO:
            pass
        elif record.levelno == logging.WARNING:
            record.msg = colored('[-] %s' % record.msg, "yellow")
        elif record.levelno == logging.CRITICAL:
            record.msg = colored('[!] %s' % record.msg, "red")
        else:
            print("[!] Logging level not recognized")

        return super(CustomFormatter, self).format(record)


def str2Bool(s):
    """
    Associates true or false string with their corresponding boolean
    """
    if s == "true":
        return True
    elif s == "false":
        return False
    else:
        return None


def getResourceTypeName(value):
    """
    Parses resources like @XXX/XXX and gets their values
    """
    path = ""
    if value is not None:
        resType, value = value.strip("@").split("/")
        if resType == "string":
            path += "strings.xml"
        if resType == "xml":
            path += f"{value}.xml"
            value = None
        if resType == "raw":
            path += value
            value = None
    return path, value


def printTestInfo(title):
    """
    Formats titles
    """
    print(colored(f"\n[*] {title}", "blue", attrs=['bold']))


def printSubTestInfo(title):
    """
    Formats subtitles (useful when there are multiple subtests associated with a kind of test)
    """
    print(colored(f"\n[+] {title}", "cyan"))


def checkDigitalAssetLinks(host):
    """
    Checks if Digital Asset Link JSON file is publicly available
    """
    try:
        if requests.get(f'https://{host}/.well-known/assetlinks.json').status_code == 200:
            return True
    except Exception:
        return False


def formatResource(path, name):
    """
    Formats a file name by adding an underline.
    If the resource is a string object, because we can't resolve the real value we format it like :
    strings.xml(value_name)
    This means the string can be found in the strings.xml file under the key "value_name".
    """
    filename = path
    res = colored(f"{filename}", attrs=["underline"])
    if name:
        # we have a string resource
        res = f"{res}({name})"
    return res


def unformatFilename(name):
    """
    Because Parser._getResValue formats filenames in a specific way
    we must undo the formatting to work with the raw string
    """
    return name[4:-4]


def runProc(*args, **kwargs):
    """
    Launches a subprocess that kills itself when its parent dies.

    :param args: The arguments to launch the subprocess.
    :type args: list[str]

    :return: The STDOUT output of the subprocess launched or None if the program does not exist.
    :rtype: bytes

    **Examples** ::
    TODO : Review this doc
        >>> runProc(["pwd"])
        b'/tmp/test\\n'
        >>> runProc(["echo", "hello"])
        b'hello\\n'
    """
    import subprocess
    p = None
    output = None
    output_stderr = None
    try:
        p = subprocess.Popen(stdout=subprocess.PIPE, *args, **kwargs)
        p.wait()
        output = p.stdout.read()
        output = p.stderr.read()
        p.stdout.close()
    finally:
        if p is not None and p.poll() is None:
            p.terminate()  # send sigterm, or ...
            p.kill()  # send sigkill
        return output, output_stderr


def handleVersion(lower_func, higher_func, trigger, min_sdk, max_sdk):
    """
    :param lower_func: Function taking a single boolean argument indicating if we need to print the condition.
    :param higher_func:
    :param trigger:
    :param min_sdk:
    :param max_sdk:
    :return:
    """
    if max_sdk < trigger:
        return lower_func()
    elif min_sdk >= trigger:
        return higher_func()
    else:
        a = lower_func(True)
        b = higher_func(True)
        return a, b
