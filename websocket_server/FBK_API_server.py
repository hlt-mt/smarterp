#!/usr/bin/env python

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


# $Id: FBK_API_server.py,v 3.0 2023/02/01 14:31:46 cattoni Exp cattoni $

import asyncio
import websockets
import ssl
import json
import logging
import sys, os
import datetime
import subprocess
import base64
import argparse
import shutil
import time


def getTime():
    # return (float) seconds
    return time.time()

def debug(msg):
    if debugFlag:
        now = datetime.datetime.now().isoformat(sep="T", timespec="seconds")
        print(f'{now} {msg}')

def stServerStart():
    global stServerProc, stServerCmdList
    # start stServer
    stServerProc = subprocess.Popen(stServerCmdList, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    # wait stServer to start up
    debug("waiting stServer to start up ...")
    line = stServerProc.stdout.readline().decode("utf-8")
    if "server started successfully" in line:
        doWarmUp()
        return
    
def stServerSendOnly(msg):
    global stServerProc
    msg = msg.rstrip()
    stServerProc.stdin.write(bytes(msg + "\n", 'utf-8'));
    stServerProc.stdin.flush();
    debug(f'stServerSendOnly -> |{msg}|')
    
def stServerSendReceive(msg):
    global stServerProc
    msg = msg.rstrip()
    stServerProc.stdin.write(bytes(msg + "\n", 'utf-8'));
    stServerProc.stdin.flush();
    debug(f'stServerSendReceive -> |{msg}|')
    reply = stServerProc.stdout.readline().rstrip().decode("utf-8")
    debug(f'stServerSendReceive <- |{reply}|')
    return reply

def doWarmUp():
    global warmupWavPath, srcLanguage, tgtLanguage
    srcLanguage = "en"
    tgtLanguage = "es"
    # read WAV file and filter out the header:w
    wContent = b''
    with open(warmupWavPath, mode='rb') as fp:
        wContent = fp.read()
        subchunk2ID = wContent[36:40].decode('UTF-8').casefold()
        if subchunk2ID == 'data'.casefold():
            wContent = wContent[44:]
        elif subchunk2ID == 'LIST'.casefold():
            subchunk3ID = wContent[70:74].decode('UTF-8').casefold()
            if subchunk3ID == 'data'.casefold():
                wContent = wContent[78:]
            else:
                print(f'unknown subchunk3ID {subchunk3ID}')
                sys.exit(1)
        else:
            print(f'unknown subchunk2ID {subchunk2ID}')
            sys.exit(1)
    #
    audioSizeOneSec = (frameRate * frameSize)
    contentLen = len(wContent)
    warmupSec = 12
    # select at max the first warmupSec seconds od audio 
    audioSta = 0
    audioEnd = min(warmupSec * audioSizeOneSec, contentLen)
    audioChunk = wContent[audioSta:audioEnd]
    debug(f'doWarmUp: before sending chunks {audioEnd}')
    t1 = getTime()
    for i in range(3):
        processAudioAndComposeClientMsg(audioChunk, useBilingualDict=False)
    t2 = getTime()
    debug(f'completed warm-up phase in {t2-t1} secs')
    return


def getNormalizedStringList(l, nesFlag=True):
    newL = []
    for item in l:
        d = {}
        d["src"] = item[0]
        d["tgt"] = item[1]
        if nesFlag:
            d["type"] = item[2]
        newL.append(d)
    s = json.dumps(newL)
    return s
            

def checkAudioAndSendToProcess():
    global totAudioSecs, stStepSecs, stWindowSecs, audioBuffer, lastSentEndSec
    debug(f'checkAudioAndSendToProcess -> {totAudioSecs} {len(audioBuffer)}')
    # if not enough audio then do nothing
    #
    if totAudioSecs < stStepSecs:
        debug('checkAudioAndSendToProcess: 1 do-nothing')
        lastSentEndSec = -1
        return None
    #
    # if audio < stWindowSecs, then
    #    send the first (stStepSecs * n) < stWindowSecs audio to be processed,
    #    and remove nothing
    if totAudioSecs < stWindowSecs:
        sec = int(totAudioSecs / stStepSecs) * stStepSecs
        if sec <= lastSentEndSec:
            debug('checkAudioAndSendToProcess: 2A do-nothing')
            return None
        dim = int(sec * (frameRate * frameSize))
        lastSentEndSec = sec
        debug(f'checkAudioAndSendToProcess: 2B sending {sec} ({dim} / {len(audioBuffer)})')
        outMsg = processAudioAndComposeClientMsg(audioBuffer[0:dim])
        return outMsg
    #
    # audio >= stWindowSecs, so send the last stWindowSecs audio
    #
    endSec = int(totAudioSecs / stStepSecs) * stStepSecs
    if endSec <= lastSentEndSec:
        debug('checkAudioAndSendToProcess: 3A do-nothing')
        return None
    lastSentEndSec = endSec
    startSec       = endSec - stWindowSecs
    ## if startSec < 0:   startSec = 0
    startBuf = int(startSec * (frameRate * frameSize))
    dim      = int(stWindowSecs * (frameRate * frameSize))
    endBuf   = int(startBuf + dim)
    debug(f'checkAudioAndSendToProcess: 3B sending [{startSec}, {endSec}] [{startBuf}, {endBuf}] ({dim} / {len(audioBuffer)})')
    outMsg = processAudioAndComposeClientMsg(audioBuffer[startBuf:endBuf])
    return outMsg
        

# send audio to the stServer, wait reply, compose the msg to the
#   client websocket and return it
#
def processAudioAndComposeClientMsg(audioData, useBilingualDict=True):
    global stWavPath, srcLanguage, tgtLanguage, bilingualDictPath
    global audioSaveFlag, lastSentEndSec
    # compute audio byte size
    audioSize = len(audioData)
    with open(stWavPath, mode='wb') as fp:
        # write WAV header (78 bytes)
        header = b'RIFF' + (audioSize + 70).to_bytes(4, byteorder='little')
        header += b'WAVE'
        header += b'fmt ' + b'\x10\x00\x00\x00\x01\x00\x01\x00'
        header += b'\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00'
        header += b'LIST\x1a\x00\x00\x00'
        header += b'INFOISFT\x0e\x00\x00\x00'
        ## header += b'Lavf57.83.100\x00'
        header += b'Lavf58.29.100\x00'
        header += b'data' + (audioSize).to_bytes(4, byteorder='little')
        fp.write(header)
        # write content
        fp.write(audioData)
    if audioSaveFlag:
        backupWavFile = f'{stWavPath}__backup_{lastSentEndSec}.wav'
        shutil.copyfile(stWavPath, backupWavFile)
    if useBilingualDict:
        msgToSt = '{"wav_path": "%s", "src_lang":  "%s", "tgt_lang":  "%s", "dictionary": "%s"}' % (stWavPath, srcLanguage, tgtLanguage, bilingualDictPath)
    else:
        msgToSt = '{"wav_path": "%s", "src_lang":  "%s", "tgt_lang":  "%s"}' % (stWavPath, srcLanguage, tgtLanguage)
    debug(f'msgToSt {msgToSt}')
    startT = getTime()
    reply = stServerSendReceive(msgToSt)
    responseT = getTime() - startT
    debug(f'  stServer responseT {responseT}')
    debug(f'reply {reply}')
    d = json.loads(reply)
    # d["status"], d["score"], d["translation"], d["transcript"], d["nes"", d["terms"]
    ts = datetime.datetime.now().isoformat(sep="T", timespec="seconds")
    neList   = getNormalizedStringList(d["nes"])
    termList = getNormalizedStringList(d["terms"], nesFlag=False)
    info = '{"time_stamp": "%s", "ne_list": %s, "term_list": %s}' % (ts, neList, termList)
    outMsg = '{"type": "result", "status": 0, "info": %s}' % info
    return outMsg


def saveBilingualTerms(bilingualGloss):
    global bilingualDictPath
    try:
        with open(bilingualDictPath, mode='w') as fp:
            for term in bilingualGloss:
                srcText = term["src"]
                tgtText = term["tgt"]
                fp.write(f'{srcText}\t{tgtText}\n')
    except Error as err:
        debug(f'ERROR: due to {err}')
        return False
    return True


class MissingActionError(Exception):
    """Raised when the input msg does not include the action to be performed"""
    pass

class MissingStartDataError(Exception):
    """Raised when the input msg of type "start" does not include the expected data"""
    pass


async def externalLoop(websocket, path):
    global stWavPath, audioBuffer, totAudioSecs, srcLanguage, tgtLanguage
    print(f'started connection from {websocket.remote_address} {path}')
    while True:
        try:
            debug(f'waiting msg from {websocket.remote_address}')
            inMsg = await websocket.recv()
            d = json.loads(inMsg)
            debug(f'received inMsg (len {len(inMsg)}, type {type(inMsg)}) from {websocket.remote_address}')

            if not "action" in d:
                raise MissingActionError
            action = d["action"]
            #
            outMsg = ""
            if action == "shutdown":
                debug(f'  shutdown | {inMsg}')
                stServerSendOnly('{"command": "shutdown"}')
                if os.path.exists(stWavPath):   os.remove(stWavPath)
                if os.path.exists(bilingualDictPath):    os.remove(bilingualDictPath)
                sys.exit(0);
            #
            elif action == "start":
                debug(f'  start | {inMsg}')
                if not "data" in d:
                    raise MissingStartDataError
                if not "src" in d["data"] or not "tgt" in d["data"] or not "bilingual_gloss" in d["data"]:
                    raise MissingStartDataError
                #
                srcLanguage    = d["data"]["src"]
                tgtLanguage    = d["data"]["tgt"]
                bilingualGloss = d["data"]["bilingual_gloss"]
                saveBilingualTerms(bilingualGloss)
                audioBuffer = b''
                totAudioSecs = 0
                outMsg = '{"type": "response", "status": 0, "info": ""}'
                debug(f'outMsg {outMsg}')
                await websocket.send(outMsg)
            #
            elif action == "chunk":
                debug(f'  chunk | ')
                b64Content = d["data"]["audio"]
                audioChunk = base64.b64decode(b64Content)
                audioSecs = len(audioChunk) / (frameRate * frameSize)
                totAudioSecs += audioSecs
                audioBuffer += audioChunk
                debug(f'  audioBuffer {len(audioBuffer)}, audioChunk {type(audioChunk)} {len(audioChunk)}, b64Content {type(b64Content)} {len(b64Content)}, audioSecs {audioSecs}, totAudioSecs {totAudioSecs}')
                #
                outMsg = checkAudioAndSendToProcess()
                if outMsg:
                    debug(f'outMsg {outMsg}')
                    await websocket.send(outMsg)
            #
            elif action == "end":
                debug(f'  end | {inMsg}')
                # if still audio then send it to ST to be processed
                #
                outMsg = checkAudioAndSendToProcess()
                if outMsg:
                    debug(f'outMsg {outMsg}')
                    await websocket.send(outMsg)
                audioBuffer = b''
                totAudioSecs = 0
                lastSentEndSec = -1
                if os.path.exists(stWavPath):    os.remove(stWavPath)
                if os.path.exists(bilingualDictPath):    os.remove(bilingualDictPath)
                outMsg = '{"type": "response", "status": 0, "info": ""}'
                debug(f'outMsg {outMsg}')
                await websocket.send(outMsg)
            #
            else:
                # unknown action
                info = f'unknown action {action}'
                outMsg = '{"type": "response", "status": 1, "info": "unknown action %s"}' % action
                debug(f'outMsg {outMsg}')
                await websocket.send(outMsg)

        except json.decoder.JSONDecodeError as err:
            debug(f'ERROR: not json format from {websocket.remote_address}')

        except MissingActionError as err:
            debug(f'ERROR: missing-action from {websocket.remote_address}')

        except MissingStartDataError as err:
            debug(f'ERROR: missing-start-data from {websocket.remote_address}')

        except websockets.WebSocketException as err:
            print(f'end connection from {websocket.remote_address} due to {err}')
            break
    return


# ---
# run
# ---

# With frame_rate=16000 and frame_size=2 (bytes), the size of each second
#   of audio is 32000 bytes.
frameRate = 16000  # the number of audio frames per second
frameSize = 2      # the size (in bytes) of each audio frame

# the default time (in seconds) of the atomic audio unit
stStepSecs   = 1.5
# the default size (in seconds) of the audio window to be processed by the ST
stWindowSecs = 10
# the wav file to be processed by the ST
stWavPath    = f'/tmp/FAs.{os.getpid()}.wav'  

audioBuffer  = b'' # the buffer with the stored audio
totAudioSecs = 0   # the current amount of stored audio
debugFlag = False
lastSentEndSec = -1

srcLanguage = ""
tgtLanguage = ""
bilingualDictPath  = f'/tmp/FAs.{os.getpid()}.dict.tsv'  
audioSaveFlag = False
warmupWavPath = './warmupFile.wav'


parser = argparse.ArgumentParser()
# (optional) args
parser.add_argument("-d", "--debug", action="store_true", help="enable debug")
parser.add_argument("-s", "--stepsize", type=float, help=f"the size (in seconds) of the atomic audio unit (default {stStepSecs})")
parser.add_argument("-w", "--windowsize", type=float, help=f"the size (in seconds) of the audio window to be processed (default {stWindowSecs})")
parser.add_argument("-a", "--saveaudio", action="store_true", help="enable audio saving")

#
# positional (mandatory) args
parser.add_argument("host",
                    help="the host running the server (e.g. localhost)")
parser.add_argument("port", type=int,
                    help="the port to connect to the server")
parser.add_argument("stServerInfo", help="the ST server command and possible args (| separated)")
args = parser.parse_args()
host = args.host
port = args.port
stServerInfo = args.stServerInfo
debugFlag    = args.debug
if args.stepsize:
    stStepSecs   = args.stepsize
if args.windowsize:
    stWindowSecs = args.windowsize
audioSaveFlag = args.saveaudio

stServerCmdList = stServerInfo.split('|')
if not os.path.isfile(stServerCmdList[0]):
    print(f'ERROR: cannot find file {stServerCmdList[0]}')
    sys.exit(-2);
langPair=stServerCmdList[1]

if not os.path.isfile(warmupWavPath):
    print(f'ERROR: cannot find warmupWavPath {warmupWavPath}')
    sys.exit(-2);

print('initialization phase: please wait...')

stServerStart()

print(f'  ok stServer with pid {stServerProc.pid}; stStepSecs {stStepSecs}, stWindowSecs {stWindowSecs}')

    
cPath = os.environ.get('CREDENTIAL_HOME')
if cPath == None:
  print('ERROR: missing environmen variable CREDENTIAL_HOME')
  sys.exit(-1)

certF  = cPath + "/" + "ca.pem"
keyF   = cPath + "/" + "privatekey.pem"
debug(f'certF {certF}, keyF {keyF}')

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain(certF, keyF)

ws = websockets.serve(externalLoop, host, port,
                      ping_interval=None,
                      ssl=ssl_context)
print(f'ready websocket FBK API server {langPair} at {host}:{port}')


asyncio.get_event_loop().run_until_complete(ws)
asyncio.get_event_loop().run_forever()

