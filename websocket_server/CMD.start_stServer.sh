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


wDir=$(cd $(dirname $0) ; pwd)

test $# -ge 1 || { echo 'ARGS: langPair' ; exit 1 ; }
langPair=$1

case $langPair in
  en-es|es-en|fr-es)
     :
     ;;
  *)
     echo unknown langPair $langPair ; exit 1 ;
     ;;
esac

rootDir=${wDir}/..
exe=$rootDir/api/simple_io_server_st.py
test -f $exe || { echo cannot find exe $exe ; exit 1 ; }

src=$(echo $langPair | cut -d- -f1)
tgt=$(echo $langPair | cut -d- -f2)

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


sysName=triangle
pt=avg7.pt

dataD=${FBK_ST_DATA_PATH}/${langPair}
modelF=$dataD/$pt
yamlF=$dataD/config_st.yaml

test -d $dataD || { echo cannot find dataD $dataD ; exit 1 ; }
test -f $modelF || { echo cannot find modelF $modelF ; exit 1 ; }
test -f $yamlF || { echo cannot find yamlF $yamlF ; exit 1 ; }




logFerr=$wDir/ioserver.${sysName}.LOG.err

# in absence of the PRINT_STDERR env var, print STDERR on a local flie 
if test -z "${PRINT_STDERR}"
then
  python -u $exe $dataD \
    --user-dir examples/speech_to_text \
    --config-yaml $yamlF \
    --max-tokens 10000 \
    --scoring sacrebleu --beam 5 \
    --path $modelF \
    --max-source-positions 10000 --max-target-positions 1000 \
    --model-overrides "{'load_pretrained_encoder_from': None}" \
    --task speech_to_text_tagged_dual \
    --server-processor st_triangle_ne 2> $logFerr
else
  python -u $exe $dataD \
    --user-dir examples/speech_to_text \
    --config-yaml $yamlF \
    --max-tokens 10000 \
    --scoring sacrebleu --beam 5 \
    --path $modelF \
    --max-source-positions 10000 --max-target-positions 1000 \
    --model-overrides "{'load_pretrained_encoder_from': None}" \
    --task speech_to_text_tagged_dual \
    --server-processor st_triangle_ne
fi

