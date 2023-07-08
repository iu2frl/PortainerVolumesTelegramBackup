# Create automated backups of Docker Volumes

This script scans the usual Docker Volumes path, compresses them to .tar.gz archive and sends it to a Telegram chat

## Usage

1. Clone the repo
2. Install requirements with `pip install -r ./requirements.txt`
3. Configure the BOT `API_KEY` in the environment variables (for example: `export BOT_TOKEN="000000:aaaaaBBBBBccccc"`)
4. Configure the destination chat in `BOT_DEST` (for example: `export BOT_DEST="000000:aaaaaBBBBBccccc"`)
5. (optional) Configure the volumes root path in `ROOT_DIR`
6. (optional) Configure a temporary path in `TMP_DIR` 
7. Execute the script `python3 ./main.py`

## Docker usage

1. Clone the repo
2. Build the image with `sudo docker build . -t docker-backup:latest`
3. Create a `.env` file with the environment variables (one per each line)
4. Execute the image with `sudo docker run --env-file=.env -v /var/lib/docker/volumes:/root/backup -it docker-backup` making sure to map the proper physical folder to `/root/backup`

## Image from Docker Hub

Link: [iu2frl/portainer-volumes-telegram-backup/general](https://hub.docker.com/repository/docker/iu2frl/portainer-volumes-telegram-backup/general)

## What if i have multiple volume paths?

You can map as many elements of the `ROOT_DIR` as you wish, for example:
- Environment: `ROOT_DIR=/root/backup/`
- Volumes: `-v /local/volume/path:/root/backup/someService -v /local/other/volume:/root/backup/someOtherService`
