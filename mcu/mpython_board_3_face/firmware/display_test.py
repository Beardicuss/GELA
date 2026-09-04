"""Non-persistent display test for the installed mPython Pro firmware."""

import time

from lv_oled import oled


oled.fill(0)
oled.DispChar("GELA DISPLAY OK", 56, 68, 1)
oled.show()
time.sleep(3)
