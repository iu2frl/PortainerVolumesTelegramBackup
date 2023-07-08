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

# Crontab example

This example creates a backup of everything in `/var/snap/docker/common/var-lib-docker/volumes` plus `/home/iu2frl/guacamole` every Sunday at 2am, execution log is sent to `/tmp/port-backup-log.txt`

```bash
# For example, you can run a backup of all your user accounts
# at 5 a.m every week with:
# 0 5 * * 1 tar -zcf /var/backups/home.tgz /home/
# 
# For more information see the manual pages of crontab(5) and cron(8)
# 
# m h  dom mon dow   command
0 2 * * Sun docker run -itd -v /var/snap/docker/common/var-lib-docker/volumes:/root/backup -v /home/ubuntu/guacamole:/root/backup/guacamole --env-file=/home/iu2frl/portainer-backup.env --rm iu2frl/portainer-volumes-telegram-backup:latest > /tmp/port-backup-log.txt 2>&1
```
