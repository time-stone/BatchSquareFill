#!/bin/zsh

# EDIT WITH Text-Wrangle only!! --> UnixLF & UTF8
# make executable :  chmod +x *.command
#ps -p $$

# switch to the folder of the script file
# 
cd "`dirname "$0"`"
MYDIR=$(pwd)
echo "#########################################"
echo $'\u2713' SWITCHING TO FOLDER OF SCRIPT-File: $MYDIR


echo "#################################################################################"
echo $'\U0001F50E' CHECKING if UV Package Manager is installed...
if command -v uv >/dev/null 2>&1; then
  echo $'\u2713' uv is installed
else
  echo $'\u26A0' uv is not installed. finishing
  echo install via brew install uv.
  echo EXITING...
  exit 1
fi

echo "#################################################################################"
echo $'\U0001F527' SYNCING dependencies...
uv sync 2>&1

echo "#################################################################################"
echo $'\U0001F680' RUNNING BatchSquareFill.py...
.venv/bin/python BatchSquareFill.py

echo "#################################################################################"
echo "Press any key to close..."
read -k1 -s
