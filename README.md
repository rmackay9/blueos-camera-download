# Camera Download

BlueOS Extension to download images and videos from camera gimbals connected via Ethernet

## Usage

Users should select the Camera Type and update the IP address if different from the default

Push the "Ping" button to confirm the camera can be reached

Push the "Download" button to download images and videos from the camera gimbal.  Results of the download are displayed in the text area at the bottom of the screen

## Developer Information

To build and publish for Ubuntu, RPI3, RPI4, RPI5

- Open docker desktop (required only on Windows WSL2 machines)
- docker buildx build --platform linux/amd64,linux/arm/v7,linux/arm64/v8 . -t YOURDOCKERHUBUSER/blueos-camera-download:latest --output type=registry
- login to https://hub.docker.com/repositories/ and confirm the image has appeared

To manually install the extension in BlueOS

- Start BlueOS on RPI, open Chrome browser and connect to BlueOS (e.g. via WifiAP use http://blueos-hotspot.local/, if on same network use http://blueos-avahi.local/)
- Open BlueOS Extensions tab, select Installed
  - Push "+" button on the bottom right
  - Under "Create Extension" fill in these fields
    - Extension Identifier: YOURDOCKERHUBUSER.YOURDOCKERHUBREPO
    - Extension Name: Camera Download
    - Docker image: YOURDOCKERHUBUSER/YOURDOCKERHUBREPO
    - Dockertag: latest
    - Settings: add the lines below after replacing the capitalised values with your DockerHub username and repository name

```
{
  "ExposedPorts": {
    "8000/tcp": {}
  },
  "HostConfig": {
    "Binds":[
      "/usr/blueos/extensions/camera-download/downloads:/app/downloads",
      "/usr/blueos/extensions/camera-download/settings:/app/settings",
      "/usr/blueos/extensions/camera-download/logs:/app/logs"
      ],
    "PortBindings": {
      "8000/tcp": [
        {
          "HostPort": ""
        }
      ]
    }
  }
}
```

  - "Camera Download" should appear in list of installed extensions and "Status" should appear as "Up xx seconds"

To test on an Ubuntu PC

- Ensure the PC and camera is on the same ethernet subnet
- Open docker desktop (required only on Windows WSL2 machines)
- docker build -t YOURDOCKERHUBUSER/YOURDOCKERHUBREPO:latest .
- docker run -p 8000:8000 YOURDOCKERHUBUSER/YOURDOCKERHUBREPO:latest
- On docker desktop, Containers, a new image should appear with "Port(s)" field, "8000:8000".  Click to open a browser
- Within the web browser the Camera Download page should appear, set the "IP Address" field to the IP address of the camera
