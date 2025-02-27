import os
import logging
from datetime import datetime
import tarfile
import telebot
import requests

logFile = "/tmp/" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
logging.basicConfig(filename=logFile, level=logging.DEBUG)

TELEGRAM_API_TOKEN: str = os.environ.get('BOT_TOKEN')
if not TELEGRAM_API_TOKEN:
    logging.critical("Input token is empty!")
    raise Exception("Invalid BOT_TOKEN")
else:
    logging.debug("BOT_TOKEN length: [%s]", len(TELEGRAM_API_TOKEN))

# Get destination chat
TELEGRAM_DEST_CHAT: str = os.environ.get('BOT_DEST')
if not TELEGRAM_DEST_CHAT:
    logging.critical("Destination chat is empty!")
    raise Exception("Invalid BOT_DEST")
else:
    TELEGRAM_DEST_CHAT: int = int(TELEGRAM_DEST_CHAT)
    logging.debug("BOT_DEST: [%s]", TELEGRAM_DEST_CHAT)

bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

# Custom message to send before files list
TELEGRAM_BACKUP_MESSAGE: str = os.environ.get('CUST_MSG')
if not TELEGRAM_BACKUP_MESSAGE:
    TELEGRAM_BACKUP_MESSAGE = "Backup at " + datetime.now().strftime("%Y%m%d_%H%M%S")
else:
    TELEGRAM_BACKUP_MESSAGE += "\n\nBackup at " + datetime.now().strftime("%Y%m%d_%H%M%S")

# Get volumes root path
DOCKER_VOLUME_DIRECTORIES: str = os.environ.get('ROOT_DIR')
if not DOCKER_VOLUME_DIRECTORIES:
    # Common volumes locations
    DOCKER_VOLUME_DIRECTORIES = ["/var/snap/docker/common/var-lib-docker/volumes/", "/var/lib/docker/volumes", "/root/backup"]
    logging.warning("ROOT_DIR is empty, falling back to default path(s): %s", DOCKER_VOLUME_DIRECTORIES)
else:
    # Get directories from environment
    DOCKER_VOLUME_DIRECTORIES = [str(x).split() for x in DOCKER_VOLUME_DIRECTORIES.split(",")]

# Get temporary path
TMP_DIR: str = os.environ.get('TMP_DIR')
if not TMP_DIR:
    TMP_DIR = "/tmp"
    logging.warning("TMP_DIR is empty, falling back to default path: [%s]", TMP_DIR )
TMP_DIR = os.path.join(TMP_DIR, datetime.now().strftime("%Y%m%d_%H%M%S"))
logging.debug("TMP_DIR: [%s]", TMP_DIR)

PORTAINER_API_URL = os.environ.get('BACKUP_API_URL')
if not PORTAINER_API_URL:
    logging.critical("PORTAINER_API_URL is empty!")
    raise Exception("Invalid PORTAINER_API_URL")
logging.debug("PORTAINER_API_URL: [%s]", PORTAINER_API_URL)

PORTAINER_API_KEY = os.environ.get('API_KEY')
if not PORTAINER_API_KEY:
    logging.critical("API_KEY is empty!")
    raise Exception("Invalid API_KEY")
logging.debug("API_KEY length: [%s]", len(PORTAINER_API_KEY))

PORTAINER_BACKUP_FILE = os.path.join(TMP_DIR, "portainer_backup.tar.gz")
logging.debug("PORTAINER_BACKUP_FILE: [%s]", PORTAINER_BACKUP_FILE)

# Function to compress a folder
def MakeTar(source_dir, output_filename):
    logging.debug("Compressing: [%s] to: [%s]", source_dir, output_filename)
    try:
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))
        return True
    except:
        return False

# Function to request Portainer backup
def request_portainer_backup(api_url, api_key, output_file):
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json; charset=utf-8"
    }
    data = {
        "password": ""
    }
    response = requests.post(api_url, headers=headers, json=data, verify=False, timeout=10)
    if response.status_code == 200:
        with open(output_file, 'wb') as f:
            f.write(response.content)
        logging.info("Portainer backup saved to: [%s]", output_file)
        return True
    else:
        logging.error("Failed to request Portainer backup: [%s]", response.text)
        return False

# Function to send Portainer backup to Telegram
def send_portainer_backup_to_telegram(bot_token, chat_id, file_path):
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    files = {'document': open(file_path, 'rb')}
    data = {'chat_id': chat_id}
    response = requests.post(url, files=files, data=data, timeout=10)
    if response.status_code == 200:
        logging.info("Portainer backup sent to Telegram successfully")
        return True
    else:
        logging.error("Failed to send Portainer backup to Telegram: [%s]", response.text)
        return False

if __name__ == '__main__':
    # Send custom message
    bot.send_message(TELEGRAM_DEST_CHAT, TELEGRAM_BACKUP_MESSAGE)
    # Create temporary output path
    if not os.path.exists(TMP_DIR):
        logging.info("Creating: [" + TMP_DIR + "] folder")
        os.mkdir(TMP_DIR)
    else:
        logging.warning("Folder: [" + TMP_DIR + "] already exists, this could cause some troubles")
    # Process path(s) list
    for singleLocation in DOCKER_VOLUME_DIRECTORIES:
        try:
            # Check if we can access that folder
            subFolders = os.listdir(singleLocation)
        except FileNotFoundError:
            logging.warning("Cannot access path: [" + singleLocation + "]")
            continue
        # If the path exists
        for singleSubfolder in subFolders:
            folderToCompress = os.path.join(singleLocation, singleSubfolder)
            # Check if it is a folder
            if os.path.isdir(folderToCompress):
                logging.debug("Found valid folder: " + folderToCompress)
                archiveName = singleSubfolder + "-" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".tar.gz"
                outputPath = os.path.join(TMP_DIR, archiveName)
                if (MakeTar(folderToCompress, outputPath)):
                    logging.info("Succesfully compressed: [" + outputPath + "]")
                    # Send archive
                    try:
                        bot.send_document(TELEGRAM_DEST_CHAT, open(outputPath, 'rb'))
                        logging.debug("Document: [" + outputPath + "] was sent succesfully")
                    except Exception as retEx:
                        logging.error("Cannot send document: [" + str(retEx) + "]")
                    # Delete archive
                    try:
                        os.remove(outputPath)
                        logging.debug("File: [" + outputPath + "] was deleted succesfully")
                    except Exception as retEx:
                        logging.error("Error while deleting: [" + retEx + "]")
                else:
                    logging.error("Cannot compress: [" + outputPath + "]")
    try:
        # Send log file
        bot.send_document(TELEGRAM_DEST_CHAT, open(logFile, 'rb'))
        logging.debug("Backup file sent")
    except Exception as retEx:
        logging.error("Error while sending log file: [" + str(retEx) + "]")

    # Request and send Portainer backup
    if request_portainer_backup(PORTAINER_API_URL, PORTAINER_API_KEY, PORTAINER_BACKUP_FILE):
        send_portainer_backup_to_telegram(TELEGRAM_API_TOKEN, TELEGRAM_DEST_CHAT, PORTAINER_BACKUP_FILE)
    else:
        logging.error("Failed to request Portainer backup")

    # Done, bye!
    logging.info("Completed!")
