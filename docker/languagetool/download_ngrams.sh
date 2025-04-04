#!/bin/bash
set -e

download_ngrams() {
    lang=$1
    base_url="https://languagetool.org/download/ngram-data"

    if [ ! -d "$langtool_languageModel/$lang" ] || [ -z "$(ls -A $langtool_languageModel/$lang)" ]; then
        # create the directory if it doesn't exist
        # mkdir -p "/ngrams"

        echo "Searching for the latest n-grams for $lang..."

        # Get the list of available files and sort by date (newest first)
        latest_file=$(wget -q -O - "$base_url/" |
            grep -Eo "ngrams-$lang-[0-9]{8}\.zip" |
            sort -r |
        head -n 1)

        if [ -z "$latest_file" ]; then
            echo "No n-gram file found for $lang"
            return 1
        fi

        echo "Downloading $latest_file..."
        wget -e dotbytes=100M "$base_url/$latest_file" -O "/tmp/$latest_file"

        echo "Extracting n-grams..."
        7z x "/tmp/$latest_file" -o"$langtool_languageModel/"
        rm "/tmp/$latest_file"

        echo "N-grams for $lang downloaded and extracted."
    else
        echo "N-grams for $lang already exist, skipping download"
    fi
}
