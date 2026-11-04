import logging
import subprocess

log = logging.getLogger(__name__)


def notify(message: str) -> None:
    log.info("notify: %s", message)
    subprocess.run(["notify-send", "--app-name=meetrec", "meetrec", message], check=False)
