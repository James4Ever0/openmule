Open source Computer Using Agent marketplace - MuleRun alternative

---

openmule can either relay traffic between CUA servers (ai controller) and clients (command receivers, executors), pay bills to servers, or host its own servers by putting all config files to openmule server.

---

Agent framework: [trycua/cua](https://github.com/trycua/cua)

Accounting framework: [cybergod-gym](https://github.com/James4Ever0/agi_computer_control/tree/master/gym-primitives%2Fcybergod)

AI billing: litellm

Frontend: vue3

Backend: fastapi, websocket

---

use YAML for storing agent prompt, Dockerfile, billing info, input and output file, remote machine vnc credential info etc


---

can control user defined remote machine, cloud machine, openmule hosted machine or remote openmule client

---

users are recommended to use a virtualized machine to be controlled by openmule, or a remote managed vm instance.

---

the user shall have a webui interface to virtualized machine which is being controlled, with a password, to configure cua connection details and view logs, and a dialogue to confirm if this machine is bare metal without virtualization, if so then any keyboard or mouse movement will trigger emergency stop, or some other action like moving mouse to a specific corner
