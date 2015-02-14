#!/bin/sh

find ./ -name '*.py' -not -wholename "*/migrations/*" -print -exec autopep8 --in-place --aggressive --aggressive --max-line-length 140 {} \;
