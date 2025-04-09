#!/bin/bash
set -e

echo "Running entrypoint as $(whoami)"

source /usr/local/bin/download_ngrams.sh &&
download_ngrams de
download_ngrams en
download_ngrams fr

chmod +x /LanguageTool/start.sh

echo "Starting LanguageTool as languagetool user ..."
su-exec languagetool /LanguageTool/start.sh
