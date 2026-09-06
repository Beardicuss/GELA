"""Gela face, Wi-Fi push-to-talk and controls for mPython Board 3.0."""
import audio, gc, json, lvgl as lv, network, os, random, select, socket, sys, time
from lv_oled import oled
from mpython import button_a, button_b

FRAME_ROOT="/gela_frames"; CONFIG_PATH="/gela_config.json"; RECORDING_PATH="/gela_command.wav"
MCU_PORT=8767; DISCOVERY_PORT=8766; DISCOVERY_REQUEST=b"GELA_DISCOVER_V1"
STATE_IDLE="IDLE"; STATE_LISTEN="LISTEN"; STATE_THINK="THINK"; STATE_ERROR="ERROR"; STATE_SUCCESS="SUCCESS"; STATE_TALK="TALK"
STATES=(STATE_IDLE,STATE_LISTEN,STATE_THINK,STATE_ERROR,STATE_SUCCESS,STATE_TALK)
IDLE_SEQUENCE=("idle_0.png","idle_1.png","idle_0.png","idle_2.png")
CALM_SEQUENCE=("calm_0.png","idle_1.png","calm_0.png","idle_2.png")
STATIC_STATES={STATE_LISTEN:("listen.png","listen_blink.png"),STATE_THINK:("think.png","think_blink.png"),STATE_ERROR:("error.png","error_blink.png"),STATE_SUCCESS:("success.png","success_blink.png")}
TALK_FRAMES=("talk_open.png","talk_closed.png")
AMBIENT_MOODS=("ATTENTIVE","CALM","SLEEPY","AWAY")

def load_config():
    try:
        with open(CONFIG_PATH,"r") as source: value=json.load(source)
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError): return {}

class FaceAnimator:
    def __init__(self):
        self.state=STATE_IDLE; self.mood="ATTENTIVE"; self.frame_index=0; self.next_frame_ms=0; self.return_to_idle_ms=None
        self.idle_blink_active=False; self.next_idle_blink_ms=time.ticks_add(time.ticks_ms(),7000+random.getrandbits(13))
        self.last_filename="idle_0.png"; self.status_text="USB"; self._draw_for_state(True)
    def draw(self,filename):
        self.last_filename=filename; oled.fill(0); oled.Bitmap(0,0,320,172,FRAME_ROOT+"/"+filename)
        if self.status_text:self._draw_small_status(self.status_text[:28])
        oled.show(); oled.canvas.init_layer(oled.layer); gc.collect()
    def _draw_small_status(self,text):
        background=lv.draw_rect_dsc_t(); background.init(); background.bg_color=lv.color_hex(0x000000); background.bg_opa=lv.OPA.COVER; background.border_width=0
        area=lv.area_t(); area.x1=0; area.y1=151; area.x2=319; area.y2=171; lv.draw_rect(oled.layer,background,area)
        label=lv.draw_label_dsc_t(); label.init(); label.color=lv.color_hex(0xB8B8B8); label.font=lv.font_montserrat_16; label.opa=lv.OPA.COVER; label.text=text
        area=lv.area_t(); area.x1=6; area.y1=152; area.x2=314; area.y2=171; lv.draw_label(oled.layer,label,area)
    def set_status(self,text):
        text=str(text)
        if text!=self.status_text: self.status_text=text; self.draw(self.last_filename)
    def set_state(self,state):
        if state not in STATES:return False
        if state==self.state:return True
        self.state=state; self.frame_index=0; now=time.ticks_ms()
        self.return_to_idle_ms=time.ticks_add(now,2200) if state in (STATE_SUCCESS,STATE_ERROR) else None
        self._draw_for_state(True); return True
    def set_mood(self,mood):
        if mood not in AMBIENT_MOODS or mood==self.mood:return
        self.mood=mood; self.frame_index=0; self.next_frame_ms=time.ticks_ms()
    def _schedule(self,now,minimum,jitter_bits=0): self.next_frame_ms=time.ticks_add(now,minimum+(random.getrandbits(jitter_bits) if jitter_bits else 0))
    def _draw_for_state(self,force=False):
        now=time.ticks_ms()
        if not force and time.ticks_diff(now,self.next_frame_ms)<0:return
        if self.return_to_idle_ms is not None and time.ticks_diff(now,self.return_to_idle_ms)>=0:self.state,self.frame_index,self.return_to_idle_ms=STATE_IDLE,0,None
        if self.state==STATE_IDLE:
            if self.mood=="ATTENTIVE":sequence,delay,jitter=IDLE_SEQUENCE,1250,9
            elif self.mood=="CALM":sequence,delay,jitter=CALM_SEQUENCE,1750,10
            elif self.mood=="SLEEPY":sequence,delay,jitter=("sleepy.png",),2500,10
            else:sequence,delay,jitter=("sleeping.png",),4500,11
            if self.idle_blink_active:
                self.idle_blink_active=False; self.next_idle_blink_ms=time.ticks_add(now,7000+random.getrandbits(13))
            elif ((self.mood=="ATTENTIVE" and self.last_filename=="idle_0.png") or (self.mood=="CALM" and self.last_filename=="calm_0.png")) and time.ticks_diff(now,self.next_idle_blink_ms)>=0:
                self.idle_blink_active=True; self.draw("idle_blink.png"); self._schedule(now,180); return
            filename=sequence[self.frame_index%len(sequence)]
            self.frame_index+=1; self.draw(filename); self._schedule(now,delay,jitter); return
        if self.state==STATE_TALK:
            self.draw(TALK_FRAMES[self.frame_index&1]); self.frame_index+=1; self._schedule(now,150,6); return
        base,blink=STATIC_STATES[self.state]
        if self.frame_index==1:self.draw(blink); self.frame_index=2; self._schedule(now,170)
        else:self.draw(base); self.frame_index=1; self._schedule(now,1800,11)
    def tick(self):self._draw_for_state()

