import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from voice_assistant.mcu_terminal import create_mcu_handler
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

def test_mcu_api_is_authenticated_and_allowlisted():
    actions=[]
    handler=create_mcu_handler("secret-token",audio_recognizer=lambda audio,rate,channels:Recognized(),executor=lambda text,language:RemoteCommandResult("executed",text,"Steam","Steam",None),status_supplier=lambda:{"gelaStatus":"sleeping","faceState":"IDLE"},cancel=lambda:actions.append("cancel"),toggle_mute=lambda:actions.append("toggle-mute"))
    server=ThreadingHTTPServer(("127.0.0.1",0),handler); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start(); base=f"http://127.0.0.1:{server.server_port}"
    try:
        assert request(base,"/v1/mcu/status",token="wrong")[0]==401
        assert request(base,"/v1/mcu/status")[1]["faceState"]=="IDLE"
        assert request(base,"/v1/mcu/audio",body=b"\0"*2000,content_type="audio/L16")[1]["matchedCommand"]=="Steam"
        for action in ("cancel","toggle-mute"):assert request(base,"/v1/mcu/action",body=json.dumps({"action":action}).encode())[0]==200
        assert actions==["cancel","toggle-mute"]
        assert request(base,"/v1/mcu/action",body=b'{"action":"shutdown"}')[0]==400
    finally:server.shutdown(); server.server_close()
