# Security boundary

This is a disposable public demo, not a hardened appliance. The CI VM has **no NIC, virtual disk, shared host directory, SSH service or account credential**. Source and fixture data are synthetic. Changes live in RAM. Docker builds accept only the explicitly listed image, script and fixture files, with no privileged mode or home mounts.

The root and kiosk passwords are locked. Emacs runs as kiosk; PID 1 and the local X server run as root. Xorg has TCP listening disabled but local access control is relaxed for this one-user demo. Physical/UI access gives a shell and is not a security boundary. The image is not designed to be attached to an untrusted network or installed on hardware.

No AI client or Slack adapter is installed. A real integration requires separate reviewed runtime permissions and vendor-supported interactive authentication, outside this image and its build. Never put tokens in source, build arguments, artifacts, logs or recordings. Do not mount a host home or expose tmux sockets.

Alpine branch packages receive updates; exact resolved versions are included with every build. The image is not package-digest locked. There is no update, persistence, secure-boot or rollback implementation. Use a supported installed distribution for any real deployment and design those features explicitly.
