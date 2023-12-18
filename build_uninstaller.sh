#!/bin/bash
# pip install -U py2app
# if [[ ! -n "setup.py" ]]; then
#     py2applet --make-setup mub.py
# fi
# python setup.py py2app
APP_NAME="PikeSquares Uninstaller"
pip install -U PyInstaller
pip install -U --upgrade PyInstaller pyinstaller-hooks-contrib
pip install -r requirements.txt
if [ ! -e "$APP_NAME" ]; then
    pyinstaller \
        -F \
        --noconfirm \
        --name "$APP_NAME" \
        --collect-all mib \
        --windowed \
        src/mib/mub.py 

else
    pyinstaller \
        --noconfirm \
        --collect-all mib \
        "$APP_NAME.spec"
fi
