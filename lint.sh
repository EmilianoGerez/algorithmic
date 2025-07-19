#!/bin/bash
# Flake8 wrapper script that ignores the violations you specified

python -m flake8 \
  --exclude=venv,./venv,.venv,env \
  --ignore=D,F401,E402,E501,F841,I100,I101,I201,I202,E121,E122,W291,E251,F541 \
  --count \
  --show-source \
  --max-line-length=88 \
  --max-complexity=10 \
  "$@"
