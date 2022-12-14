#!/usr/bin/env python3
import argparse
import sys

from src.parser import Parser
from src.apkParser import APKParser
from src.analyzer import Analyzer
from src.constants import ANDROID_MAX_SDK
import logging
from src.utils import CustomFormatter
from src.external import downloadAPK
import tempfile
import xml.etree.ElementTree


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description='Utility to analyse Android Manifest files.')
    argparser.add_argument('--log-level', '-v', type=int, choices=[0, 1, 2], help='Sets the log level', default=0)
    argparser.add_argument("path", help="The path to the manifest file.")
    argparser.add_argument("--min-sdk-version", '-min', type=int, choices=range(1, ANDROID_MAX_SDK+1),
                           help='Indicate the minimum version supported by your application',
                           metavar=f"[1,{ANDROID_MAX_SDK}]", required=True)
    argparser.add_argument("--max-sdk-version", '-max', type=int, choices=range(1, ANDROID_MAX_SDK+1),
                           help='Indicate the maximum version supported by your application',
                           metavar=f"[1,{ANDROID_MAX_SDK}]", required=True)
    argparser.add_argument('--adb', action="store_true", help='Indicates to use ADB. The path argument is treated as '
                                                              'the app\'s package name')
    args = argparser.parse_args()
    assert args.min_sdk_version <= args.max_sdk_version, "min SDK version cannot be higher than max SDK version"

    # silence https://github.com/appknox/pyaxmlparser/blob/d111a4fc6330a0c293ffc2f114af360eb78ad2ef/pyaxmlparser
    # /stringblock.py#L208
    logging.getLogger("pyaxmlparser.stringblock").setLevel(logging.CRITICAL)
    # silence https://github.com/appknox/pyaxmlparser/blob/d111a4fc6330a0c293ffc2f114af360eb78ad2ef/pyaxmlparser
    # /arscparser.py#L150
    logging.getLogger("pyaxmlparser.arscparser").setLevel(logging.CRITICAL)

    logger = logging.getLogger("MainLogger")
    logger.setLevel(logging.INFO)
    if args.log_level == 1:
        logger.setLevel(logging.WARNING)
    elif args.log_level == 2:
        logger.setLevel(logging.ERROR)

    # Create stdout handler for logging to the console
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(CustomFormatter())
    # Add handlers to the logger
    logger.addHandler(stdout_handler)

    with tempfile.TemporaryDirectory() as tmpPath:
        packageName = None
        if args.adb:
            packageName = args.path
            args.path = downloadAPK(args.path, tmpPath)

            if args.path is None:
                logger.error("Invalid package name !")
                sys.exit(1)

        try:
            # try as APK
            parser = APKParser(args.path)
            if parser.apk is None:
                # not an APK file
                parser = Parser(args.path)
            analyzer = Analyzer(parser, args)
            analyzer.packageName = packageName
            analyzer.runAllTests()

        except FileNotFoundError:
            logger.error("Invalid file name !")
        except xml.etree.ElementTree.ParseError:
            logger.error("Invalid file !")
        finally:
            sys.exit(1)
