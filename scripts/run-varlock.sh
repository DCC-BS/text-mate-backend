#!/bin/bash

source ./.env
varlock run -- "$@"

# (set -a; source ./.env; set +a; varlock run -- "$@")
