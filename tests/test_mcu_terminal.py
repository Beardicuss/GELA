import json
import threading
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voice_assistant.mcu_terminal import MCU_CAPABILITIES, MCU_PROTOCOL_VERSION, create_mcu_handler
from voice_assistant.mobile_bridge import ThreadingHTTPServer
from voice_assistant.remote_commands import RemoteCommandResult

class Recognized:
    text = "გახსენი სთიმი"
    confidence = 0.88

def request(base, path, token="secret-token", body=None, content_type="application/json"):
    req = Request(base+path, data=body, headers={"Authorization":"Bearer "+token,"Content-Type":content_type}, method="POST" if body is not None else "GET")
    try:
        with urlopen(req,timeout=2) as response:return response.status,json.loads(response.read())
    except HTTPError as exc:return exc.code,json.loads(exc.read())

def oversized_audio_request(server_port):
    connection=HTTPConnection("127.0.0.1",server_port,timeout=2)
    connection.putrequest("POST","/v1/mcu/audio")
    connection.putheader("Authorization","Bearer secret-token")
    connection.putheader("Content-Type","audio/L16")
    connection.putheader("Content-Length","180001")
    connection.endheaders()
    try:return connection.getresponse().status
    finally:connection.close()

def test_mcu_api_is_authenticated_and_allowlisted():
    actions=[]; connections=[]; commands=[]
    health={"cpuPercent":25,"memoryPercent":60,"diskFreePercent":40,"batteryPercent":80,"charging":True,"network":"online"}
    handler=create_mcu_handler("secret-token",audio_recognizer=lambda audio,rate,channels:Recognized(),executor=lambda text,language:RemoteCommandResult("executed",text,"Steam","Steam",None),status_supplier=lambda:{"gelaStatus":"sleeping","faceState":"IDLE","health":health},cancel=lambda:actions.append("cancel"),toggle_mute=lambda:actions.append("toggle-mute"),command_observer=commands.append,connection_observer=connections.append)
    server=ThreadingHTTPServer(("127.0.0.1",0),handler); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start(); base=f"http://127.0.0.1:{server.server_port}"
    try:
        assert request(base,"/v1/mcu/status",token="wrong")[0]==401
        status=request(base,"/v1/mcu/status")[1]
        assert status["faceState"]=="IDLE"
        assert status["protocolVersion"]==MCU_PROTOCOL_VERSION
        assert status["minimumProtocolVersion"]==1
        assert status["capabilities"]==list(MCU_CAPABILITIES)
        assert status["health"]==health
        command=request(base,"/v1/mcu/audio",body=b"\0"*2000,content_type="audio/L16")[1]
        assert command["matchedCommand"]=="Steam"
        assert commands and commands[-1].matched_command=="Steam"
        assert request(base,"/v1/mcu/audio",body=b"\0"*170_000,content_type="audio/L16")[0]==200
        assert oversized_audio_request(server.server_port)==413
        for action in ("cancel","toggle-mute"):assert request(base,"/v1/mcu/action",body=json.dumps({"action":action}).encode())[0]==200
        assert actions==["cancel","toggle-mute"]
        assert request(base,"/v1/mcu/action",body=b'{"action":"shutdown"}')[0]==400
        assert request(base,"/v1/mcu/event",body=b'{"type":"boot","detail":"192.168.1.5"}')[0]==200
        assert request(base,"/v1/mcu/event",body=b'{"type":"made-up"}')[0]==400
        assert connections and set(connections)=={"127.0.0.1"}
    finally:server.shutdown(); server.server_close()
