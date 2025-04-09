FROM erikvl87/languagetool

ARG langtool_languageModel=/languagetool/.cache/ngrams

# Switch to root user to perform operations
USER root

# Install p7zip to extract the n-gram datasets
RUN apk add --no-cache \
    bash \
    p7zip \
    wget \
    su-exec \
    pv

# Copy the download_ngrams script
COPY download_ngrams.sh /usr/local/bin/download_ngrams.sh
RUN chmod +x /usr/local/bin/download_ngrams.sh

COPY ./entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# RUN mkdir -p $langtool_languageModel && \
#     chown languagetool:languagetool $langtool_languageModel && \
#     chmod 755 $langtool_languageModel

ENTRYPOINT [ "/usr/local/bin/entrypoint.sh" ]
