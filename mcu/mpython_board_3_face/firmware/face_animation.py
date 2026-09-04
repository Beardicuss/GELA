"""Gela face, Wi-Fi push-to-talk and controls for mPython Board 3.0."""
import _thread, audio, gc, json, lvgl as lv, network, os, random, select, socket, sys, time
from lv_oled import oled
from mpython import button_a, button_b, touchPad_N

FRAME_ROOT="/gela_frames"; CONFIG_PATH="/gela_config.json"; RECORDING_PATH="/gela_command_%d.wav"
MCU_PORT=8767; MCU_PROTOCOL_VERSION=2; DISCOVERY_PORT=8766; DISCOVERY_REQUEST=b"GELA_DISCOVER_V1"
RECORDING_MIN_MS=300; RECORDING_TAIL_MS=250; RECORDING_CHUNKS=1; WAV_HEADER_BYTES=44
STATE_IDLE="IDLE"; STATE_LISTEN="LISTEN"; STATE_THINK="THINK"; STATE_ERROR="ERROR"; STATE_SUCCESS="SUCCESS"; STATE_TALK="TALK"
STATES=(STATE_IDLE,STATE_LISTEN,STATE_THINK,STATE_ERROR,STATE_SUCCESS,STATE_TALK)
IDLE_SEQUENCE=("idle_0.png","idle_1.png","idle_0.png","idle_2.png","idle_0.png","idle_3.png")
STATIC_STATES={STATE_LISTEN:("listen.png","listen_blink.png"),STATE_THINK:("think.png","think_blink.png"),STATE_ERROR:("error.png","error_blink.png"),STATE_SUCCESS:("success.png","success_blink.png")}
TALK_FRAMES=("talk_open.png","talk_closed.png")

class HttpError(Exception):
    def __init__(self,status):self.status=status

def load_config():
    try:
        with open(CONFIG_PATH,"r") as source: value=json.load(source)
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError): return {}

class FaceAnimator:
    def __init__(self):
        self.state=STATE_IDLE; self.frame_index=0; self.next_frame_ms=0; self.return_to_idle_ms=None
        self.last_filename="idle_0.png"; self.status_text="USB"; self.health=None; self.activity=None; self.card_until_ms=None; self._draw_for_state(True)
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
        if text!=self.status_text:
            self.status_text=text
            if not self.card_active():self.draw(self.last_filename)
    def set_state(self,state):
        if state not in STATES:return False
        if state==self.state:return True
        self.state=state; self.frame_index=0; now=time.ticks_ms()
        self.return_to_idle_ms=time.ticks_add(now,2200) if state in (STATE_SUCCESS,STATE_ERROR) else None
        if not self.card_active():self._draw_for_state(True)
        return True
    def card_active(self):return self.card_until_ms is not None and time.ticks_diff(self.card_until_ms,time.ticks_ms())>0
    def _health_line(self,text,y,color=0xD8D8D8):
        label=lv.draw_label_dsc_t(); label.init(); label.color=lv.color_hex(color); label.font=lv.font_montserrat_16; label.opa=lv.OPA.COVER; label.text=text
        area=lv.area_t(); area.x1=18; area.y1=y; area.x2=304; area.y2=y+22; lv.draw_label(oled.layer,label,area)
    def show_health(self,health=None):
        if isinstance(health,dict):self.health=health
        if not isinstance(self.health,dict):return False
        self.card_until_ms=time.ticks_add(time.ticks_ms(),10000); oled.fill(0)
        self._health_line("PC HEALTH",10,0xE45A52)
        cpu=self.health.get("cpuPercent"); memory=self.health.get("memoryPercent"); disk=self.health.get("diskFreePercent")
        self._health_line("CPU   %s%%"%("--" if cpu is None else cpu),42)
        self._health_line("RAM   %s%%"%("--" if memory is None else memory),66)
        self._health_line("DISK  %s%% FREE"%("--" if disk is None else disk),90)
        self._health_line("NET   "+str(self.health.get("network","unknown")).upper(),114)
        battery=self.health.get("batteryPercent")
        if battery is not None:self._health_line("BAT   %s%% %s"%(battery,"AC" if self.health.get("charging") else ""),138)
        else:self._health_line("HOLD N TO REFRESH",138,0x888888)
        oled.show(); oled.canvas.init_layer(oled.layer); gc.collect(); return True
    def show_activity(self,activity=None,duration_ms=10000):
        if isinstance(activity,dict):self.activity=activity
        if not isinstance(self.activity,dict):return False
        self.card_until_ms=time.ticks_add(time.ticks_ms(),duration_ms); oled.fill(0)
        self._health_line("CURRENT ACTIVITY",10,0xE45A52)
        self._health_line("GELA  "+str(self.activity.get("gelaStatus","UNKNOWN"))[:22],42)
        transcript=str(self.activity.get("transcript","") or "NO COMMAND YET")
        self._health_line("HEARD "+transcript[:27],70)
        matched=str(self.activity.get("matchedCommand","") or "-")
        self._health_line("MATCH "+matched[:27],98)
        result=str(self.activity.get("result","") or "READY")
        source=str(self.activity.get("source","") or "PC")
        self._health_line(result[:24],126,0xE45A52 if "FAILED" in result or "NOT FOUND" in result else 0xD8D8D8)
        self._health_line("SOURCE "+source[:12],150,0x888888)
        oled.show(); oled.canvas.init_layer(oled.layer); gc.collect(); return True
    def _schedule(self,now,minimum,jitter_bits=0): self.next_frame_ms=time.ticks_add(now,minimum+(random.getrandbits(jitter_bits) if jitter_bits else 0))
    def _draw_for_state(self,force=False):
        now=time.ticks_ms()
        if not force and time.ticks_diff(now,self.next_frame_ms)<0:return
        if self.return_to_idle_ms is not None and time.ticks_diff(now,self.return_to_idle_ms)>=0:self.state,self.frame_index,self.return_to_idle_ms=STATE_IDLE,0,None
        if self.state==STATE_IDLE:
            filename=IDLE_SEQUENCE[self.frame_index%len(IDLE_SEQUENCE)]
            if filename=="idle_0.png" and random.getrandbits(4)==0:filename="idle_blink.png"
            self.frame_index+=1; self.draw(filename); self._schedule(now,1250,9); return
        if self.state==STATE_TALK:
            self.draw(TALK_FRAMES[self.frame_index&1]); self.frame_index+=1; self._schedule(now,150,6); return
        base,blink=STATIC_STATES[self.state]
        if self.frame_index==1:self.draw(blink); self.frame_index=2; self._schedule(now,170)
        else:self.draw(base); self.frame_index=1; self._schedule(now,1800,11)
    def tick(self):
        if self.card_until_ms is not None:
            if self.card_active():return
            self.card_until_ms=None; self._draw_for_state(True); return
        self._draw_for_state()

