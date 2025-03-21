FROM erikvl87/languagetool

# Switch to root user to perform operations
USER root

# Install p7zip to extract the n-gram datasets
RUN apk add --no-cache \
    bash \
    p7zip \
    wget \
    pv

# Create a directory for n-grams
RUN mkdir -p /ngrams

# Copy the download_ngrams script
COPY download_ngrams.sh /usr/local/bin/download_ngrams.sh
RUN chmod +x /usr/local/bin/download_ngrams.sh

COPY ./entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Switch back to the languagetool user
USER languagetool

# Set the languageModel configuration to use the n-grams
ENV langtool_languageModel=/ngrams

ENTRYPOINT [ "/usr/local/bin/entrypoint.sh" ]
