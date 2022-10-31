from termcolor import colored
from tabulate import tabulate
from .utils import (
    CustomFormatter,
    printTestInfo,
    printSubTestInfo,
    checkDigitalAssetLinks,
    runProc
)
from .config import EXTERNAL_BINARIES
import logging
from .constants import dangerous_perms
from .apkParser import APKParser
from .networkSecParser import NetworkSecParser


class Analyzer():

    def __init__(self, parser, args):
        self.parser = parser
        self.args = args
        self.isAPK = type(self.parser) is APKParser
        self.logger = logging.getLogger(__name__)
        self.setLogLevel(args.log_level)

        # Create stdout handler for logging to the console (logs all five levels)
        stdout_handler = logging.StreamHandler()
        stdout_handler.setFormatter(CustomFormatter())
        # Add handlers to the logger
        self.logger.addHandler(stdout_handler)

    def setLogLevel(self, level):
        """
        Associates log levels to their corresponding logger levels
        """
        if level == 0:
            self.logger.setLevel(logging.INFO)
        elif level == 1:
            self.logger.setLevel(logging.WARNING)
        elif level == 2:
            self.logger.setLevel(logging.ERROR)
        else:
            raise NotImplementedError("Unknown logging level")

    def showApkInfo(self):
        """
        With a Manifest as input file: 
            Shows general information, including : 
                - Package name
                - VersionCode
                - VersionName
                - uses-sdk min and max version
                - Number of activities, services, receivers and providers (exported or not)
                - Required shared libraries
                - Required vendor-provided native shared librairies
                - Required hardware or software features

        With an APK as input file:
            Shows all the above information as well as the signature verification
        """
        printTestInfo("APK information")
        info = self.parser.getApkInfo()
        self.logger.info(f'Package name: {info.package}')
        if info.versionCode is not None: self.logger.info(f'Version code: {info.versionCode}')
        if info.versionName is not None: self.logger.info(f'Version name: {info.versionName}')

        versions = self.parser.getSdkVersion()
        uses_sdk_min_sdk_version = versions[0]
        uses_sdk_max_sdk_version = versions[1]
        min_sdk_version_args = self.args.min_sdk_version
        max_sdk_version_args = self.args.max_sdk_version
        warning_msg_1 = ""
        warning_msg_2 = ""
        res = 0

        if uses_sdk_min_sdk_version != 0 and uses_sdk_min_sdk_version != min_sdk_version_args:
            res |= 1
            warning_msg_1 += colored("(Mismatch between args "
                                     f"and uses-sdk tag : {uses_sdk_min_sdk_version})", "yellow")
        if uses_sdk_max_sdk_version != 0 and uses_sdk_max_sdk_version != max_sdk_version_args:
            res |= 2
            warning_msg_2 += colored("(Mismatch between args "
                                     f"and uses-sdk tag : {uses_sdk_max_sdk_version})", "yellow")

        self.logger.info(f'Minimal SDK version: {min_sdk_version_args} {warning_msg_1}')
        self.logger.info(f'Maximal SDK version: {max_sdk_version_args} {warning_msg_2}')
        if uses_sdk_max_sdk_version != 0:
            self.logger.warning("Declaring the android:maxSdkVersion attribute is not recommended. "
                                "Please check the official documentation")

        activities_number = self.parser.componentStats("activity")
        exported_activities_number = self.parser.exportedComponentStats("activity")
        self.logger.info(f'Number of activities: {activities_number} ({exported_activities_number} exported)')

        alias_activities_number = self.parser.componentStats("activity-alias")
        exported_alias_activities_number = self.parser.exportedComponentStats("activity-alias")
        self.logger.info(f'Number of activity-aliases: {alias_activities_number} ({exported_alias_activities_number} exported)')
        
        receivers_number = self.parser.componentStats("receiver")
        exported_receivers_number = self.parser.exportedComponentStats("receiver")
        self.logger.info(f'Number of receivers: {receivers_number} ({exported_receivers_number} exported)')

        providers_number = self.parser.componentStats("provider")
        exported_providers_number = self.parser.exportedComponentStats("provider")
        self.logger.info(f'Number of providers: {providers_number} ({exported_providers_number} exported)')

        services_number = self.parser.componentStats("service")
        exported_services_number = self.parser.exportedComponentStats("service")
        self.logger.info(f'Number of services: {services_number} ({exported_services_number} exported)')

        for l in self.parser.usesLibrary():
            self.logger.info(f'Shared library "{l.name}" can be used by the application (mandatory for runtime : {l.required})')

        for nl in self.parser.usesNativeLibrary():
            self.logger.info(f'Vendor provided shared native library "{nl.name}" can be used by the application (mandatory for runtime : {nl.required})')

        for f in self.parser.usesFeatures():
            self.logger.info(f'Hardware or software feature "{f.name}" can be used by the application (mandatory for runtime : {f.required})')
                
        # for now do it here
        # if we want to add post treatment we will move those kinds of checks into a new file
        if self.isAPK:
            cmd = EXTERNAL_BINARIES["apksigner"] + ["verify", "--print-certs", "--verbose", "--min-sdk-version",
                                                    str(self.args.min_sdk_version), self.args.path]
            cmdres = runProc(cmd)
            if cmdres:
                printSubTestInfo("Output of apksigner")
                self.logger.info(colored(f"executed command : {' '.join(cmd)}", "yellow"))
                self.logger.info(cmdres.decode())

        return res

    def analyzeRequiredPerms(self):
        """
        Lists all permissions required by the target APK
        Provides an analysis of builtin ones based on protectionLevel
        """
        printTestInfo("Analyzing required permissions")
        dangerous_perms_number = 0
        for perm in self.parser.requiredPermissions():
            if perm in dangerous_perms :
                if self.logger.level <= logging.WARNING:
                    print(colored(perm, "yellow"))
                dangerous_perms_number+=1
            else:
                self.logger.info(perm)
        if dangerous_perms_number > 0:
            if dangerous_perms_number == 1:
                msg = "permission"
            else:
                msg = "permissions"
            self.logger.warning(
                f'APK requires {dangerous_perms_number} dangerous builtin {msg} to work properly. Check it out!')

    def analyzeCustomPerms(self):
        """
        Analyzes custom permissions definitions based on protectionLevel
        """
        printTestInfo("Analyzing custom permissions definition")
        # Purpose : display custom permissions whose protectionLevel is inferior or equal to dangerous
        # because this means another malicious apps can require and get the permission
        table = []
        header = ["name", "protectionLevel"]
        custom_permissions = self.parser.customPermissions()
        dangerous_protection_level = 0


        for custom_permission in custom_permissions:
            name = custom_permission.name
            protectionLevel = custom_permission.protectionLevel

            if protectionLevel == "normal" or protectionLevel == "dangerous":
                name = colored(name,"red")
                protectionLevel = colored(protectionLevel,"red")
                table.append([name, protectionLevel])
                dangerous_protection_level+=1
            elif self.logger.level <= logging.INFO:
                table.append([name, protectionLevel])

        if len(table) > 0: print(tabulate(table, header, tablefmt="fancy_grid"))
        if dangerous_protection_level > 0:
            if dangerous_protection_level == 1:
                msg = "permission"
            else:
                msg = "permissions"
            self.logger.critical(
                f'APK declared {dangerous_protection_level} custom {msg} with a protectionLevel <= dangerous. Check it out!')

    def isADBBackupAllowed(self):
        """
        Checks if ADB backups are allowed (taking into account 
        Android versions and their corresponding default values).
        https://developer.android.com/guide/topics/manifest/application-element#allowbackup
        :return: True if ADB backup is allowed, False otherwise.
        """
        printSubTestInfo("Checking for ADB backup functionality")
        backup_attr = self.parser.allowBackup()

        # android:allowBackup default value is true for any android version
        if backup_attr or backup_attr is None:
            self.logger.info("ADB backup can be performed")
            return True
        self.logger.info("APK cannot be backed up with adb")
        return False

    def isAutoBackupAllowed(self):
        """
        Checks if Auto Backup are allowed (taking into account 
        Android versions and their corresponding default values).
        https://developer.android.com/guide/topics/data/autobackup
        :return: True if Auto Backup is allowed, False otherwise.
        """
        printSubTestInfo("Checking for auto-backup functionality")
        backup_attr = self.parser.allowBackup()
        MaxAPILevel = self.args.max_sdk_version
        MinAPILevel = self.args.min_sdk_version

        # android:allowBackup default value is true for any android version but auto backup is only available for API >= 23
        if (backup_attr or backup_attr is None) and MaxAPILevel >= 23:
            msg = "Google drive Auto backup functionality is activated "
            # Android 9 => API level >= 28
            if MinAPILevel >= 28:
                msg += colored("(E2E encrypted)", "green")
            elif MaxAPILevel < 28:
                msg += colored("(E2E encryption not available)", "red")
            else:
                msg += colored("(E2E encryption is only available from Android 9 (API level 28))", "yellow")
            self.logger.info(msg)
            return True
        self.logger.info("APK cannot be backed up with Auto Backup")
        return False

    def isBackupAgentImplemented(self):
        """
        Checks if a backup agent is implemented as a Java/Kotlin class.

        .. note::
        https://developer.android.com/guide/topics/manifest/application-element#agent

        :return: True if a backupAgent property has been found in Manifest, False otherwise.
        """
        printSubTestInfo("Checking for own developer backup agent")
        agent = self.parser.backupAgent()
        if agent:
            self.logger.warning(
                f'APK implements is own backup agent in {agent.split(".")[-1]}. Please make deeper checks')
            return True
        self.logger.info("No backup agent implementation has been found")
        return False

    def getBackupRulesFile(self):
        """
        With a Manifest as input file: 
            Checks the presence of attributes related to backup rules files (taking into account Android versions) 
            Analyses if the result is in line with min_sdk_version and max_sdk_version args.

        With an APK as input file:
            If there are one of those files, does the above and summarizes fullBackupContent and 
            dataExtractionRules files content in a table.
        
        Both tag can be specified together in the Manifest
        However, for all versions higher or equal than Android 12 (API 31), fullBakcupContent is overriden
        with datExtractionRules.
        """
        printSubTestInfo("Checking backup rules files")
        fullBackupContent_xml_file_rules = self.parser.fullBackupContent()
        dataExtractionRules_xml_rules_files = self.parser.dataExtractionRules()

        res = 0
        if self.args.min_sdk_version <= 30:
            if fullBackupContent_xml_file_rules is not None:
                self.logger.info(f'For Android versions <= 11 (API 30), custom rules has been defined to control what gets backed up in {fullBackupContent_xml_file_rules} file')
                res |= 1
                rules = self.parser.getFullBackupContentRules() or []
                headers = ["type", "domain", "path", "requireFlags"]
                table = [[e.type, e.domain, e.path, e.requireFlags] for e in rules]
                if len(table) > 0:
                    self.logger.info(tabulate(table, headers, tablefmt="fancy_grid"))
            else:
                self.logger.warning(f'Minimal supported SDK version ({self.args.min_sdk_version})'
                f' allows Android versions <= 11 (API 30) and no exclusion custom rules file has been specified in the fullBackupContent attribute.')
        if self.args.max_sdk_version >= 31:
            if dataExtractionRules_xml_rules_files is not None:
                self.logger.info(f'For Android versions >= 12 (API 31), custom rules has been defined to control what gets backed up in {dataExtractionRules_xml_rules_files} file')
                res |= 2
                cloudBackupRules, disableIfNoEncryptionCapabilities, deviceTransferRules = self.parser.getDataExtractionRulesContent()
                headers = ["type", "domain", "path", "requireFlags"]
                # show cloudBackupRules
                table = [[e.type, e.domain, e.path, e.requireFlags] for e in cloudBackupRules]
                if len(table) > 0:
                    # TODO :améliorer l'affichage de cette info
                    self.logger.info(f"{disableIfNoEncryptionCapabilities=}")
                    self.logger.info("Cloud backup rules have been defined :")
                    self.logger.info(tabulate(table, headers, tablefmt="fancy_grid"))
                # show device transfer rules
                table = [[e.type, e.domain, e.path, e.requireFlags] for e in deviceTransferRules]
                if len(table) > 0:
                    self.logger.info("Cloud backup rules have been defined :")
                    self.logger.info(tabulate(table, headers, tablefmt="fancy_grid"))
            else:
                self.logger.warning(f'Maximal supported SDK version ({self.args.max_sdk_version})'
                f' allows Android versions >= 12 (API 31) and no exclusion custom rules file has been specified in the dataExtractionRules attribute.')
        return res

    def getNetworkConfigFile(self):
        """
        With a Manifest as input file: 
            Checks the presence of network_security_config_file attribute

        With an APK as input file:
            Does the above and if applicable, summarizes network_security_config file content in a table (taking into account Android
            versions and their corresponding default values and configurations)
        """
        printTestInfo("Checking the existence of network_security_config XML file")
        network_security_config_xml_file = self.parser.networkSecurityConfig()
        if network_security_config_xml_file is not None:
            # TOTO : dans le cas d'un APK rajouter des sous tests
            # le cleartext traffic sera probablement géré dans le test a cet effet donc pas besoin de le faire ici
            # on peut checker le certificate pinning et les trust anchors ici dans 2 sous-tests
            # si pas un APK ca reste comme ça
            self.logger.info(f'APK network security configuration is defined in {network_security_config_xml_file} file')
            if self.isAPK : self.analyseNetworkSecurityConfigFile()
            return True
        self.logger.warning("networkSecurityConfig property not found")
        return False

    def analyzeBackupFeatures(self):
        """
        Regroups all functions related to backup analysis
        """
        printTestInfo("Analyzing backup functionality")
        isADBBackupAllowed = self.isADBBackupAllowed()
        isAutoBackupAllowed = self.isAutoBackupAllowed()
        if isADBBackupAllowed or isAutoBackupAllowed:
            self.getBackupRulesFile()
        self.isBackupAgentImplemented()

    def isDebuggable(self):
        """
        Checks if APK is compiled in debug mode
        Default value is False
        https://developer.android.com/guide/topics/manifest/application-element#debug
        """
        printTestInfo("Checking compilation mode")
        debuggable = self.parser.debuggable()
        if debuggable:
            self.logger.warning("Debuggable flag found. APK can be debugged on a device running in user mode")
            # flutter kernel_blob.bin
            path = 'assets/flutter_assets/kernel_blob.bin'
            if self.parser.hasFile(path):
                self.logger.critical(f"Flutter app is debuggable and source code can be found in the strings of {path}")
            return True
        self.logger.info("APK is not compiled in debug mode")
        return False
    
    def analyzeExportedComponent(self):
        """
        Analyzes exported components permissions
         - If the exported component does not specify any permission, highlight it with self.logger.warning
           to indicate deeper checks are required.
         - Do not add deeplinks or applinks, as they cannot have specific permissions (by default they are used to call our app when
           a specific URI is handled by another app)
        """
        printTestInfo("Analyzing permissions set on exported components")
        headers = ["Name", "Type", "Permission", "readPermission", "writePermission"]
        table = []
        # Getting deeplink (don't analyze exported component which is a deeplink)
        universal_links = self.parser.getUniversalLinks()
        # Getting a set of deeplink components' name
        unique_names = {universal_link.name for universal_link in universal_links}
        count = 0
        res = 0

        for component in ["activity", "receiver", "provider", "service"]:
            for e in self.parser.getExportedComponentPermission(component):
                if e.componentName not in unique_names:
                    n = e.componentName.split(".")[-1]
                    # Main activity is the entrypoint of our app. It's always exported without permission
                    # So do not add it
                    if n == "MainActivity":
                        continue
                    t = e.componentType
                    p = e.permission
                    # Keep entire permission name to make the difference between custom and builtin
                    rp = e.readPermission
                    wp = e.writePermission

                    if (t != "provider" and p is None) or (
                        t == "provider" and wp is None and rp is None and p is None):
                        cName = colored(n, "yellow")
                        cType = colored(t, "yellow")
                        if self.logger.level <= logging.WARNING:
                            table.append([cName, cType, p, rp, wp])
                            count += 1
                            res += 1
                    else:
                        if self.logger.level == logging.INFO:
                            table.append([n, t, p, rp, wp])
                            res += 2
        
        # There might not be any exported components -> no permission to analyze
        if len (table) > 0 :
            # no write permissions
            nowp = all([e[-1] == None for e in table])
            # no read permissions
            norp = all([e[-2] == None for e in table])
            # remove empty columns
            # start with the inner most column otherwise the index changes
            if norp:
                table = [e[:-2]+e[-1:] for e in table]
                headers.pop(-2)
            if nowp:
                table = [e[:-1] for e in table]
                headers.pop(-1)

            self.logger.info("Deeplinks are not shown in table below because they never have permissions")
            print(tabulate(table, headers, tablefmt="fancy_grid"))
        if count > 0:
            self.logger.warning(f'There are {count} exported components which can be called without any permission. Check it out!')
        return res

    def analyzeUnexportedProviders(self):
        """
        Analyses unexported providers whose grantUriPermissions attribute is set to True
        This information is useful because in combination with other vulnerabilities it 
        is possible to exploit those components
        """
        printTestInfo("Analyzing unexported providers")
        res = self.parser.getUnexportedProviders()
        msg = ""
        if len(res) == 1: msg = "provider"
        if len(res) > 1: msg = "providers"
        if len(res) > 0:
            self.logger.warning(f'Found {len(res)} unexported {msg} with grantUriPermissions set to True. Please make deeper checks!')
        if self.logger.level <= logging.WARNING:
            for e in res:
                print(f'\t{e}')

    def isCleartextTrafficAllowed(self):
        """
        With a Manifest as input file:
            Checks if the app intends to use cleartext network traffic, such as cleartext HTTP.
            https://developer.android.com/guide/topics/manifest/application-element#usesCleartextTraffic

        The default value for apps that target API level 27 or lower is "true". 
        Apps that target API level 28 or higher default to "false".
        This flag is ignored on Android 7.0 (API level 24) and above if an Android Network Security Config is present.

        With an APK as input file:
            Does the above and if applicable, summarizes network_security_config file content in a table (taking into account Android
            versions and there corresponding default values and configurations)
            
        """
        printTestInfo("Checking if http traffic can be used")
        network_security_config_xml_file = self.parser.networkSecurityConfig()
        if network_security_config_xml_file is not None and self.args.min_sdk_version >= 24:
            # TODO : a terme remplacer ça par un call vers une autre fonction qui analyse le contenu du network security config
            # pour specifiquement voir si HTTP est autorisé et pour quels domaines
            # evidement cela que dans le cas d'un APK, sinon ça reste comme ça je pense
            self.logger.info("APK network security configuration is defined. Please refer to this test instead.")
            return
        cleartextTraffic = self.parser.usesCleartextTraffic()
        if cleartextTraffic or (cleartextTraffic is None and self.args.min_sdk_version <= 27):
            self.logger.warning("This app may intend to use cleartext network traffic "
                "such as HTTP to communicate with remote hosts")
            return True
        self.logger.info("Usage of cleartext traffic is not allowed "
            "(this flag is honored as a best effort, please refer to the documentation)")
        return False

    def getIntentFilterInfo(self):
        """
        Displays information about exported components Intent Filter (scheme, host, port, path)
        """
        printTestInfo("Gathering information on exported components which specified Intent Filters")
        headers = ["Name", "Action", "Category", "Link", "Mime Type"]
        table = []
        for e, tag in self.parser.getIntentFilterExportedComponents():
            for intent_data in self.parser.getIntentFilters(e):
                row = []
                row.append(f'{e.split(".")[-1]}\n({tag})')
                # split mime types over two lines if too big
                mt = intent_data[-1]
                if len(mt) > 40:
                    mt = "/\n".join(mt.split("/"))
                    intent_data[-1] = mt
                row += intent_data
                table.append(row)
        if len(table) > 0:
            self.logger.info(tabulate(table, headers, tablefmt="fancy_grid"))

    def isAppLinkUsed(self):
        """
        Checks if APK defines AppLink(s)
        Applink is a specific type of deeplink with android:autoVerify property in its intent filter.
        """
        printSubTestInfo("Checking for AppLinks")
        res = self.parser.getUniversalLinks()
        verified_hosts = {h for e in res if e.autoVerify for h in e.hosts}

        for host in verified_hosts:
            # check if the assetlink.json is publicly accessible
            active_msg = colored("Digital Asset Link JSON file not found", "red")
            if checkDigitalAssetLinks(host):
                active_msg = colored(f"Digital Asset Link JSON file found at https://{host}/.well-known/assetlinks.json", "green")
            self.logger.warning(f'Found an applink with host "{host}":')
            if self.logger.level <= logging.WARNING:
                print(active_msg)

            # only applink infos for this particular host
            applinks = [e for e in res if host in e.hosts]
            # might be used in multiple activities
            unique_names = {a.name for a in applinks}
            # separate by activities
            for name in unique_names:
                # only applink infos for this particular host and for this activity
                applinks_with_this_name = [e for e in applinks if e.name == name]
                if self.logger.level <= logging.WARNING:
                    print(colored(f'\tDeclared in {applinks_with_this_name[0].tag} {name.split(".")[-1]} '
                              f' with the following URI :', "yellow"))
                    # show the URI
                    for applink in applinks_with_this_name:
                        for uri in applink.uris:
                            print(f"\t\t{uri}")
        return len(verified_hosts)

    def isDeepLinkUsed(self):
        """
        Checks if APK defines DeepLink(s)
        DeepLink is a component specifying an intent filter (with action = VIEW and category = BROWSABLE) 
        """
        printSubTestInfo("Checking for DeepLinks")
        res = self.parser.getUniversalLinks()
        unique_names = {deeplink.name for deeplink in res}
        # get component name and uris
        for name in unique_names:
            deeplinks = [e for e in res if e.name == name]
            self.logger.warning(f'Found a deeplink in {deeplinks[0].tag} {deeplinks[0].name.split(".")[-1]}'
                                f' with the following URI:')
            for deeplink in deeplinks:
                for uri in deeplink.uris:
                    if self.logger.level <= logging.WARNING:
                        print(f"\t{uri}")
        return len(unique_names) > 0

    def analyzeIntentFilters(self):
        """
        Regroups all functions related to Intent Filters analysis
        """
        self.getIntentFilterInfo()
        if self.isDeepLinkUsed():
            self.isAppLinkUsed()

    def getExportedComponents(self):
        """
        Lists all exported components
        """
        printTestInfo("Listing exported components")
        for component in ["activity", "receiver", "provider", "service"]:
            for e in self.parser.exportedComponents(component):
                self.logger.info(f'{e.split(".")[-1]} ({component})')

    def checkForFirebaseURL(self):
        """
        Checks if Firebase is used and returns the associated URL
        """
        # the rest of the code will do nothing if not an APK
        if self.isAPK: printTestInfo("Looking for Firebase URL")
        res = self.parser.searchInStrings("https://.*firebaseio.com")
        if len(res) > 0:
            for e in res:
                self.logger.info(f"\t{e}")

    def analyseNetworkSecurityConfigFile(self):
        """
        Analyses network_security_config file
        """
        printSubTestInfo("Analysing Network security config file")
        nsf = self.parser.getNetworkSecurityConfigFile()
        if nsf:
            nsParser = NetworkSecParser(nsf)
            nsParser.printXML()

    def runAllTests(self):
        print(colored(f"Analysis of {self.args.path}", "magenta", attrs=["bold"]))
        self.showApkInfo()
        self.analyzeRequiredPerms()
        self.analyzeCustomPerms()
        self.analyzeBackupFeatures()
        self.getNetworkConfigFile()
        self.isDebuggable()
        self.isCleartextTrafficAllowed()
        self.getExportedComponents()
        self.analyzeIntentFilters()
        self.analyzeExportedComponent()
        self.analyzeUnexportedProviders()
        self.checkForFirebaseURL()
