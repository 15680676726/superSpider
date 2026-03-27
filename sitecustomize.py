import os

os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "logfire-plugin")
