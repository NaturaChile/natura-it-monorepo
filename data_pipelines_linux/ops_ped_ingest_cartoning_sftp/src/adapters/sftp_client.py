import os
import paramiko
from dataclasses import dataclass

@dataclass
class SftpConfig:
    host: str
    user: str
    password: str
    remote_path: str

class SftpClient:
    def __init__(self, config: SftpConfig):
        self.cfg = config

    def _connect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.cfg.host, username=self.cfg.user, password=self.cfg.password, timeout=15)
        return ssh, ssh.open_sftp()

    def list_files(self):
        """Retorna lista de archivos con sus atributos (nombre, tamaño, fecha)."""
        ssh, sftp = None, None
        try:
            ssh, sftp = self._connect()
            files = sftp.listdir_attr(self.cfg.remote_path)
            # Filtramos solo archivos, no carpetas
            return [f for f in files if not str(f).startswith('d')]
        except Exception as e:
            print(f" Error SFTP Listing: {e}")
            return []
        finally:
            if sftp: sftp.close()
            if ssh: ssh.close()

    def download_file(self, filename: str, local_dir: str) -> bool:
        ssh, sftp = None, None
        try:
            ssh, sftp = self._connect()
            remote = f"{self.cfg.remote_path}/{filename}"
            local = os.path.join(local_dir, filename)
            sftp.get(remote, local)
            return True
        except Exception as e:
            print(f" Error descargando {filename}: {e}")
            return False
        finally:
            if sftp: sftp.close()
            if ssh: ssh.close()