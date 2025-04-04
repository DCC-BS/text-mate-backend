#!/bin/bash
set -e

source /usr/local/bin/download_ngrams.sh &&
download_ngrams de
download_ngrams en
download_ngrams fr

source /LanguageTool/start.sh
