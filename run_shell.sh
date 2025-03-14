#!/bin/bash

# Variables
VERSION=1.0
IMAGE_NAME="ChipSQLInterface_v${VERSION}.sif"
SCRIPT=$(readlink -f $0)
IMAGE_PATH=`dirname $SCRIPT`

# Check if the image exists
if [ ! -f "${IMAGE_PATH}/${IMAGE_NAME}" ]; then
    echo "Error: Image ${IMAGE_NAME} not found in ${IMAGE_PATH}."
    exit 1
fi

# Run the image
echo "Running ${IMAGE_NAME}..."
apptainer shell --fakeroot -B /mnt,logs:/var/run/postgresql -B database:/opt:rw "${IMAGE_PATH}/${IMAGE_NAME}"