class GelaWifi:
    def __init__(self,animator):
        self.animator=animator; self.config=load_config(); self.wlan=network.WLAN(network.STA_IF)
        self.host=self.config.get("host",""); self.token=self.config.get("token",""); self.next_connect_ms=0; self.next_status_ms=0; self.pc_online=False; self.failures=0; self.session_reported=False
        self.recording=False; self.recording_started_ms=0; self.recording_seconds=-1; self.stop_recording_ms=None; self.recording_done=False; self.recording_error=None; self.recording_paths=[]
        self.sending=False; self.send_done=False; self.send_result=None; self.send_error=None
        for index in range(3):
            try:os.remove(RECORDING_PATH%index)
            except OSError:pass
    def configured(self):return bool(self.config.get("ssid") and self.config.get("password") and self.token)
    def maintain(self):
        now=time.ticks_ms()
        if self.recording or self.sending:return
        if not self.configured():self.animator.set_status("USB / SETUP WIFI"); return
        if not self.wlan.isconnected():
            if time.ticks_diff(now,self.next_connect_ms)>=0:self.wlan.active(True); self.wlan.connect(self.config["ssid"],self.config["password"]); self.next_connect_ms=time.ticks_add(now,8000)
            self.pc_online=False; self.animator.set_status("WIFI CONNECTING"); return
        if time.ticks_diff(now,self.next_status_ms)>=0:
            self.next_status_ms=time.ticks_add(now,2000)
            if not self.host:self.host=self.discover_pc() or ""
            try:
                was_offline=not self.pc_online; status=self.request("GET","/v1/mcu/status"); self.pc_online=True; self.failures=0
                if int(status.get("minimumProtocolVersion",1))>MCU_PROTOCOL_VERSION:raise HttpError(426)
                face=status.get("faceState",STATE_IDLE)
                if face in STATES:self.animator.set_state(face)
                if isinstance(status.get("health"),dict):self.animator.health=status.get("health")
                if isinstance(status.get("activity"),dict):self.animator.activity=status.get("activity")
                rssi=self.wlan.status("rssi"); signal="STRONG" if rssi>=-55 else ("GOOD" if rssi>=-70 else "WEAK")
                label="GELA PAUSED" if status.get("paused") else "PC ONLINE %s%s"%(signal," M" if status.get("mobileConnected") else "")
                self.animator.set_status(label)
                if was_offline:
                    try:
                        if not self.session_reported:self.event("boot"); self.event("wifi-connected",self.wlan.ifconfig()[0]); self.session_reported=True
                        self.event("pc-reconnected")
                    except Exception:pass
            except HttpError as exc:
                self.pc_online=False; self.failures+=1; self.next_status_ms=time.ticks_add(now,min(30000,1000*(2**min(self.failures,5))))
                self.animator.set_status("UPDATE GELA" if exc.status==426 else ("AUTH ERROR" if exc.status in (401,403) else "PC ERROR %d"%exc.status))
            except Exception:
                self.pc_online=False; self.failures+=1; self.next_status_ms=time.ticks_add(now,min(30000,1000*(2**min(self.failures,5))))
                if self.failures>=3:self.host=self.discover_pc() or ""
                self.animator.set_status("PC OFFLINE")
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
            headers=("%s %s HTTP/1.0\r\nHost: %s\r\nAuthorization: Bearer %s\r\nX-Gela-MCU-Protocol: %d\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"%(method,path,self.host,self.token,MCU_PROTOCOL_VERSION,content_type,length)).encode("ascii")
            self._send_all(sock,headers)
            if body is not None:self._send_all(sock,body)
            response=bytearray()
            while True:
                chunk=sock.recv(1024)
                if not chunk:break
                response.extend(chunk)
            header,payload=bytes(response).split(b"\r\n\r\n",1)
            status_line=header.split(b"\r\n",1)[0]; status=int(status_line.split()[1])
            if status!=200:raise HttpError(status)
            return json.loads(payload.decode("ascii"))
        finally:sock.close()
    def action(self,name):return self.request("POST","/v1/mcu/action",json.dumps({"action":name}).encode("ascii"))
    def event(self,event_type,detail=""):return self.request("POST","/v1/mcu/event",json.dumps({"type":event_type,"detail":detail}).encode("ascii"))
    def _record_worker(self):
        try:
            audio.recorder_init()
            for index in range(RECORDING_CHUNKS):
                if not self.recording:break
                path=RECORDING_PATH%index; audio.record(path,5)
                try:
                    if os.stat(path)[6]>WAV_HEADER_BYTES:self.recording_paths.append(path)
                except OSError:pass
        except Exception as exc:self.recording_error=repr(exc)
        finally:
            try:audio.recorder_deinit()
            except Exception:pass
            self.recording=False; self.recording_done=True
    def start_push_to_talk(self):
        if not self.wlan.isconnected() or not self.pc_online:self.animator.set_state(STATE_ERROR); self.animator.set_status("PC OFFLINE"); return
        if self.recording:return
        for index in range(RECORDING_CHUNKS):
            try:os.remove(RECORDING_PATH%index)
            except OSError:pass
        storage=os.statvfs('/'); free_bytes=storage[0]*storage[3]
        if free_bytes<86000:self.animator.set_state(STATE_ERROR); self.animator.set_status("STORAGE FULL"); return
        self.recording=True; self.recording_done=False; self.recording_error=None; self.recording_paths=[]; self.stop_recording_ms=None; self.recording_started_ms=time.ticks_ms(); self.recording_seconds=0
        self.animator.set_state(STATE_LISTEN); self.animator.set_status("HOLD A - SPEAK")
        try:
            try:self.event("command-started")
            except Exception:pass
            _thread.start_new_thread(self._record_worker,())
        except Exception:
            self.recording=False; self.recording_done=True; self.recording_error="thread start failed"
    def release_push_to_talk(self):
        if self.recording and self.stop_recording_ms is None:
            elapsed=time.ticks_diff(time.ticks_ms(),self.recording_started_ms)
            self.stop_recording_ms=time.ticks_add(time.ticks_ms(),RECORDING_TAIL_MS+max(0,RECORDING_MIN_MS-elapsed))
            self.animator.set_status("FINISHING...")
    def _send_recording_worker(self):
        try:
            if self.recording_error or not self.recording_paths:raise OSError("recording failed")
            total=sum(os.stat(path)[6]-WAV_HEADER_BYTES for path in self.recording_paths)
            sock=socket.socket(); sock.settimeout(25); sock.connect((self.host,MCU_PORT))
            try:
                headers=("POST /v1/mcu/audio HTTP/1.0\r\nHost: %s\r\nAuthorization: Bearer %s\r\nX-Gela-MCU-Protocol: %d\r\nContent-Type: audio/L16\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"%(self.host,self.token,MCU_PROTOCOL_VERSION,total)).encode("ascii")
                self._send_all(sock,headers)
                for path in self.recording_paths:
                    with open(path,"rb") as source:
                        source.read(WAV_HEADER_BYTES)
                        while True:
                            chunk=source.read(2048)
                            if not chunk:break
                            self._send_all(sock,chunk)
                response=bytearray()
                while True:
                    chunk=sock.recv(1024)
                    if not chunk:break
                    response.extend(chunk)
            finally:sock.close()
            header,payload=bytes(response).split(b"\r\n\r\n",1)
            if int(header.split(b"\r\n",1)[0].split()[1])!=200:raise OSError("PC returned an error")
            self.send_result=json.loads(payload.decode("ascii"))
            for path in self.recording_paths:
                try:os.remove(path)
                except OSError:pass
            self.recording_paths=[]
        except Exception as exc:self.send_error=repr(exc)
        finally:
            for path in self.recording_paths:
                try:os.remove(path)
                except OSError:pass
            self.recording_paths=[]; self.send_done=True; self.sending=False
    def recording_tick(self):
        now=time.ticks_ms()
        if self.recording and self.stop_recording_ms is None:
            seconds=min(15,max(0,time.ticks_diff(now,self.recording_started_ms)//1000))
            if seconds!=self.recording_seconds:self.recording_seconds=seconds; self.animator.set_status("RECORDING %dS"%seconds)
        if self.recording and self.stop_recording_ms is not None and time.ticks_diff(now,self.stop_recording_ms)>=0:
            self.recording=False
            try:audio.recorder_deinit()
            except Exception:pass
        if self.recording_done and not self.sending:
            self.recording_done=False; self.sending=True; self.send_done=False; self.send_result=None; self.send_error=None
            self.animator.set_state(STATE_THINK); self.animator.set_status("PROCESSING")
            try:_thread.start_new_thread(self._send_recording_worker,())
            except Exception as exc:self.sending=False; self.send_done=True; self.send_error=repr(exc)
        if self.send_done:
            self.send_done=False; self.stop_recording_ms=None
            result=self.send_result or {}; succeeded=not self.send_error and result.get("status")=="executed"
            self.animator.set_state(STATE_SUCCESS if succeeded else STATE_ERROR)
            self.animator.set_status("DONE" if succeeded else ("NOT UNDERSTOOD" if result else "COMMAND FAILED"))
            feedback={"gelaStatus":"READY","source":"BOARD","transcript":result.get("transcript","")}
            feedback["matchedCommand"]=result.get("matchedCommand","")
            feedback["result"]="COMPLETED" if succeeded else ("COMMAND NOT FOUND" if result.get("status")=="not-understood" else "COMMAND FAILED")
            self.animator.show_activity(feedback,6000)
            try:self.event("command-finished",result.get("status","failed"))
            except Exception:pass

def parse_state_line(line):
    parts=line.strip().upper().split()
    return parts[2] if len(parts)==3 and parts[0]=="GELA1" and parts[1]=="STATE" and parts[2] in STATES else None

def run():
    animator=FaceAnimator(); wifi=GelaWifi(animator); incoming=select.poll(); incoming.register(sys.stdin,select.POLLIN)
    a_started=b_started=n_started=None; handled=False; n_handled=False
    while True:
        if incoming.poll(0):
            state=parse_state_line(sys.stdin.readline())
            if state is not None:animator.set_state(state); print("GELA1 OK STATE "+state)
        a,b,n=button_a.is_pressed(),button_b.is_pressed(),touchPad_N.is_pressed(); now=time.ticks_ms()
        if a and a_started is None:a_started=now
        if b and b_started is None:b_started=now
        if n and n_started is None:n_started=now
        if n and not n_handled and time.ticks_diff(now,n_started)>=700:
            n_handled=True
            if not animator.show_health():animator.set_status("HEALTH NOT READY")
        if a and b and not handled and not wifi.recording:
            handled=True
            try:wifi.action("toggle-mute"); animator.set_status("PC MUTE TOGGLED")
            except Exception:animator.set_status("PC OFFLINE")
        elif a and not b and not handled and time.ticks_diff(now,a_started)>=180:handled=True; wifi.start_push_to_talk()
        elif b and not a and not handled and time.ticks_diff(now,b_started)>=180:
            handled=True
            try:wifi.action("cancel"); animator.set_state(STATE_IDLE); animator.set_status("CANCELLED")
            except Exception:animator.set_status("PC OFFLINE")
        if not a and not b:
            if handled:wifi.release_push_to_talk()
            a_started=b_started=None; handled=False
        if not n:
            if n_started is not None and not n_handled and time.ticks_diff(now,n_started)>=60:
                if not animator.show_activity():animator.set_status("ACTIVITY NOT READY")
            n_started=None; n_handled=False
        wifi.recording_tick(); wifi.maintain(); animator.tick(); time.sleep_ms(20)
