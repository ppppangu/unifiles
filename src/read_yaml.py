import yaml
from pathlib import Path

def read_config():
    """读取配置文件"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config