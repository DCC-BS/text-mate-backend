FROM erikvl87/languagetool

# Switch to root user to perform operations
USER root

# Install p7zip to extract the n-gram datasets
RUN apk add --no-cache \
    bash \
    p7zip \
    wget \
    pv

# Copy the download_ngrams script
COPY download_ngrams.sh /usr/local/bin/download_ngrams.sh
RUN chmod +x /usr/local/bin/download_ngrams.sh

COPY ./entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT [ "/usr/local/bin/entrypoint.sh" ]

# Switch back to the languagetool user
USER languagetool

CMD [ "/LanguageTool/start.sh" ]
