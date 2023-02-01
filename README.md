# Smarterp

This repository contains the code for the Smarter Interpreting project financed by CDTI Neotec funds.
The repository has been built from https://github.com/hlt-mt/FBK-fairseq.
The goal of this repository is to provide CAI tools with the suggestions produced by direct speech-to-text
translation (ST) systems.

## Architecture

The integration and communication with the CAI tool is implemented with the servers:

 1. A WebSocket server, which is the interface connected to the CAI system and manages the interaction with it
    working as a proxy for the IO server (see point 2), which serves the direct ST models;
 2. An IO server, which communicates through STDIN and STDOUT, providing an easy way to interact with the neural
    direct ST systems.


The full documentation regarding how to use server 1 can be found in [this README](websocket_server/README.md#api),
while for server 2 it can be found in [this README](api/README.md).

## Pre-trained models

The pre-trained models used in the two demo of the project are released under the same lisence of this repository
at can be downloaded HERE TODO, together with their dictionaries and configuration files:

 TODO


## Docker

To ease the reproduction of the demo, we provide a docker image ready to be used. Information on its installation and usage can be found in [this README](docker/README.md)

