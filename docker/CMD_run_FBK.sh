#! /bin/bash

# Copyright (c) 2023 FBK.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


# start the FBK API server that wraps the ST server

myError() {
  msg="$*"
  echo $msg 1>&2
  exit 1
}


img='smarterp/demo_st:v1.0'

if docker container ls -a | grep "$img" &> /dev/null
then
  myError service already running 
fi


debugFlag=""
if ! test $# -ge 2
then
  cat << EOF 1>&2
ARGS: GPU-flag langPair [-d]
  where GPU-flag == 0|1  (0 for CPU-only, 1 for GPU)
        langPair == en-es|es-en|fr-es
EOF
  exit 1
fi

gpuFlag=$1
langPair=$2
if test $# -ge 3 ; then debugFlag='-d' ; fi

gpuInfo=''
case $gpuFlag in
  1)
     gpuInfo='--runtime=nvidia'
     ;;
  *)
     gpuInfo=''
     ;;
esac


if test -z "${FBK_ST_DATA_PATH}"
then
  myError 'cannot find enviroment variable FBK_ST_DATA_PATH: please set it with the path of the directory "data" extracted from the "st_data.tar.gz" archive'
fi

if ! test -d "${FBK_ST_DATA_PATH}"
then
  myError 'ERROR: the value of the enviroment variable FBK_ST_DATA_PATH is not a directory: please check the enviroment variable FBK_ST_DATA_PATH and set it with the path of the directory "data" extracted from the "st_data.tar.gz" archive'
fi

if ! test -d "${FBK_ST_DATA_PATH}/en-es"
then
  myError 'ERROR: the value of the enviroment variable FBK_ST_DATA_PATH does not appear to contain the ST models: please check the enviroment variable FBK_ST_DATA_PATH and set it with the path of the directory "data" extracted from the "st_data.tar.gz" archive'
fi

if test -z "${CREDENTIALS_PATH}"
then
  myError 'cannot find enviroment variable CREDENTIALS_PATH: please set it with the path of the directory including the two "ca.pem" (the certificate) and "privatekey.pem" (the private key) files'
fi

if ! test -d "${CREDENTIALS_PATH}"
then
  myError 'ERROR: the value of the enviroment variable CREDENTIALS_PATH is not a directory: please check the enviroment variable CREDENTIALS_PATH and set it with the path of the directory including the two "ca.pem" (the certificate) and "privatekey.pem" (the private key) files'
fi

if ! test -f "${CREDENTIALS_PATH}/ca.pem"
then
  myError 'ERROR: cannot find the "ca.pem" (the certificate) in the directory '$CREDENTIALS_PATH
fi

if ! test -f "${CREDENTIALS_PATH}/privatekey.pem"
then
  myError 'ERROR: cannot find the "privatekey.pem" (the private key) file in the directory '$CREDENTIALS_PATH
fi


args='--rm -it'
args="$args $gpuInfo"
args="$args -p 8778:8778"
args="$args -v ${FBK_ST_DATA_PATH}:/data"
args="$args -v ${CREDENTIALS_PATH}:/credentials"
args="$args -e CREDENTIAL_HOME=/credentials"

# add the env var LINKEDDATA_IP if it is set 
#   (it must contain the IP of the host running the NE linking service)
if ! test -z "${LINKEDDATA_IP}"
then
  args="$args -e LINKEDDATA_IP=${LINKEDDATA_IP}"
fi


if ! test -z "$debugFlag"
then
  if test $gpuFlag == 1
  then 
    echo using GPU
  else 
    echo 'using CPU only (NO-GPU)'
  fi	
  echo docker run $args $img $langPair $debugFlag
fi

docker run $args $img $langPair $debugFlag

