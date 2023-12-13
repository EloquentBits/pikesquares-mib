# Mac OS Installer Builder (aka MIB)

## Usage

As simple as:

First of all, place your binary inside `_files/binary` directory and rename it according to user usage.
For example, if your built binary named `vconf-linux-x86_64`, the binary inside `_files/binary` directory should be called `vconf` as user should have run it after installation.

Then run installer script:
```bash
bash make-mac-installer.sh
```

Be sure, you're located in directory, where this script is placed!

If you named your config file `my-product.json`, and placed it into `/tmp/build` (for example) you can run mib like this:
```bash
bash make-mac-installer.sh -c /tmp/build/my-product.json
bash make-mac-installer.sh --config /tmp/build/my-product.json
```

Do not be scared, when it asked for password, the pkg installer (see `installer.check_after_build`) requires sudo for testing of successful package installation.

The built installer will be placed in this folder with the name you give it in config file
(see `installer.file_name`)


## Config file description
```jsonc
{
    /// All options you want to use in installer Jinja2-based templates
    /// Use them as {{ product.option }}
    "product": {
        // Product name
        "name": "My Product",
        /// Product version
        "version": "1.0.0",
        /// Product identifier. Will be shared within installers packages.
        "identifier": "com.company.my-product",
        /// Product copyright
        "copyright": "Copyright © 2023 My Company Inc. All rights reserved",
        /// Available product commands. Will shown after product install
        "commands": {
            /// You can put here your commands
            "run": "sudo launchctl start com.company.my-product-daemon",
            "uninstall": "sudo /usr/local/bin/my-product-uninstall"
        },
        /// Available product links. Will shown after product install
        "links": [
            {"name": "My Product Docs", "url": "https://docs.my-product.com"}
        ]
    },
    /// Installer specific options
    "installer": {
        /// File name of installer. Do not put .pkg in it.
        "file_name": "my-product-installer",
        /// Do check installer for errors after build automatically
        "check_after_build": true,
        /// Directories packed in installer
        "files": [
            {
                /// Directory name
                "name": "binary",
                /// Directory placement
                "root": "_files/binary",
                /// Where to put files of this directory within install
                "install_location": "/usr/local/bin"
            },
            {
                "name": "daemon",
                "root": "_files/daemon",
                "install_location": "/Library/LaunchDaemons",
                /// Where preinstall/postinstall scripts are placed, they will be used by installer
                "scripts_dir": "_files/daemon_scripts"
            }
        ],
        /// Directory contains all of resources
        /// If it has localized strings, it should be named English.lproj or en.lproj
        "resources_dir": "_files/Resources/en.lproj",
        /// This options will be added to distribution.xml after generate
        /// For all available values refer to:
        /// https://developer.apple.com/library/archive/documentation/DeveloperTools/Reference/DistributionDefinitionRef/Chapters/Distribution_XML_Ref.html
        "distribution": {
            /// Installer title. You will see it on top of the installer window
            "title": "My Product Installer",
            "background": {
                "mime-type": "image/png",
                "file": "banner.png",
                "scaling": "proportional"
            },
            /// Installer welcome page. Will be shown when installation window just opened
            "welcome": {
                "file": "welcome.html",
                "mime-type": "text/html"
            },
            /// Installer conclusion page. Will be shown after successful installation
            "conclusion": {
                "file": "conclusion.html",
                "mime-type": "text/html"
            },
            /// License file. Will be shown after welcome page. You will be asked to accept license.
            "license": {
                "file": "LICENSE.txt"
            },
            /// Additional options
            "options": {
                /// User can customize the installation and uncheck some of packages
                "customize": "never",
                /// Installer can have access to user environment for scripts
                "allow-external-scripts": "no"
            },
            /// Domains
            "domains": {
                /// Should product be installed in the system directory (not user directory)
                "enable_localSystem": "true"
            }
        }
    }
}
```