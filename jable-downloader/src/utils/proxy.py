"""
Clash proxy pool — spawn N Clash instances with different nodes for multi-IP downloads.

config.json example:
  {
    "proxy": {
      "clash_exe": "D:/Tools/clash.exe",
      "clash_config": "D:/Tools/config.yaml",
      "num_instances": 5,
      "base_port": 7890
    }
  }
"""

import atexit
import os
import subprocess
import threading
from pathlib import Path


class ClashPool:
    """Round-robin pool of local Clash proxy instances."""

    def __init__(self, clash_exe, clash_config, num_instances=5, base_port=7890,
                 skip_keywords=None):
        self.processes = []
        self._proxies = []
        self._index = 0
        self._lock = threading.Lock()

        exe = Path(clash_exe)
        cfg = Path(clash_config)
        if not exe.exists():
            raise FileNotFoundError(f'Clash not found: {exe}')
        if not cfg.exists():
            raise FileNotFoundError(f'Config not found: {cfg}')

        import yaml

        skip = skip_keywords or ['DIRECT', 'REJECT']
        with open(cfg, 'r', encoding='utf-8') as f:
            base = yaml.safe_load(f)

        nodes = [p for p in base.get('proxies', [])
                 if not any(k in p.get('name', '') for k in skip)]
        count = min(num_instances, len(nodes))
        if count == 0:
            print('[proxy] No usable nodes in config.')
            return

        tmp = Path('temp/clash_instances')
        tmp.mkdir(parents=True, exist_ok=True)

        for i in range(count):
            port = base_port + i * 10
            node = nodes[i]
            inst_cfg = {
                **base,
                'port': port,
                'socks-port': port + 1,
                'external-controller': f'127.0.0.1:{9090 + i}',
                'proxies': [node],
                'proxy-groups': [{'name': 'PROXY', 'type': 'select',
                                  'proxies': [node['name']]}],
                'rules': ['MATCH,PROXY'],
            }
            inst_file = tmp / f'clash_{i}.yaml'
            with open(inst_file, 'w', encoding='utf-8') as f:
                yaml.dump(inst_cfg, f, allow_unicode=True, default_flow_style=False)

            try:
                proc = subprocess.Popen(
                    [str(exe), '-f', str(inst_file)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
                self.processes.append(proc)
                self._proxies.append({
                    'http': f'http://127.0.0.1:{port}',
                    'https': f'http://127.0.0.1:{port}',
                })
            except Exception as e:
                print(f'[proxy] Instance {i} failed: {e}')

        if self._proxies:
            print(f'[proxy] {len(self._proxies)} instance(s) ready')
        atexit.register(self.cleanup)

    def get_proxy(self):
        if not self._proxies:
            return None
        with self._lock:
            p = self._proxies[self._index]
            self._index = (self._index + 1) % len(self._proxies)
            return p

    def size(self):
        return len(self._proxies)

    def cleanup(self):
        for proc in self.processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.processes.clear()


def load_proxy_pool(config):
    """Build ClashPool from config dict (``config.json['proxy']``). Returns None if not configured."""
    pcfg = config.get('proxy')
    if not pcfg or not pcfg.get('clash_exe'):
        return None
    return ClashPool(
        clash_exe=pcfg['clash_exe'],
        clash_config=pcfg['clash_config'],
        num_instances=pcfg.get('num_instances', 5),
        base_port=pcfg.get('base_port', 7890),
        skip_keywords=pcfg.get('skip_keywords'),
    )
