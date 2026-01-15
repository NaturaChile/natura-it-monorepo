import win32com.client
import subprocess
import time 

subprocess.Popen(r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe")
time.sleep(5)
SapGuiAuto = win32com.client.GetObject("SAPGUI")
application = SapGuiAuto.GetScriptingEngine
time.sleep(5)
connection = application.OpenConnection("1.02 - PRD - Produção/Producción", True)
session = connection.Children(0)
session.findById("wnd[0]/usr/txtRSYST-MANDT").text ="210"
session.findById("wnd[0]/usr/txtRSYST-BNAME").text = "Robotch_fin"
session.findById("wnd[0]/usr/pwdRSYST-BCODE").text  = "Clave.nueva.2026"
session.findById("wnd[0]/usr/txtRSYST-LANGU").text = "ES"
session.findById("wnd[0]").sendVKey(0)
session.findById("wnd[0]/tbar[0]/okcd").text = "mb52"
session.findById("wnd[0]").sendVKey (0)
