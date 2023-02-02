# The docker-based smarterp FBK ST demo component

This package contains the docker image to run the FBK ST demo
component: it includes the TLS secure WebSocket server, named FBK API
server, that is the interface connected to the CAI system and acts as
a wrapper of the direct ST system.

## Installation

### Download files

Download the three files (by clicking on the links):
1. the docker image [image.smarterp__demo_st__v1.0.tar.gz](https://drive.google.com/file/d/1BF4n6K4Qps_CX1Y6N9CpnfDAoFAW05FP/view?usp=sharing)  (2.8 GB)
2. the archive [st_data.tar.gz](https://drive.google.com/file/d/1B9_k0SFWe448ZPeB_scSfCR1XvTbSsdL/view?usp=sharing) containing the model data for the ST system (three language pairs: en-es, es-en and fr-es) (3.6 GB)
3. the script [CMD_run_FBK.sh](https://drive.google.com/file/d/1lwRdhour6YKRtzasgyfdyJcFmlRufNcp/view?usp=sharing) to run the FBK ST demo component


### Load the docker image

Issue the command
```bash
$> docker load < image.smarterp__demo_st__v1.0.tar.gz
```
that loads the 'smarterp/demo_st:v1.0' image into the docker system.


### Extract the ST model data

Issue the command
```bash
$> tar xvfz st_data.tar.gz
```
that creates the directory "data" containing the sub-directories
"en-es", "es-en" and "fr-es".


## Usage

### Environment variables

Before starting the FBK ST demo component, two environment variables are
to be set:

1. FBK_ST_DATA_PATH (mandatory): it must be assigned with the path of the
directory "data" extracted from the "st_data.tar.gz" archive
(cfr. step ./README.md#extract-the-st-model-data)
For example, if the path of such directory is
```
/home/ubuntu/smarterp/FBK/data
```
then the command to set the environment variable is
```bash
$> export FBK_ST_DATA_PATH=/home/ubuntu/smarterp/FBK/data
```

2. CREDENTIALS_PATH (mandatory) : it must be assigned with the path of the
directory containing the two "ca.pem" (the certificate) and
"privatekey.pem" (the private key) files, needed for the TLS secure
WebSocket connection.

A third environment variable LINKEDDATA_IP (optional) can be used to
change the IP of the host running the NE linking service. The utilized
default value is "3.121.98.219" .


### Start

At this point, the FBK demo component can be started with the script 
```bash
CMD_run_FBK.sh
```
that accepts two mandatory arguments:
1. GPU-flag: allowed values are 0 (for CPU-only) or 1 (for GPU)
2. langPair: allowed values are en-es or es-en or fr-es
The third optional argument '-d' can be provided to enable printing of
debug information.

It prints the initial message
```bash
initialization phase: please wait...
```
so Wait until the process prints the message
```bash
ready websocket FBK API server LANGUAGE-PAIR at HOST:PORT
```
this means it is ready to accept connections and requests.

### API

The API of the FBK ST demo component can be found in [this README](../websocket_server/README.md#api)

### Limitations

 - The server is single-thread and accepts only ONE request per time.
 - The server can serve only one model.


## Dependencies

No dependencies.
