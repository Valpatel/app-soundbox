---
name: service
description: Manage the Sound Box systemd service (start, stop, restart, status, logs)
disable-model-invocation: true
allowed-tools: Bash
argument-hint: "[status|start|stop|restart|logs|install|uninstall]"
---

## Service Management

Manage the Sound Box systemd service using `./service.sh`.

Run: `./service.sh $ARGUMENTS`

If no argument provided, run `./service.sh status` and show the current state.

Valid commands: install, uninstall, enable, disable, start, stop, restart, status, logs

After running, summarize the service state.
