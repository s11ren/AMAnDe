#!/usr/bin/env python3
import unittest
from src.analyzer import Analyzer
from src.apkParser import APKParser
from collections import namedtuple
import logging
logging.disable(logging.CRITICAL)

class FakeParser(APKParser):
    # a fake parser class that allows init with no args
    def __init__(self):
        pass

class TestAnalyzer(unittest.TestCase):
    # We do not test the parser it is assumed the parsing is done correctly.
    # This allows much simpler unit tests writing. No need to generated custom manifests.
    parser = FakeParser()
    # fake args
    args = namedtuple("a", "log_level max_sdk_version min_sdk_version")
    args.log_level = "INFO"
    analyzer = Analyzer(parser, args)

    def test_isADBBackupAllowed(self):
        # the tuple elements represents :
        # allowBackup, expectedResult
        testCases = [
            (True, True),
            (False, False),
            (None, True)
        ]

        for testCase in testCases:
            allowBackup = testCase[0]
            expected = testCase[1]
            self.parser.allowBackup = lambda: allowBackup
            res = self.analyzer.isADBBackupAllowed()
            self.assertEqual(res, expected, f"{allowBackup=} should produce {expected} but produced {res}")

    def test_isAutoBackupAllowed(self):
        # the tuple elements represents :
        # allowBackup, max_sdk_version, expectedResult
        testCases = [
            (True, 12, False),
            (True, 25, True),
            (True, 23, True),
            (None, 23, True),
            (None, 25, True),
            (None, 13, False),
            (False, 13, False),
            (False, 23, False),
            (False, 26, False),
        ]
        self.args.min_sdk_version = 8
        for testCase in testCases:
            allowBackup = testCase[0]
            max_sdk_version = testCase[1]
            expected = testCase[2]
            self.parser.allowBackup = lambda: allowBackup
            self.args.max_sdk_version = max_sdk_version
            res = self.analyzer.isAutoBackupAllowed()
            self.assertEqual(res, expected, f"{allowBackup=} and {max_sdk_version=} should produce {expected} but produced {res}")

    #Do not manage to handle test with tuple
    def test_showApkInfo(self):
        # the tuple elements represents :
        # getSdkVersion[0] (uses_sdk_min_sdk_version), getSdkVersion[1](uses_sdk_max_sdk_version),
        # args_min_sdk_version, args_max_sdk_version, expectedResult
        testCases = [
            ((15, 30), 15, 30, 0),
            ((15, 30), 20, 30, 1),
            ((15, 30), 20, 30, 1),
            ((15, 30), 20, 31, 3),
            ((15, 30), 15, 31, 2),
            ((15, 30), 1, 30, 1),
            ((15, 30), 1, 31, 3),
            ((15, 30), 15, 0, 2),
            ((15, 30), 16, 0, 3),
            ((15, 30), 1, 0, 3),
            ((0, 0), 15, 30, 0),
            ((1, 0), 15, 30, 1),
            ((0, 4), 15, 30, 2),
            ((13, 4), 15, 30, 3),
            ((15, 0), 15, 30, 0),
            ((0, 30), 15, 30, 0),
            ((1, 30), 15, 30, 1),
        ]
        Info = namedtuple("Info", "package versionCode versionName")
        self.parser.getApkInfo = lambda: Info("pack", "12", "1.2")
        self.parser.componentStats = lambda x: 0
        self.parser.exportedComponentStats = lambda x: 0
        for testCase in testCases:
            getSdkVersion = testCase[0]
            min_sdk_version = testCase[1]
            max_sdk_version = testCase[2]
            expected = testCase[3]
            self.parser.getSdkVersion = lambda: getSdkVersion
            self.args.min_sdk_version = min_sdk_version
            self.args.max_sdk_version = max_sdk_version
            res = self.analyzer.showApkInfo()
            self.assertEqual(res, expected, f"{getSdkVersion=} and {min_sdk_version=} and {max_sdk_version=} should produce {expected} but produced {res}")

    def test_isBackupAgentImplemented(self):
        # the tuple elements represents :
        # backupAgent, expectedResult
        testCases = [
            (".MyBackupAgent", True),
            (None, False),
            ("", False),
        ]

        for testCase in testCases:
            backupAgent = testCase[0]
            expected = testCase[1]
            self.parser.backupAgent = lambda: backupAgent
            res = self.analyzer.isBackupAgentImplemented()
            self.assertEqual(res, expected, f"{backupAgent=} should produce {expected} but produced {res}")

    def test_getBackupRulesFile(self):
        # the tuple elements represents :
        # fullBackupContent, dataExtractionRules, expectedResult
        testCases = [
            ("test.xml", "test.xml", 3),
            (None, "test.xml", 2),
            ("test.xml", None, 1),
            (None, None, 0),
        ]

        for testCase in testCases:
            fullBackupContent = testCase[0]
            dataExtractionRules = testCase[1]
            expected = testCase[2]
            self.parser.fullBackupContent = lambda: fullBackupContent
            self.parser.dataExtractionRules = lambda : dataExtractionRules
            res = self.analyzer.getBackupRulesFile()
            self.assertEqual(res, expected, f"{fullBackupContent=} and {dataExtractionRules=} should produce {expected} but produced {res}")

    def test_getNetworkConfigFile(self):
        # the tuple elements represents :
        # networkSecurityConfig, expectedResult
        testCases = [
            ("network_security_config", True),
            (None, False)
        ]

        for testCase in testCases:
            networkSecurityConfig = testCase[0]
            expected = testCase[1]
            self.parser.networkSecurityConfig = lambda: networkSecurityConfig
            res = self.analyzer.getNetworkConfigFile()
            self.assertEqual(res, expected, f"{networkSecurityConfig=} should produce {expected} but produced {res}")

    def test_isDebuggable(self):
        # the tuple elements represents :
        # debuggable, expectedResult
        testCases = [
            (True, True),
            (False, False),
            (None,False)
        ]

        for testCase in testCases:
            debuggable = testCase[0]
            expected = testCase[1]
            self.parser.debuggable = lambda: debuggable
            res = self.analyzer.isDebuggable()
            self.assertEqual(res, expected, f"{debuggable=} should produce {expected} but produced {res}")


    def test_isCleartextTrafficAllowed(self):
        # the tuple elements represents :
        # usesCleartextTraffic, min_sdk_version, networkSecurityConfig, expectedResult
        testCases = [
            (True, 27, None, True),
            (True, 20, None, True),
            (True, 28, None, True),
            (False, 30, None, False),
            (None, 27, None, True),
            (None, 20, None, True),
            (None, 28, None, False),
            (None, 23, "bla", True),
            (True, 23, "bla", True),
            (False, 23, "bla", False),
            (None, 24, "bla", None),
            (True, 24, "bla", None),
            (False, 24, "bla", None),
        ]

        for testCase in testCases:
            usesCleartextTraffic = testCase[0]
            min_sdk_version = testCase[1]
            networkSecurityConfig = testCase[2]
            expected = testCase[3]
            self.parser.networkSecurityConfig = lambda: networkSecurityConfig
            self.parser.usesCleartextTraffic = lambda: usesCleartextTraffic
            self.args.min_sdk_version = min_sdk_version
            res = self.analyzer.isCleartextTrafficAllowed()
            self.assertEqual(res, expected, f"{usesCleartextTraffic=} and {min_sdk_version} should produce {expected} but produced {res}")

if __name__ == '__main__':
    unittest.main(buffer=True)