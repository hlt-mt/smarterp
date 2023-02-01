# The websocker server

This package contains the TLS secure WebSocket server, named FBK API server,
that is the interface connected to the CAI system and acts as a wrapper of the direct ST system.


## FBK API server

This server consists in a simple, single-thread server that accepts as
input audio packets from a client (e.g. the CAI system), stores them
and when a (configurable) condition is met, sends the accumulated
audio packets to the ST system, waits for its reply, and sends it back
to the client in the proper format.

### API

The API supports the transfer of WAV audio chunks (PCM, sample rate
16000 Hz, mono channel) from a client to the FBK-ST server which
reports back to the client the recognized Named Entities translated
into the target language.

The communication is based on a secure TLS
WebSocket protocol.

Information is exchanged in json format using the UTF-8 character encoding.

The url of the FBK-ST server is wss://${IP]:${port}  where by default IP is “demo-smarterp.fbk.eu” and port is 8778.

#### Messages to the server

A message to the server has two attributes:
- “action” containing the action to be performed and 
- “data” which is the payload of the message.

Three are the messages accepted by the server:
1. start
  - description:
this message starts a session with the needed information, namely the source language of the audio, the target language for the Named Entities and the bilingual dictionary of terminology.
  - parameters:
    1. “action” (mandatory) with the value “start”;
    2. “data” (mandatory) containing:
      1. “src” (mandatory): source language encoded with a two-char ISO 639-1 code;
      2. “tgt” (mandatory): target language encoded with a two-char ISO 639-1 code;
      3. “bilingual_gloss” (mandatory): bilingual dictionary of terms as a list of <src, tgt>
  - response: the FBK_ST server sends a reply in JSON format to either acknowledge the success or to report an error. It includes the attributes “type” (with value “response”), "status" and "info".
    1. success: the attribute "status" is 0 and the attribute "info" is empty
    2. failure: the attribute "status" is 1 and the attribute "info" contains the error description.
  - example:
    1. received message: {"action": "start", "data": {"src": "en", "tgt": "it", "bilingual_gloss": [{"src": "heart attack", "tgt": "attacco di cuore"}, {"src": "board game", "tgt": "gioco da tavolo"} ] } }
    2. response: {"type": "response", "status": 0, "info": {}}
2. chunk
  - description: this message contains an audio chunk, which is a Base64 encoded 16 bit PCM string;
  - parameters:
    1. “action” (mandatory) with the value “chunk”;
    2. “data” (mandatory) containing:
    3. “audio” (mandatory);Base64 encoded 16 bit PCM string;
    4. “frame_rate” (mandatory): with value 16000
  - response: this message has no response
  - example: {"action": "chunk", "data": {"audio": "BASE64_ENCODED_STRING", “frame_rate”: 16000}} 
3. end
  - description: this message ends the session.
  - parameters:
    1. “action” (mandatory) with the value “end”;
    2. “data” (mandatory) with empty value {}:
  - response: the FBK_ST server sends a reply in JSON format to either acknowledge the success or to report an error. It includes the attributes “type” (with value “response”), "status" and "info".
    1. success:  the attribute "status" is 0 and the attribute "info" is empty
    2. failure: the attribute "status" is 1 and the attribute "info" contains the error description.
  - example
    - received message: {"action": "end", "data": {}}
    - response: {"type": "response", "status": 0, "info": {}}

#### Messages from the server

In addition to the responses to the received messages “start” and “end”, the FBK-ST server during the session sends to the client a sequence of messages “result” containing the recognized Named Entities translated into the target language extracted from the received audio.

The number of messages may vary depending on the audio contents.

In details:
- result
  - description: this message reports back to the client both the recognized Named Entities and the terms translated into the target language extracted from the received audio;
  - parameters:
    1. “type” (mandatory): “result”;
    2. “status” (mandatory): 0 for success, 1 for failure;
    3. “info” (mandatory):
      - in case of success contains:
        - (a) the list of extracted Named Entities, each one as triple <src, tgt, type> 
        - (b) the list of extracted terms, each one as pair <src, tgt>
        - (c) the time stamp of the response
      - in case of failure contains the error description
  - example:
{"type": "result",
 "status": 0,
 "info": {"time_stamp": "2022-10-17T22:30:57",
             "ne_list": [
               {"src": "London", "tgt": "Londra", "type": "GPE"}, 
               {"src": "France", "tgt": "Francia", "type": "GPE"} ],
              “term_list”: [
                {"src": "large river", "tgt": "grande fiume"} ] } }


### Usage

```bash
python -u ./FBK_API_server.py HOSTNAME CMD.start_stServer.sh\|LANGUAGE_PAIR
```


### Limitations

 - The server is single-thread and accepts only ONE request per time.
 - The server can serve only one language pair.

## Dependencies

The following python packages are needed:

```bash
pip install websockets
```