class GelaWifi:
    def __init__(self,animator):
        self.animator=animator; self.config=load_config(); self.wlan=network.WLAN(network.STA_IF)
        self.host=self.config.get("host",""); self.token=self.config.get("token",""); self.next_connect_ms=0; self.next_status_ms=0; self.pc_online=False
    def configured(self):return bool(self.config.get("ssid") and self.config.get("password") and self.token)
    def maintain(self):
        now=time.ticks_ms()
        if not self.configured():self.animator.set_status("USB / SETUP WIFI"); return
        if not self.wlan.isconnected():
            if time.ticks_diff(now,self.next_connect_ms)>=0:self.wlan.active(True); self.wlan.connect(self.config["ssid"],self.config["password"]); self.next_connect_ms=time.ticks_add(now,8000)
            self.pc_online=False; self.animator.set_status("WIFI CONNECTING"); return
        if time.ticks_diff(now,self.next_status_ms)>=0:
            self.next_status_ms=time.ticks_add(now,2000)
            if not self.host:self.host=self.discover_pc() or ""
            try:
                status=self.request("GET","/v1/mcu/status"); self.pc_online=True
                face=status.get("faceState",STATE_IDLE)
                if face in STATES:self.animator.set_state(face)
                self.animator.set_mood(status.get("ambientMood","ATTENTIVE"))
                rssi=self.wlan.status("rssi"); signal="STRONG" if rssi>=-55 else ("GOOD" if rssi>=-70 else "WEAK")
                label="GELA PAUSED" if status.get("paused") else "PC ONLINE %s%s"%(signal," M" if status.get("mobileConnected") else "")
                self.animator.set_status(label)
            except Exception:self.pc_online=False; self.host=self.discover_pc() or self.host; self.animator.set_status("PC OFFLINE")
    def discover_pc(self):
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1); sock.settimeout(.6); sock.sendto(DISCOVERY_REQUEST,("255.255.255.255",DISCOVERY_PORT)); _payload,address=sock.recvfrom(512); return address[0]
        except OSError:return None
        finally:sock.close()
    def _send_all(self,sock,data):
        view=memoryview(data)
        while view:
            sent=sock.send(view)
            if not sent:raise OSError("socket closed")
            view=view[sent:]
    def request(self,method,path,body=None,content_type="application/json"):
        if not self.host:raise OSError("PC not discovered")
        sock=socket.socket(); sock.settimeout(22); sock.connect((self.host,MCU_PORT))
        try:
            length=len(body) if body is not None else 0
            headers=("%s %s HTTP/1.0\r\nHost: %s\r\nAuthorization: Bearer %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"%(method,path,self.host,self.token,content_type,length)).encode("ascii")
            self._send_all(sock,headers)
            if body is not None:self._send_all(sock,body)
            response=bytearray()
            while True:
                chunk=sock.recv(1024)
                if not chunk:break
                response.extend(chunk)
            header,payload=bytes(response).split(b"\r\n\r\n",1)
            if b" 200 " not in header.split(b"\r\n",1)[0]:raise OSError("PC returned an error")
            return json.loads(payload.decode("ascii"))
        finally:sock.close()
    def action(self,name):return self.request("POST","/v1/mcu/action",json.dumps({"action":name}).encode("ascii"))
    def push_to_talk(self):
        if not self.wlan.isconnected() or not self.pc_online:self.animator.set_state(STATE_ERROR); self.animator.set_status("PC OFFLINE"); return
        self.animator.set_state(STATE_LISTEN); self.animator.set_status("SPEAK - 4 SECONDS")
        try:
            audio.recorder_init(); audio.record(RECORDING_PATH,4); audio.recorder_deinit(); self.animator.set_state(STATE_THINK)
            with open(RECORDING_PATH,"rb") as source:source.read(44); pcm=source.read()
            result=self.request("POST","/v1/mcu/audio",pcm,"audio/L16")
            self.animator.set_state(STATE_SUCCESS if result.get("status")=="executed" else STATE_ERROR); self.animator.set_status("DONE" if result.get("status")=="executed" else "NOT UNDERSTOOD")
        except Exception:
            try:audio.recorder_deinit()
            except Exception:pass
            self.animator.set_state(STATE_ERROR); self.animator.set_status("COMMAND FAILED")
        finally:
            try:os.remove(RECORDING_PATH)
            except OSError:pass

def parse_state_line(line):
    parts=line.strip().upper().split()
    return parts[2] if len(parts)==3 and parts[0]=="GELA1" and parts[1]=="STATE" and parts[2] in STATES else None

def run():
    animator=FaceAnimator(); wifi=GelaWifi(animator); incoming=select.poll(); incoming.register(sys.stdin,select.POLLIN)
    a_started=b_started=None; handled=False
    while True:
        if incoming.poll(0):
            state=parse_state_line(sys.stdin.readline())
            if state is not None:animator.set_state(state); print("GELA1 OK STATE "+state)
        a,b=button_a.is_pressed(),button_b.is_pressed(); now=time.ticks_ms()
        if a and a_started is None:a_started=now
        if b and b_started is None:b_started=now
        if a and b and not handled:
            handled=True
            try:wifi.action("toggle-mute"); animator.set_status("PC MUTE TOGGLED")
            except Exception:animator.set_status("PC OFFLINE")
        elif not a and not b and a_started is not None and not handled:
            handled=True; wifi.push_to_talk()
        if not a and not b:a_started=b_started=None; handled=False
        wifi.maintain(); animator.tick(); time.sleep_ms(20)
