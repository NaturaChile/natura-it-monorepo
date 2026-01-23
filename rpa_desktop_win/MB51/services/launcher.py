import subprocess
import os


def launch_sap(system: str, client: str, user: str, pw: str, lang: str, exe_path: str = None, extra_args: list = None) -> None:
    """Lanza SAP usando sapshcut.exe con argumentos básicos. Copiado de sap_bot/services/launcher.py"""
    exe = exe_path or r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\sapshcut.exe"
    if not os.path.exists(exe):
        raise FileNotFoundError(f"No encuentro sapshcut.exe en: {exe}")

    cmd = [exe, f"-system={system}", f"-client={client}", f"-user={user}", f"-pw={pw}", f"-language={lang}", "-maxgui"]
    if extra_args:
        cmd.extend(extra_args)

    subprocess.Popen(cmd)
